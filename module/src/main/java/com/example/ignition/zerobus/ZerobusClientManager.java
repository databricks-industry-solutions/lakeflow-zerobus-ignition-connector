package com.example.ignition.zerobus;

import com.databricks.zerobus.ZerobusSdk;
import com.databricks.zerobus.ZerobusStream;
import com.databricks.zerobus.TableProperties;
import com.databricks.zerobus.StreamConfigurationOptions;
import com.databricks.zerobus.IngestRecordResponse;
import com.databricks.zerobus.ZerobusException;
import com.databricks.zerobus.NonRetriableException;
import com.example.ignition.zerobus.proto.OTEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * ZerobusClientManager - Manages Databricks Zerobus SDK integration.
 * 
 * Responsibilities:
 * - Initialize Zerobus SDK with OAuth credentials
 * - Manage stream lifecycle
 * - Send batched events to Zerobus Ingest
 * - Handle retries, backoff, and error logging
 * - Provide diagnostics and metrics
 */
public class ZerobusClientManager {
    
    private static final Logger logger = LoggerFactory.getLogger(ZerobusClientManager.class);
    
    private final ConfigModel config;
    private AtomicBoolean initialized = new AtomicBoolean(false);
    private AtomicBoolean connected = new AtomicBoolean(false);
    
    // Metrics
    private AtomicLong totalEventsSent = new AtomicLong(0);
    private AtomicLong totalBatchesSent = new AtomicLong(0);
    private AtomicLong totalFailures = new AtomicLong(0);
    private volatile long lastSuccessfulSendTime = 0;
    private volatile long lastAckedOffset = 0;
    private volatile String lastError = null;
    
    // Zerobus SDK objects
    private ZerobusSdk zerobusSdk;
    private ZerobusStream<OTEvent> zerobusStream;
    private TableProperties<OTEvent> tableProperties;
    private StreamConfigurationOptions streamOptions;

    // Reconnect throttling to avoid hot-looping when the remote service is down.
    private final AtomicLong lastReconnectAttemptMs = new AtomicLong(0);
    private final Object reconnectLock = new Object();
    
    /**
     * Constructor.
     * 
     * @param config Configuration model with connection details
     */
    public ZerobusClientManager(ConfigModel config) {
        this.config = config;
    }
    
    /**
     * Initialize the Zerobus SDK and create a stream.
     * 
     * @throws Exception if initialization fails
     */
    public void initialize() throws Exception {
        if (initialized.get()) {
            logger.warn("ZerobusClientManager already initialized");
            return;
        }
        
        logger.info("Initializing Zerobus client...");
        logger.info("  Workspace URL: {}", config.getWorkspaceUrl());
        logger.info("  Zerobus Endpoint: {}", config.getZerobusEndpoint());
        logger.info("  Target Table: {}", config.getTargetTable());
        
        try {
            // Validate configuration
            List<String> errors = config.validate();
            if (!errors.isEmpty()) {
                throw new IllegalArgumentException("Invalid configuration: " + String.join(", ", errors));
            }
            
            // Initialize Zerobus SDK
            logger.info("Creating ZerobusSdk instance...");
            this.zerobusSdk = new ZerobusSdk(
                config.getZerobusEndpoint(),
                config.getWorkspaceUrl()
            );
            
            // Configure table properties
            this.tableProperties = new TableProperties<>(
                config.getTargetTable(),
                OTEvent.getDefaultInstance()
            );
            
            // Configure stream options
            this.streamOptions = StreamConfigurationOptions.builder()
                .setMaxInflightRecords(config.getMaxQueueSize())
                .setRecovery(true)
                .setRecoveryTimeoutMs((int) config.getConnectionTimeoutMs())
                .setRecoveryBackoffMs((int) config.getRetryBackoffMs())
                .setRecoveryRetries(config.getMaxRetries())
                .setFlushTimeoutMs((int) config.getRequestTimeoutMs())
                .setServerLackOfAckTimeoutMs((int) config.getRequestTimeoutMs())
                .setAckCallback(this::handleAcknowledgment)
                .build();
            
            // Create stream
            logger.info("Creating Zerobus stream...");
            CompletableFuture<ZerobusStream<OTEvent>> streamFuture = zerobusSdk.createStream(
                tableProperties,
                config.getOauthClientId(),
                config.getOauthClientSecret(),
                streamOptions
            );
            
            // Wait for stream creation (with timeout)
            this.zerobusStream = streamFuture.get(
                config.getConnectionTimeoutMs(),
                TimeUnit.MILLISECONDS
            );
            
            initialized.set(true);
            connected.set(true);
            
            logger.info("Zerobus client initialized successfully");
            logger.info("  Stream ID: {}", zerobusStream.getStreamId());
            logger.info("  Stream State: {}", zerobusStream.getState());
            
        } catch (Exception e) {
            logger.error("Failed to initialize Zerobus client", e);
            lastError = e.getMessage();
            throw e;
        }
    }
    
    /**
     * Shutdown the Zerobus client and close the stream.
     */
    public void shutdown() {
        if (!initialized.get()) {
            return;
        }
        
        logger.info("Shutting down Zerobus client...");
        
        try {
            // Flush and close the stream
            if (zerobusStream != null) {
                logger.info("Flushing stream...");
                zerobusStream.flush();
                
                logger.info("Closing stream...");
                zerobusStream.close();
                zerobusStream = null;
            }
            
            connected.set(false);
            initialized.set(false);
            
            logger.info("Zerobus client shut down successfully");
            
        } catch (Exception e) {
            logger.error("Error shutting down Zerobus client", e);
            lastError = e.getMessage();
        }
    }
    
    /**
     * Send a batch of events to Zerobus Ingest.
     * 
     * @param events List of TagEvent objects to send
     * @return true if successful, false otherwise
     */
    public boolean sendEvents(List<TagEvent> events) {
        if (!ensureConnected()) {
            logger.warn("Cannot send events - client not initialized or not connected");
            return false;
        }
        
        if (events == null || events.isEmpty()) {
            logger.debug("No events to send");
            return true;
        }
        
        logger.debug("Sending batch of {} events to Zerobus", events.size());
        
        try {
            // Convert and ingest all events, collecting futures
            List<CompletableFuture<Void>> futures = new ArrayList<>();
            
            for (TagEvent event : events) {
                OTEvent protoEvent = convertToProtobuf(event);
                
                // Ingest record - returns a future that completes when durably written
                CompletableFuture<Void> ingestFuture = zerobusStream.ingestRecord(protoEvent);
                futures.add(ingestFuture);
            }
            
            // Wait for ALL futures to complete (parallel, not serial!)
            CompletableFuture<Void> allFutures = CompletableFuture.allOf(
                futures.toArray(new CompletableFuture[0])
            );
            allFutures.get(config.getRequestTimeoutMs(), TimeUnit.MILLISECONDS);
            
            // Flush to ensure all records are sent
            zerobusStream.flush();
            
            // Update metrics
            totalEventsSent.addAndGet(events.size());
            totalBatchesSent.incrementAndGet();
            lastSuccessfulSendTime = System.currentTimeMillis();
            
            if (config.isDebugLogging()) {
                logger.debug("Batch sent successfully - {} events", events.size());
            }
            
            return true;
            
        } catch (NonRetriableException e) {
            // Fatal error - do not retry
            logger.error("Non-retriable error sending events to Zerobus", e);
            lastError = "Non-retriable: " + e.getMessage();
            totalFailures.incrementAndGet();
            connected.set(false);
            
            return false;
            
        } catch (ZerobusException e) {
            // Retriable error - log and attempt recovery
            logger.warn("Retriable error sending events to Zerobus", e);
            lastError = "Retriable: " + e.getMessage();
            totalFailures.incrementAndGet();
            
            // Attempt stream recovery
            attemptRecovery();
            
            return false;
            
        } catch (Exception e) {
            logger.error("Unexpected error sending events to Zerobus", e);
            lastError = "Unexpected: " + e.getMessage();
            totalFailures.incrementAndGet();
            connected.set(false);

            // Attempt recovery on unexpected failures as well; some gRPC/transport failures surface here.
            attemptRecovery();
            
            return false;
        }
    }

    /**
     * Best-effort: ensure the client is connected, attempting recovery/reinitialize with throttling.
     * This prevents the system from getting "stuck" in a disconnected state after a transient failure.
     */
    private boolean ensureConnected() {
        // If module is disabled, do not attempt to connect.
        if (!config.isEnabled()) {
            return false;
        }

        if (initialized.get() && connected.get()) {
            return true;
        }

        synchronized (reconnectLock) {
            if (initialized.get() && connected.get()) {
                return true;
            }

            long now = System.currentTimeMillis();
            long last = lastReconnectAttemptMs.get();
            long minInterval = Math.max(1000L, config.getRetryBackoffMs());
            if ((now - last) < minInterval) {
                return false;
            }
            lastReconnectAttemptMs.set(now);

            try {
                // If we have a stream but are disconnected, try stream recovery first.
                if (initialized.get() && !connected.get() && zerobusStream != null && zerobusSdk != null) {
                    attemptRecovery();
                    if (connected.get()) {
                        return true;
                    }
                }

                // Fallback: full reinitialize.
                try {
                    shutdown();
                } catch (Exception ignored) {
                    // shutdown is best-effort
                }
                initialize();
                return connected.get();
            } catch (Exception e) {
                lastError = e.getMessage();
                connected.set(false);
                return false;
            }
        }
    }
    
    /**
     * Test the connection to Zerobus.
     * 
     * @return true if connection is successful
     */
    public boolean testConnection() {
        logger.info("Testing Zerobus connection...");
        
        try {
            // Create a temporary SDK instance for testing
            ZerobusSdk testSdk = new ZerobusSdk(
                config.getZerobusEndpoint(),
                config.getWorkspaceUrl()
            );
            
            TableProperties<OTEvent> testTableProps = new TableProperties<>(
                config.getTargetTable(),
                OTEvent.getDefaultInstance()
            );
            
            StreamConfigurationOptions testOptions = StreamConfigurationOptions.builder()
                .setMaxInflightRecords(100)
                .setRecovery(false)
                .setFlushTimeoutMs(10000)
                .build();
            
            // Try to create a stream
            CompletableFuture<ZerobusStream<OTEvent>> streamFuture = testSdk.createStream(
                testTableProps,
                config.getOauthClientId(),
                config.getOauthClientSecret(),
                testOptions
            );
            
            ZerobusStream<OTEvent> testStream = streamFuture.get(10, TimeUnit.SECONDS);
            
            // Close the test stream
            testStream.close();
            
            logger.info("Connection test successful");
            return true;
            
        } catch (NonRetriableException e) {
            logger.error("Connection test failed with non-retriable error", e);
            lastError = e.getMessage();
            return false;
            
        } catch (Exception e) {
            logger.error("Connection test failed", e);
            lastError = e.getMessage();
            return false;
        }
    }
    
    /**
     * Attempt to recover a failed stream.
     */
    private void attemptRecovery() {
        if (!initialized.get() || zerobusStream == null) {
            logger.warn("Cannot attempt recovery - not initialized");
            return;
        }
        
        logger.info("Attempting stream recovery...");
        
        try {
            // Use SDK's recreateStream to recover
            CompletableFuture<ZerobusStream<OTEvent>> recoveryFuture = 
                zerobusSdk.recreateStream(zerobusStream);
            
            // Wait for recovery
            this.zerobusStream = recoveryFuture.get(
                config.getConnectionTimeoutMs(),
                TimeUnit.MILLISECONDS
            );
            
            connected.set(true);
            logger.info("Stream recovery successful");
            logger.info("  Stream ID: {}", zerobusStream.getStreamId());
            logger.info("  Stream State: {}", zerobusStream.getState());
            
        } catch (Exception e) {
            logger.error("Stream recovery failed", e);
            lastError = "Recovery failed: " + e.getMessage();
            connected.set(false);
        }
    }
    
    /**
     * Handle acknowledgment callback from Zerobus server.
     * 
     * @param response The acknowledgment response
     */
    private void handleAcknowledgment(IngestRecordResponse response) {
        long offset = response.getDurabilityAckUpToOffset();
        this.lastAckedOffset = offset;
        
        if (config.isDebugLogging()) {
            logger.debug("Received acknowledgment up to offset: {}", offset);
        }
    }
    
    /**
     * Convert a TagEvent to OTEvent protobuf message.
     * 
     * @param event The tag event to convert
     * @return OTEvent protobuf message
     */
    private OTEvent convertToProtobuf(TagEvent event) {
        // Generate unique event ID
        String eventId = java.util.UUID.randomUUID().toString();
        
        // Get current time in milliseconds for ingestion timestamp
        long ingestionTime = System.currentTimeMillis();
        
        // Extract tag provider from tag path (e.g., "[default]TagName" -> "default")
        String tagProvider = "default";
        String tagPath = event.getTagPath();
        if (tagPath != null && tagPath.startsWith("[") && tagPath.contains("]")) {
            int endBracket = tagPath.indexOf("]");
            tagProvider = tagPath.substring(1, endBracket);
        }
        
        // Determine data type
        String dataType = "UNKNOWN";
        if (event.isNumeric()) {
            dataType = "DOUBLE";
        } else if (event.isString()) {
            dataType = "STRING";
        } else if (event.isBoolean()) {
            dataType = "BOOLEAN";
        }
        
        // Build the OTEvent
        // Note: Delta TIMESTAMP expects microseconds (not milliseconds) when using int64
        long eventTimeMicros = event.getTimestamp().getTime() * 1000;  // Convert millis to micros
        long ingestionTimeMicros = ingestionTime * 1000;  // Convert millis to micros
        
        OTEvent.Builder builder = OTEvent.newBuilder()
            .setEventId(eventId)
            .setEventTime(eventTimeMicros)
            .setTagPath(tagPath != null ? tagPath : "")
            .setTagProvider(tagProvider)
            .setQuality(event.getQuality() != null ? event.getQuality() : "UNKNOWN")
            .setQualityCode(event.isGoodQuality() ? 192 : 0)  // 192 is Ignition's GOOD quality code
            .setSourceSystem(config.getSourceSystemId())
            .setIngestionTimestamp(ingestionTimeMicros)
            .setDataType(dataType)
            .setAlarmState("")  // Empty if not in alarm
            .setAlarmPriority(0);  // 0 if no alarm
        
        // Set the appropriate value field based on type
        if (event.isNumeric()) {
            builder.setNumericValue(event.getValueAsDouble());
        } else {
            builder.setNumericValue(0.0);
        }
        
        if (event.isString()) {
            builder.setStringValue(event.getValueAsString());
        } else {
            builder.setStringValue("");
        }
        
        if (event.isBoolean()) {
            builder.setBooleanValue(event.getValueAsBoolean());
        } else {
            builder.setBooleanValue(false);
        }
        
        return builder.build();
    }
    
    /**
     * Get diagnostics information for monitoring.
     * 
     * @return Diagnostics string
     */
    public String getDiagnostics() {
        StringBuilder sb = new StringBuilder();
        sb.append("=== Zerobus Client Diagnostics ===\n");
        sb.append("Initialized: ").append(initialized.get()).append("\n");
        sb.append("Connected: ").append(connected.get()).append("\n");
        
        if (zerobusStream != null) {
            sb.append("Stream ID: ").append(zerobusStream.getStreamId()).append("\n");
            sb.append("Stream State: ").append(zerobusStream.getState()).append("\n");
        }
        
        sb.append("Total Events Sent: ").append(totalEventsSent.get()).append("\n");
        sb.append("Total Batches Sent: ").append(totalBatchesSent.get()).append("\n");
        sb.append("Total Failures: ").append(totalFailures.get()).append("\n");
        sb.append("Last Acked Offset: ").append(lastAckedOffset).append("\n");
        
        if (lastSuccessfulSendTime > 0) {
            long secondsAgo = (System.currentTimeMillis() - lastSuccessfulSendTime) / 1000;
            sb.append("Last Successful Send: ").append(secondsAgo).append(" seconds ago\n");
        } else {
            sb.append("Last Successful Send: Never\n");
        }
        
        if (lastError != null) {
            sb.append("Last Error: ").append(lastError).append("\n");
        }
        
        return sb.toString();
    }
    
    // Metric getters
    
    public long getTotalEventsSent() {
        return totalEventsSent.get();
    }
    
    public long getTotalBatchesSent() {
        return totalBatchesSent.get();
    }
    
    public long getTotalFailures() {
        return totalFailures.get();
    }
    
    public boolean isInitialized() {
        return initialized.get();
    }
    
    public boolean isConnected() {
        return connected.get();
    }
    
    public String getStreamId() {
        return zerobusStream != null ? zerobusStream.getStreamId() : null;
    }
}
