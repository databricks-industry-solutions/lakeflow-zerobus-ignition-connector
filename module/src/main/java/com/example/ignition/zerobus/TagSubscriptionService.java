package com.example.ignition.zerobus;

import com.example.ignition.zerobus.web.TagEventPayload;
import com.example.ignition.zerobus.pipeline.OtEventMapper;
import com.example.ignition.zerobus.pipeline.StoreAndForwardBuffer;
import com.example.ignition.zerobus.pipeline.EventSink;
import com.example.ignition.zerobus.pipeline.ZerobusPipelineFactory;
import com.example.ignition.zerobus.proto.OTEvent;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import com.inductiveautomation.ignition.gateway.tags.model.GatewayTagManager;
import com.inductiveautomation.ignition.common.model.values.QualifiedValue;
import com.inductiveautomation.ignition.common.tags.model.TagPath;
import com.inductiveautomation.ignition.common.tags.paths.parser.TagPathParser;
import com.inductiveautomation.ignition.common.tags.model.event.TagChangeEvent;
import com.inductiveautomation.ignition.common.tags.model.event.TagChangeListener;
import com.inductiveautomation.ignition.common.tags.model.event.InvalidListenerException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * TagSubscriptionService - Event-driven tag event processing service.
 * 
 * This service receives tag events from Ignition Event Streams via REST API:
 * - Receives tag events from Event Stream Script handlers
 * - Queues events with backpressure management
 * - Batches events by count and time window
 * - Applies rate limiting
 * - Sends batches to ZerobusClientManager
 * 
 * ALSO SUPPORTED (recommended for Ignition 8.1): direct Gateway tag subscriptions:
 * - Subscribes to tags using Ignition TagManager (no scripts, no HTTP hop)
 * - Converts TagChangeEvent → TagEvent and queues for batching
 */
public class TagSubscriptionService {
    
    private static final Logger logger = LoggerFactory.getLogger(TagSubscriptionService.class);
    
    private final GatewayContext gatewayContext;
    private final ConfigModel config;
    
    private AtomicBoolean running = new AtomicBoolean(false);
    private ScheduledExecutorService scheduledExecutor;
    private final StoreAndForwardBuffer buffer;
    private final OtEventMapper mapper;
    private final EventSink sink;

    // Direct tag subscription state
    private volatile GatewayTagManager tagManager;
    private final Map<TagPath, TagChangeListener> subscribedListeners = new ConcurrentHashMap<>();
    private final Map<String, Object> lastSentValueByTag = new ConcurrentHashMap<>();
    private volatile boolean autoPausedDirectSubscriptions = false;
    
    // Metrics
    private AtomicLong totalEventsReceived = new AtomicLong(0);
    private AtomicLong totalEventsDropped = new AtomicLong(0);
    private AtomicLong totalBatchesFlushed = new AtomicLong(0);
    
    // Rate limiting
    private volatile long lastFlushTime = 0;
    private AtomicLong eventsThisSecond = new AtomicLong(0);
    private volatile long currentSecond = 0;
    
    /**
     * Constructor.
     * 
     * @param gatewayContext Ignition Gateway context
     * @param config Configuration model
     */
    public TagSubscriptionService(GatewayContext gatewayContext,
                                  ConfigModel config,
                                  OtEventMapper mapper,
                                  StoreAndForwardBuffer buffer,
                                  EventSink sink) {
        this.gatewayContext = gatewayContext;
        this.config = config;
        this.mapper = mapper;
        this.buffer = buffer;
        this.sink = sink;
    }

    private TagSubscriptionService(GatewayContext gatewayContext,
                                   ConfigModel config,
                                   ZerobusPipelineFactory.PipelineComponents comps) {
        this(gatewayContext, config, comps.mapper, comps.buffer, comps.sink);
    }

    /**
     * Backwards-compatible convenience constructor.
     *
     * Prefer injecting {@link OtEventMapper}, {@link StoreAndForwardBuffer}, and {@link EventSink}
     * (or using {@link ZerobusPipelineFactory}) so this service is not responsible for wiring.
     */
    @Deprecated
    public TagSubscriptionService(GatewayContext gatewayContext,
                                  ZerobusClientManager zerobusClientManager,
                                  ConfigModel config) {
        this(gatewayContext, config, ZerobusPipelineFactory.create(config, zerobusClientManager));
    }
    
    /**
     * Start the tag event processing service.
     * 
     * This service is event-driven. It can ingest events in two ways:
     * - Direct Gateway tag subscription (preferred for Ignition 8.1/8.2)
     * - REST ingest endpoints (for Event Streams or external forwarding)
     */
    public void start() {
        if (running.get()) {
            logger.warn("TagSubscriptionService already running");
            return;
        }
        
        logger.info("Starting Zerobus Event Processing Service...");
        logger.info("Mode: Event-driven (Gateway subscriptions + optional REST ingest)");
        
        try {
            running.set(true);
            
            // Create scheduled executor for periodic flushing
            scheduledExecutor = Executors.newSingleThreadScheduledExecutor(r -> {
                Thread t = new Thread(r, "Zerobus-Flush-Thread");
                t.setDaemon(true);
                return t;
            });
            
            // Schedule periodic flushing of queued events
            scheduledExecutor.scheduleAtFixedRate(
                this::flushBatch,
                config.getBatchFlushIntervalMs(),
                config.getBatchFlushIntervalMs(),
                TimeUnit.MILLISECONDS
            );
            
            logger.info("Event processing service started successfully");
            logger.info("  Buffering: {}", buffer.isDiskBacked() ? "disk store-and-forward" : "in-memory");
            logger.info("  Batch size: {}", config.getBatchSize());
            logger.info("  Flush interval: {}ms", config.getBatchFlushIntervalMs());

            // Direct subscription: subscribe to configured tags
            subscribeConfiguredTags();
            
        } catch (Exception e) {
            logger.error("Failed to start event processing service", e);
            running.set(false);
            throw new RuntimeException("Failed to start event processing service", e);
        }
    }
    
    /**
     * Shutdown the event processing service.
     */
    public void shutdown() {
        if (!running.get()) {
            return;
        }
        
        logger.info("Shutting down event processing service...");
        
        running.set(false);
        
        try {
            // Unsubscribe tags first (stop incoming events)
            unsubscribeAll();

            // Flush any remaining events
            flushBatch();
            
            // Shutdown executors
            if (scheduledExecutor != null) {
                scheduledExecutor.shutdown();
                if (!scheduledExecutor.awaitTermination(5, TimeUnit.SECONDS)) {
                    scheduledExecutor.shutdownNow();
                }
            }
            
            logger.info("Event processing service shut down successfully");
            
        } catch (Exception e) {
            logger.error("Error shutting down event processing service", e);
        }
    }

    public boolean isRunning() {
        return running.get();
    }
    
    
    
    
    
    private void subscribeConfiguredTags() {
        try {
            // If disabled, don't subscribe
            if (!config.isEnabled()) {
                logger.info("Module disabled; skipping direct tag subscriptions");
                return;
            }

            // If configured for HTTP-ingest-only, don't subscribe
            if (!config.isEnableDirectSubscriptions()) {
                logger.info("Direct subscriptions disabled; skipping tag subscriptions (HTTP ingest only)");
                return;
            }

            // Only implement explicit mode for now; it's the safest and most deterministic.
            String mode = config.getTagSelectionMode();
            if (!"explicit".equals(mode)) {
                logger.warn("Direct tag subscriptions currently support tagSelectionMode='explicit' only. Current mode='{}'. " +
                        "You can still ingest via REST endpoints (/system/zerobus/ingest).", mode);
                return;
            }

            List<String> paths = config.getExplicitTagPaths();
            if (paths == null || paths.isEmpty()) {
                logger.warn("No explicitTagPaths configured; nothing to subscribe to");
                return;
            }

            this.tagManager = (GatewayTagManager) gatewayContext.getTagManager();

            List<TagPath> tagPaths = new ArrayList<>();
            List<TagChangeListener> listeners = new ArrayList<>();

            for (String pathStr : paths) {
                if (pathStr == null || pathStr.trim().isEmpty()) {
                    continue;
                }
                try {
                    TagPath tagPath = TagPathParser.parse(pathStr.trim());
                    TagChangeListener listener = new DirectTagChangeListener();
                    tagPaths.add(tagPath);
                    listeners.add(listener);
                    subscribedListeners.put(tagPath, listener);
                } catch (Exception parseErr) {
                    logger.warn("Invalid tag path '{}': {}", pathStr, parseErr.getMessage());
                }
            }

            if (tagPaths.isEmpty()) {
                logger.warn("No valid tag paths to subscribe to after parsing");
                return;
            }

            tagManager.subscribeAsync(tagPaths, listeners)
                    .whenComplete((ok, err) -> {
                        if (err != null) {
                            logger.error("Failed to subscribe to {} tags", tagPaths.size(), err);
                        } else {
                            logger.info("Subscribed to {} tags via Gateway TagManager", tagPaths.size());
                            if (config.isDebugLogging()) {
                                for (TagPath tp : tagPaths) {
                                    logger.debug("  subscribed: {}", tp.toString());
                                }
                            }
                        }
                    });

        } catch (Throwable t) {
            logger.error("Error starting direct tag subscriptions", t);
        }
    }

    private void unsubscribeAll() {
        try {
            if (tagManager == null || subscribedListeners.isEmpty()) {
                return;
            }
            List<TagPath> paths = new ArrayList<>(subscribedListeners.keySet());
            List<TagChangeListener> listeners = new ArrayList<>();
            for (TagPath tp : paths) {
                TagChangeListener l = subscribedListeners.get(tp);
                if (l != null) {
                    listeners.add(l);
                }
            }

            // Clear maps immediately to avoid double-unsubscribe
            subscribedListeners.clear();
            lastSentValueByTag.clear();

            if (paths.isEmpty() || listeners.isEmpty()) {
                return;
            }

            tagManager.unsubscribeAsync(paths, listeners)
                    .whenComplete((ok, err) -> {
                        if (err != null) {
                            logger.warn("Error unsubscribing from tags", err);
                        } else {
                            logger.info("Unsubscribed from {} tags", paths.size());
                        }
                    });
        } catch (Throwable t) {
            logger.warn("Error while unsubscribing tags", t);
        } finally {
            tagManager = null;
        }
    }

    private final class DirectTagChangeListener implements TagChangeListener {
        @Override
        public void tagChanged(TagChangeEvent event) throws InvalidListenerException {
            if (!running.get()) {
                return;
            }
            if (event == null) {
                return;
            }

            // Avoid startup floods by skipping initial values
            if (event.isInitial()) {
                return;
            }

            // Rate limiting
            if (!checkRateLimit()) {
                totalEventsDropped.incrementAndGet();
                return;
            }

            TagPath tagPath = event.getTagPath();
            String tagPathStr = tagPath != null ? tagPath.toString() : "";

            QualifiedValue qv = event.getValue();
            Object value = qv != null ? qv.getValue() : null;
            Date ts = (qv != null && qv.getTimestamp() != null) ? qv.getTimestamp() : new Date();
            String quality = (qv != null && qv.getQuality() != null) ? qv.getQuality().toString() : "UNKNOWN";

            // optional filtering: onlyOnChange + numeric deadband
            if (config.isOnlyOnChange()) {
                Object last = lastSentValueByTag.get(tagPathStr);
                if (!hasMeaningfulChange(last, value)) {
                    return;
                }
                lastSentValueByTag.put(tagPathStr, value);
            }

            acceptTagEvent(new TagEvent(tagPathStr, value, quality, ts), "direct");
        }
    }

    private boolean hasMeaningfulChange(Object last, Object current) {
        if (last == null && current == null) {
            return false;
        }
        if (last == null || current == null) {
            return true;
        }
        if (last instanceof Number && current instanceof Number) {
            double a = ((Number) last).doubleValue();
            double b = ((Number) current).doubleValue();
            double deadband = config.getNumericDeadband();
            return Math.abs(a - b) > deadband;
        }
        return !Objects.equals(last, current);
    }
    
    /**
     * Flush a batch of events to Zerobus.
     * 
     * Note: Not synchronized - uses thread-safe queue operations.
     * Multiple threads can call this concurrently without blocking each other.
     */
    private void flushBatch() {
        try {
            // Update backpressure + pause/resume subscriptions when disk-backed
            buffer.refreshBackpressure();
            if (buffer.isDiskBacked()) {
                if (buffer.isPaused() && !autoPausedDirectSubscriptions && !subscribedListeners.isEmpty()) {
                    logger.warn("Auto-pausing direct subscriptions due to backpressure (spool high watermark).");
                    autoPausedDirectSubscriptions = true;
                    unsubscribeAll();
                } else if (!buffer.isPaused() && autoPausedDirectSubscriptions) {
                    logger.info("Backpressure cleared; resubscribing direct subscriptions.");
                    autoPausedDirectSubscriptions = false;
                    subscribeConfiguredTags();
                }
            }

            // Sink-down behavior: do NOT drain (especially disk spool) unless the sink is connected/ready.
            // This avoids repeatedly reading/parsing the same records when disconnected.
            if (!sink.isReady()) {
                sink.tryEnsureReady();
                if (!sink.isReady()) {
                    return;
                }
            }

            StoreAndForwardBuffer.DrainResult drained = buffer.drain(config.getBatchSize());
            if (drained.events == null || drained.events.isEmpty()) {
                return;
            }

            logger.debug("Flushing batch of {} events", drained.events.size());
            boolean success = sink.send(drained.events);
            if (success) {
                buffer.commit(drained);
                totalBatchesFlushed.incrementAndGet();
                lastFlushTime = System.currentTimeMillis();
            } else {
                // Do NOT commit; records remain for retry. For memory mode, commit is required to remove.
                logger.warn("Failed to send batch of {} events (will retry)", drained.events.size());
            }
        } catch (Exception e) {
            logger.error("Error flushing batch", e);
        }
    }

    private boolean acceptTagEvent(TagEvent te, String source) {
        if (te == null) {
            return true;
        }

        // When store-and-forward is enabled and we're paused, reject new events rather than drop later.
        buffer.refreshBackpressure();
        if (buffer.isDiskBacked() && buffer.isPaused()) {
            totalEventsDropped.incrementAndGet();
            return false;
        }

        OTEvent evt = mapper.map(te);
        boolean ok = buffer.offer(evt);
        if (ok) {
            totalEventsReceived.incrementAndGet();
            if (config.isDebugLogging()) {
                logger.debug("Accepted tag event ({}) -> {}", source, te.getTagPath());
            }
        } else {
            totalEventsDropped.incrementAndGet();
            logger.warn("Buffer full, dropped event ({}) -> {}", source, te.getTagPath());
        }
        return ok;
    }
    
    /**
     * Check if the rate limit allows processing this event.
     * 
     * @return true if within rate limit
     */
    private boolean checkRateLimit() {
        long now = System.currentTimeMillis() / 1000; // Current second
        
        if (now != currentSecond) {
            // New second - reset counter
            currentSecond = now;
            eventsThisSecond.set(0);
        }
        
        long count = eventsThisSecond.incrementAndGet();
        return count <= config.getMaxEventsPerSecond();
    }
    
    
    /**
     * Get diagnostics information.
     * 
     * @return Diagnostics string
     */
    public String getDiagnostics() {
        StringBuilder sb = new StringBuilder();
        sb.append("=== Event Processing Service Diagnostics ===\n");
        sb.append("Running: ").append(running.get()).append("\n");
        sb.append("Mode: Event-driven (Gateway subscriptions + optional REST ingest)\n");
        if (buffer.isDiskBacked()) {
            sb.append("Buffer: disk store-and-forward\n");
            sb.append("Spool Backlog: ").append(buffer.backlogBytes()).append(" bytes\n");
            sb.append("Backpressure Paused: ").append(buffer.isPaused()).append("\n");
        } else {
            sb.append("Buffer: in-memory\n");
            sb.append("Queue Size: ").append(buffer.backlogBytes())
                .append("/").append(config.getMaxQueueSize()).append("\n");
        }
        sb.append("Total Events Received: ").append(totalEventsReceived.get()).append("\n");
        sb.append("Total Events Dropped: ").append(totalEventsDropped.get()).append("\n");
        sb.append("Total Batches Flushed: ").append(totalBatchesFlushed.get()).append("\n");
        sb.append("Direct Subscriptions: ").append(subscribedListeners.size()).append(" tags\n");
        sb.append("Auto-Paused Direct Subscriptions: ").append(autoPausedDirectSubscriptions).append("\n");
        
        if (lastFlushTime > 0) {
            long secondsAgo = (System.currentTimeMillis() - lastFlushTime) / 1000;
            sb.append("Last Flush: ").append(secondsAgo).append(" seconds ago\n");
        } else {
            sb.append("Last Flush: Never\n");
        }
        
        return sb.toString();
    }
    
    /**
     * Ingest a single tag event from Event Streams.
     * This method is called by the REST endpoint when Event Streams sends tag events.
     * 
     * @param payload Tag event payload from Event Streams
     * @return true if event was accepted, false if queue is full
     */
    public boolean ingestEvent(TagEventPayload payload) {
        if (!running.get()) {
            logger.warn("Cannot ingest event: service not running");
            return false;
        }
        
        try {
            if (!checkRateLimit()) {
                totalEventsDropped.incrementAndGet();
                return false;
            }
            // Convert payload to TagEvent
            TagEvent event = convertPayloadToEvent(payload);
            return acceptTagEvent(event, "http");
            
        } catch (Exception e) {
            logger.error("Error ingesting event from Event Streams", e);
            return false;
        }
    }
    
    /**
     * Ingest a batch of tag events from Event Streams.
     * This method is called by the REST endpoint when Event Streams sends batched tag events.
     * 
     * @param payloads Array of tag event payloads from Event Streams
     * @return number of events accepted
     */
    public int ingestEventBatch(TagEventPayload[] payloads) {
        if (!running.get()) {
            logger.warn("Cannot ingest batch: service not running");
            return 0;
        }
        
        int accepted = 0;
        
        for (TagEventPayload payload : payloads) {
            try {
                if (!checkRateLimit()) {
                    totalEventsDropped.incrementAndGet();
                    continue;
                }
                TagEvent event = convertPayloadToEvent(payload);
                if (acceptTagEvent(event, "http-batch")) {
                    accepted++;
                }
                
            } catch (Exception e) {
                logger.error("Error processing event from batch: {}", payload.getTagPath(), e);
            }
        }
        
        logger.debug("Batch ingestion: {} of {} events accepted", accepted, payloads.length);
        return accepted;
    }
    
    /**
     * Convert TagEventPayload from Event Streams to internal TagEvent.
     * 
     * @param payload TagEventPayload from Event Streams
     * @return TagEvent for internal processing
     */
    private TagEvent convertPayloadToEvent(TagEventPayload payload) {
        // Extract timestamp (Event Streams provides it in milliseconds)
        long timestampMs = payload.getTimestamp() != null ? payload.getTimestamp() : System.currentTimeMillis();
        Date timestamp = new Date(timestampMs);
        
        // Extract quality
        String quality = payload.getQuality() != null ? payload.getQuality() : "GOOD";
        
        // Create TagEvent using simple constructor
        // The ZerobusClientManager will extract additional metadata during protobuf conversion
        return new TagEvent(
            payload.getTagPath(),
            payload.getValue(),
            quality,
            timestamp
        );
    }
    
    /**
     * Determine the data type from the value object.
     * 
     * @param value The value object
     * @return String representation of the data type
     */
    private String determineDataType(Object value) {
        if (value == null) {
            return "NULL";
        } else if (value instanceof Boolean) {
            return "Boolean";
        } else if (value instanceof Integer) {
            return "Int4";
        } else if (value instanceof Long) {
            return "Int8";
        } else if (value instanceof Float) {
            return "Float4";
        } else if (value instanceof Double) {
            return "Float8";
        } else if (value instanceof String) {
            return "String";
        } else {
            return value.getClass().getSimpleName();
        }
    }
}

