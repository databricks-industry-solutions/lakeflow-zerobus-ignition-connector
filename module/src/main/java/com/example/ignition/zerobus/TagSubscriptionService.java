package com.example.ignition.zerobus;

import com.example.ignition.zerobus.web.TagEventPayload;
import com.example.ignition.zerobus.pipeline.OtEventMapper;
import com.example.ignition.zerobus.pipeline.StoreAndForwardBuffer;
import com.example.ignition.zerobus.pipeline.EventSink;
import com.example.ignition.zerobus.pipeline.ZerobusPipelineFactory;
import com.example.ignition.zerobus.proto.OTEvent;
import com.example.ignition.zerobus.compression.SdtValidationManager;
import com.example.ignition.zerobus.compression.SdtValidationReport;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import com.inductiveautomation.ignition.gateway.tags.model.GatewayTagManager;
import com.inductiveautomation.ignition.common.model.values.QualifiedValue;
import com.inductiveautomation.ignition.common.tags.browsing.NodeDescription;
import com.inductiveautomation.ignition.common.tags.config.types.TagObjectType;
import com.inductiveautomation.ignition.common.tags.model.TagPath;
import com.inductiveautomation.ignition.common.tags.paths.parser.TagPathParser;
import com.inductiveautomation.ignition.common.tags.model.event.TagChangeEvent;
import com.inductiveautomation.ignition.common.tags.model.event.TagChangeListener;
import com.inductiveautomation.ignition.common.tags.model.event.InvalidListenerException;
import com.inductiveautomation.ignition.common.browsing.BrowseFilter;
import com.inductiveautomation.ignition.common.browsing.Results;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.*;
import java.util.regex.Pattern;
import java.util.regex.PatternSyntaxException;
import java.util.Arrays;
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
    private static final int COMPRESSION_WINDOW_MINUTES = 15;
    private static final int COMPRESSION_TAG_STATS_MAX = 5000;
    
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
    private final Map<String, Object> lastEmittedValueByTag = new ConcurrentHashMap<>();
    private final Map<String, SdtCompressor.State> sdtStateByTag = new ConcurrentHashMap<>();
    private volatile boolean autoPausedDirectSubscriptions = false;
    
    // Metrics
    private AtomicLong totalEventsReceived = new AtomicLong(0);
    private AtomicLong totalEventsDropped = new AtomicLong(0);
    private AtomicLong totalBatchesFlushed = new AtomicLong(0);

    // Compression metrics (edge reduction)
    private final AtomicLong totalEventsFilteredDeadband = new AtomicLong(0);
    private final AtomicLong totalEventsFilteredSdt = new AtomicLong(0);
    private final AtomicLong totalEventsEmittedSdt = new AtomicLong(0);
    private final AtomicLong totalEventsForcedBySdtMaxInterval = new AtomicLong(0);
    private final AtomicLong totalSdtOutOfOrderResets = new AtomicLong(0);

    // Rolling window metrics for visual diagnostics (last N minutes)
    private final RollingCompressionMetrics rolling = new RollingCompressionMetrics(COMPRESSION_WINDOW_MINUTES);
    private final RollingLatencyMetrics rollingLatency = new RollingLatencyMetrics(COMPRESSION_WINDOW_MINUTES);

    // Per-tag stats (bounded) to highlight which signals get compressed
    private final ConcurrentHashMap<String, TagCompressionStats> perTagCompression = new ConcurrentHashMap<>();

    // SDT validation buffers (raw points + pivot markers) for deviation-band proof
    private final SdtValidationManager sdtValidationManager = new SdtValidationManager();
    
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

            // Direct subscription: subscribe to configured tags.
            //
            // IMPORTANT:
            // Do NOT do folder/pattern resolution synchronously on the module startup thread.
            // Browsing large tag trees (or browsing before the tag system is fully ready) can block
            // gateway startup and keep /system/* endpoints returning 503.
            //
            // Instead, start subscriptions asynchronously.
            Thread t = new Thread(() -> {
                try {
                    // If the service was stopped before this thread ran, exit.
                    if (!running.get()) {
                        return;
                    }
                    subscribeConfiguredTags();
                } catch (Throwable err) {
                    logger.error("Error starting direct tag subscriptions (async)", err);
                }
            }, "Zerobus-DirectSubs-Init");
            t.setDaemon(true);
            t.start();
            
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

            // IMPORTANT:
            // - In disk SAF mode, events are already persisted; do NOT block shutdown on network/auth recovery.
            // - In memory mode, we can do a best-effort flush, but we must NOT attempt reconnect during shutdown.
            if (!buffer.isDiskBacked()) {
                flushBatch(false);
            }
            
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

    /**
     * Generate an SDT validation report by comparing raw points vs linear interpolation of emitted pivots.
     *
     * This is primarily intended for demos and tuning (proving the deviation guarantee).
     */
    public SdtValidationReport getSdtValidationReport(int maxTags, int samplePoints) {
        // If we haven't recorded any SDT points yet, return an "unavailable" report.
        if (sdtValidationManager.getTrackedTagCount() == 0) {
            SdtValidationReport r = new SdtValidationReport();
            r.enabled = false;
            r.deviationConfigured = config.getNumericSdtDeviation();
            r.sdtMaxIntervalMs = config.getNumericSdtMaxIntervalMs();
            r.sdtMinIntervalMs = config.getNumericSdtMinIntervalMs();
            r.trackedTags = 0;
            r.overallVerdict = "PASS";
            r.tags = java.util.Collections.emptyList();
            return r;
        }

        // Use global SDT params for the report header.
        // Note: per-tag overrides may exist; this report is still useful as a "best-effort" proof.
        return sdtValidationManager.generateReport(
                config.getNumericSdtDeviation(),
                config.getNumericSdtMaxIntervalMs(),
                config.getNumericSdtMinIntervalMs(),
                maxTags,
                samplePoints
        );
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

            GatewayTagManager tm;
            try {
                tm = (GatewayTagManager) gatewayContext.getTagManager();
                this.tagManager = tm;
            } catch (Throwable t) {
                logger.error("Unable to acquire GatewayTagManager; direct subscriptions will be disabled", t);
                this.tagManager = null;
                tm = null;
            }
            if (tm == null) {
                logger.error("GatewayTagManager is null; cannot start direct tag subscriptions");
                return;
            }

            List<TagPath> tagPaths = new ArrayList<>();
            List<TagChangeListener> listeners = new ArrayList<>();

            // Resolve which tag paths to subscribe to (explicit, folder, or pattern).
            // IMPORTANT: use the local `tm` reference for all browse/subscribe operations.
            // This prevents a race where shutdown/unsubscribe can null out the field reference mid-browse.
            List<TagPath> resolved = resolveConfiguredTagPaths(tm);
            for (TagPath tagPath : resolved) {
                if (tagPath == null) {
                    continue;
                }
                TagChangeListener listener = new DirectTagChangeListener();
                tagPaths.add(tagPath);
                listeners.add(listener);
                subscribedListeners.put(tagPath, listener);
            }

            if (tagPaths.isEmpty()) {
                logger.warn("No valid tag paths to subscribe to after parsing");
                return;
            }

            tm.subscribeAsync(tagPaths, listeners)
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

    private List<TagPath> resolveConfiguredTagPaths(GatewayTagManager tm) {
        String mode = config.getTagSelectionMode() != null ? config.getTagSelectionMode().trim() : "explicit";

        if ("explicit".equalsIgnoreCase(mode)) {
            return resolveExplicitTagPaths();
        }
        if ("folder".equalsIgnoreCase(mode)) {
            return resolveFolderTagPaths(tm);
        }
        if ("pattern".equalsIgnoreCase(mode)) {
            return resolvePatternTagPaths(tm);
        }

        logger.warn("Unknown tagSelectionMode='{}'. Falling back to explicit.", mode);
        return resolveExplicitTagPaths();
    }

    private List<TagPath> resolveExplicitTagPaths() {
        List<String> paths = config.getExplicitTagPaths();
        if (paths == null || paths.isEmpty()) {
            logger.warn("No explicitTagPaths configured; nothing to subscribe to");
            return List.of();
        }
        List<TagPath> out = new ArrayList<>();
        for (String pathStr : paths) {
            if (pathStr == null || pathStr.trim().isEmpty()) {
                continue;
            }
            try {
                out.add(TagPathParser.parse(pathStr.trim()));
            } catch (Exception parseErr) {
                logger.warn("Invalid tag path '{}': {}", pathStr, parseErr.getMessage());
            }
        }
        return out;
    }

    private List<TagPath> resolveFolderTagPaths(GatewayTagManager tm) {
        String folder = config.getTagFolderPath();
        if (folder == null || folder.trim().isEmpty()) {
            logger.warn("Tag folder path is empty; nothing to subscribe to");
            return List.of();
        }

        TagPath root;
        try {
            root = TagPathParser.parse(folder.trim());
        } catch (Exception e) {
            logger.warn("Invalid folder tag path '{}': {}", folder, e.getMessage());
            return List.of();
        }

        boolean recursive = config.isIncludeSubfolders();
        List<TagPath> out = browseLeafAtomicTags(tm, root, recursive);
        logger.info("Folder selection resolved {} tag(s) from root={} (includeSubfolders={})",
                out.size(), folder.trim(), recursive);
        return out;
    }

    private List<TagPath> resolvePatternTagPaths(GatewayTagManager tm) {
        String patternStr = config.getTagPathPattern();
        if (patternStr == null || patternStr.trim().isEmpty()) {
            logger.warn("Tag path pattern is empty; nothing to subscribe to");
            return List.of();
        }

        Pattern p;
        try {
            p = Pattern.compile(patternStr);
        } catch (PatternSyntaxException e) {
            logger.warn("Invalid regex tagPathPattern='{}': {}", patternStr, e.getDescription());
            return List.of();
        }

        // Pattern mode is evaluated over the FULL tag path string (e.g., "[renewables]Renewables/Site01/MetMast01/WindSpeed_mps").
        //
        // IMPORTANT:
        // Naively browsing ALL providers can be slow (or effectively "hang") on gateways with large tag trees.
        // If the pattern clearly restricts provider(s) at the start (e.g. "^\[(a|b)\]..."), we can browse
        // only those providers for a big performance win.
        List<String> providers = tryExtractProviderFilter(patternStr);
        if (providers == null || providers.isEmpty()) {
            try {
                providers = tm.getTagProviderNames();
            } catch (Exception e) {
                logger.warn("Unable to list tag providers for pattern mode: {}", e.getMessage());
                return List.of();
            }
            logger.info("Pattern selection browsing ALL providers ({}). pattern='{}'", providers.size(), patternStr.trim());
        } else {
            logger.info("Pattern selection browsing filtered providers ({}): {}. pattern='{}'",
                    providers.size(), providers, patternStr.trim());
        }

        // Safety cap to avoid accidental "subscribe to entire gateway" explosions.
        final int MAX_MATCHES = 50_000;
        List<TagPath> out = new ArrayList<>();

        for (String provider : providers) {
            if (provider == null || provider.isBlank()) {
                continue;
            }
            TagPath providerRoot;
            try {
                providerRoot = TagPathParser.parse("[" + provider + "]");
            } catch (Exception ignored) {
                continue;
            }

            long t0 = System.currentTimeMillis();
            List<TagPath> leafs = browseLeafAtomicTags(tm, providerRoot, true);
            long t1 = System.currentTimeMillis();
            if (config.isDebugLogging()) {
                logger.info("Pattern browse provider='{}': leafAtomicTags={} ({}ms)", provider, leafs.size(), (t1 - t0));
            }
            for (TagPath tp : leafs) {
                if (tp == null) continue;
                String s = tp.toString();
                if (p.matcher(s).matches()) {
                    out.add(tp);
                    if (out.size() >= MAX_MATCHES) {
                        logger.warn("Pattern selection reached safety cap ({} matches). Stopping early. pattern={}",
                                MAX_MATCHES, patternStr.trim());
                        return out;
                    }
                }
            }
            if (config.isDebugLogging()) {
                logger.info("Pattern match progress after provider='{}': totalMatches={}", provider, out.size());
            }
        }

        logger.info("Pattern selection resolved {} tag(s) for pattern='{}'", out.size(), patternStr.trim());
        return out;
    }

    /**
     * Best-effort: if the regex begins with a provider constraint like:
     *   ^\[(a|b|c)\]...
     *   ^\[a\]...
     *
     * then return ["a","b","c"] so we only browse those providers.
     *
     * If the pattern doesn't match this shape (or uses complex regex), return null.
     */
    private static List<String> tryExtractProviderFilter(String patternStr) {
        if (patternStr == null) {
            return null;
        }
        String s = patternStr.trim();
        if (s.startsWith("^")) {
            s = s.substring(1);
        }
        if (!s.startsWith("\\[")) {
            return null;
        }
        int end = s.indexOf("\\]");
        if (end < 0) {
            return null;
        }
        String inside = s.substring(2, end); // between \[ and \]
        if (inside.startsWith("(") && inside.endsWith(")") && inside.length() >= 2) {
            inside = inside.substring(1, inside.length() - 1);
        }
        // Only accept a simple alternation of "provider-ish" tokens.
        // If it contains other regex metacharacters, we can't safely infer providers.
        if (!inside.matches("[A-Za-z0-9_\\-\\|]+")) {
            return null;
        }
        String[] parts = inside.split("\\|");
        if (parts.length == 0) {
            return null;
        }
        return Arrays.asList(parts);
    }

    private List<TagPath> browseLeafAtomicTags(GatewayTagManager tm, TagPath root, boolean recursive) {
        if (root == null) {
            return List.of();
        }
        if (tm == null) {
            logger.warn("Cannot browse tags because GatewayTagManager is not initialized (root={})", root.toString());
            return List.of();
        }

        final int PAGE_SIZE = 5000;
        final int MAX_TOTAL = 100_000;
        List<TagPath> out = new ArrayList<>();

        String continuation = null;
        String lastContinuation = null;
        int totalSeen = 0;
        int page = 0;
        long startMs = System.currentTimeMillis();

        do {
            page++;
            BrowseFilter filter = new BrowseFilter()
                    .setRecursive(recursive)
                    .setMaxResults(PAGE_SIZE)
                    .setContinuationPoint(continuation);

            CompletableFuture<Results<NodeDescription>> fut = tm.browseAsync(root, filter);
            Results<NodeDescription> res;
            try {
                // Browsing is local; use requestTimeout as a reasonable ceiling.
                res = fut.get(Math.max(250L, config.getRequestTimeoutMs()), TimeUnit.MILLISECONDS);
            } catch (Exception e) {
                logger.warn("Browse failed for root={} (recursive={}): {}", root.toString(), recursive, e.getMessage());
                return out;
            }

            Collection<NodeDescription> nodes = res != null ? res.getResults() : null;
            int nodeCount = nodes == null ? 0 : nodes.size();
            if (nodes != null) {
                for (NodeDescription nd : nodes) {
                    totalSeen++;
                    if (totalSeen >= MAX_TOTAL) {
                        logger.warn("Browse reached safety cap ({} nodes) for root={}; stopping early", MAX_TOTAL, root.toString());
                        return out;
                    }
                    if (nd == null) continue;
                    if (nd.getObjectType() != TagObjectType.AtomicTag) continue;
                    TagPath fp = nd.getFullPath();
                    if (fp == null) continue;
                    out.add(fp);
                }
            }

            lastContinuation = continuation;
            continuation = (res != null) ? res.getContinuationPoint() : null;

            // Guardrails:
            // Some providers can return empty pages but keep returning continuation points indefinitely.
            // Stop early to avoid infinite loops / runaway browsing.
            if (nodeCount == 0 && continuation != null && !continuation.isBlank()) {
                if (lastContinuation != null && continuation.equals(lastContinuation)) {
                    logger.warn("Browse returned 0 nodes and repeated continuationPoint for root={}; stopping to avoid infinite loop", root.toString());
                    break;
                }
                logger.warn("Browse returned 0 nodes but continuationPoint is set for root={}; stopping to avoid runaway browse", root.toString());
                break;
            }
            if (continuation != null && lastContinuation != null && continuation.equals(lastContinuation)) {
                logger.warn("Browse returned repeated continuationPoint for root={}; stopping to avoid infinite loop", root.toString());
                break;
            }
            if (config.isDebugLogging()) {
                long elapsed = System.currentTimeMillis() - startMs;
                logger.info("Browse progress root={} page={} nodes={} atomic={} totalSeen={} cont={} elapsedMs={}",
                        root.toString(), page, nodeCount, out.size(), totalSeen,
                        (continuation == null ? "null" : (continuation.isBlank() ? "<blank>" : "<set>")),
                        elapsed);
            }
        } while (continuation != null && !continuation.isBlank());

        return out;
    }

    private void unsubscribeAll() {
        try {
            GatewayTagManager tm = this.tagManager;
            if (tm == null || subscribedListeners.isEmpty()) {
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
            lastEmittedValueByTag.clear();
            sdtStateByTag.clear();
            sdtValidationManager.clear();

            if (paths.isEmpty() || listeners.isEmpty()) {
                return;
            }

            tm.unsubscribeAsync(paths, listeners)
                    .whenComplete((ok, err) -> {
                        if (err != null) {
                            logger.warn("Error unsubscribing from tags", err);
                        } else {
                            logger.info("Unsubscribed from {} tags", paths.size());
                        }
                    });
        } catch (Throwable t) {
            logger.warn("Error while unsubscribing tags", t);
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

            acceptTagEvent(new TagEvent(tagPathStr, value, quality, ts), "direct");
        }
    }

    private boolean hasMeaningfulChange(Object last, Object current, double deadband) {
        if (last == null && current == null) {
            return false;
        }
        if (last == null || current == null) {
            return true;
        }
        if (last instanceof Number && current instanceof Number) {
            double a = ((Number) last).doubleValue();
            double b = ((Number) current).doubleValue();
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
        flushBatch(true);
    }

    /**
     * Flush a batch of events.
     *
     * @param allowReconnect if false, do not attempt to reconnect. This is used during shutdown so the gateway
     *                       is not held hostage by connectionTimeoutMs/auth recovery.
     */
    private void flushBatch(boolean allowReconnect) {
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
                if (allowReconnect) {
                    sink.tryEnsureReady();
                }
                if (!sink.isReady()) {
                    return;
                }
            }

            StoreAndForwardBuffer.DrainResult drained = buffer.drain(config.getBatchSize());
            if (drained.events == null || drained.events.isEmpty()) {
                // If we read records but couldn't parse any, the spool contains corrupt bytes.
                // Commit the cursor to skip them; otherwise we'd get stuck forever with "failed reading from spool".
                if (drained.recordsRead > 0 && buffer.isDiskBacked() && drained.nextOffset >= 0) {
                    logger.warn("All {} record(s) read from spool were corrupt; advancing spool cursor to recover.", drained.recordsRead);
                    buffer.commit(drained);
                    lastFlushTime = System.currentTimeMillis();
                }
                return;
            }

            logger.debug("Flushing batch of {} events", drained.events.size());
            long sendStartMs = System.currentTimeMillis();
            long batchBytes = 0L;
            List<OTEvent> sendEvents = new ArrayList<>(drained.events.size());
            for (OTEvent e : drained.events) {
                if (e == null) {
                    continue;
                }
                batchBytes += e.getSerializedSize();
                sendEvents.add(e.toBuilder().setBatchBytesSent(0L).build());
            }
            for (int i = 0; i < sendEvents.size(); i++) {
                OTEvent e = sendEvents.get(i);
                sendEvents.set(i, e.toBuilder().setBatchBytesSent(batchBytes).build());
            }
            boolean success = sink.send(sendEvents);
            if (success) {
                buffer.commit(drained);
                recordSendLatencies(sendStartMs, sendEvents);
                totalBatchesFlushed.incrementAndGet();
                lastFlushTime = System.currentTimeMillis();
            } else {
                // Do NOT commit; records remain for retry. For memory mode, commit is required to remove.
                logger.warn("Failed to send batch of {} events (will retry)", sendEvents.size());
            }
        } catch (Exception e) {
            logger.error("Error flushing batch", e);
        }
    }

    private boolean acceptTagEvent(TagEvent te, String source) {
        if (te == null) {
            return true;
        }

        String tagPathStr = te.getTagPath() != null ? te.getTagPath() : "";
        long nowMs = (te.getTimestamp() != null) ? te.getTimestamp().getTime() : System.currentTimeMillis();
        rolling.recordIncoming(nowMs);
        recordIngestLatency(nowMs, te);

        // When store-and-forward is enabled and we're paused, reject new events rather than drop later.
        buffer.refreshBackpressure();
        if (buffer.isDiskBacked() && buffer.isPaused()) {
            totalEventsDropped.incrementAndGet();
            rolling.recordDropped(nowMs);
            return false;
        }

        // Numeric compression / filtering (applies consistently for BOTH direct subscriptions and HTTP ingest).
        ConfigModel.NumericCompressionPolicy policy = config.getNumericCompressionPolicyForTag(tagPathStr);
        ConfigModel.NumericCompressionMode mode = policy != null ? policy.mode : ConfigModel.NumericCompressionMode.NONE;

        TagEvent toEmit = null;
        Object value = te.getValue();

        if (mode == ConfigModel.NumericCompressionMode.NONE) {
            toEmit = te;
        } else if (value instanceof Number) {
            if (mode == ConfigModel.NumericCompressionMode.DEADBAND) {
                Object last = lastEmittedValueByTag.get(tagPathStr);
                if (!hasMeaningfulChange(last, value, policy.deadband)) {
                    totalEventsFilteredDeadband.incrementAndGet();
                    rolling.recordFilteredDeadband(nowMs);
                    recordPerTag(tagPathStr, mode, false, true, false, false);
                    if (config.isDebugLogging()) {
                        logger.debug("Skipped tag event (deadband) ({}) -> {}", source, tagPathStr);
                    }
                    return true;
                }
                toEmit = te;
            } else if (mode == ConfigModel.NumericCompressionMode.SDT) {
                // Validation buffers record the raw point *before* SDT decision so we can prove reconstruction
                // via interpolation stays within deviation.
                long tMs = te.getTimestamp() != null ? te.getTimestamp().getTime() : nowMs;
                double v = ((Number) te.getValue()).doubleValue();
                sdtValidationManager.recordRawPoint(tagPathStr, tMs, v);

                SdtCompressor.State state = sdtStateByTag.computeIfAbsent(tagPathStr, k -> new SdtCompressor.State());
                SdtCompressor.Outcome out = state.offer(te, policy.sdtDeviation, policy.sdtMaxIntervalMs, policy.sdtMinIntervalMs);
                if (out == null || out.emit == null) {
                    totalEventsFilteredSdt.incrementAndGet();
                    rolling.recordFilteredSdt(nowMs);
                    recordPerTag(tagPathStr, mode, false, false, true, false);
                    return true;
                }
                // Mark the emitted pivot in the validation buffer (by timestamp handles "emit previous point").
                if (out.emit.getTimestamp() != null) {
                    sdtValidationManager.markPivotByTimestamp(tagPathStr, out.emit.getTimestamp().getTime());
                } else {
                    sdtValidationManager.markPivot(tagPathStr);
                }
                if (out.forcedByMaxInterval) {
                    totalEventsForcedBySdtMaxInterval.incrementAndGet();
                    rolling.recordForcedByMaxInterval(nowMs);
                }
                if (out.resetDueToOutOfOrder) {
                    totalSdtOutOfOrderResets.incrementAndGet();
                }
                toEmit = out.emit;
            } else {
                // Defensive: treat unknown modes as NONE.
                toEmit = te;
            }
        } else {
            // Non-numeric values: treat DEADBAND/SDT as "only on change" semantics.
            Object last = lastEmittedValueByTag.get(tagPathStr);
            if (Objects.equals(last, value)) {
                totalEventsFilteredDeadband.incrementAndGet();
                rolling.recordFilteredDeadband(nowMs);
                recordPerTag(tagPathStr, mode, false, true, false, false);
                return true;
            }
            toEmit = te;
        }

        boolean sdtEnabled = mode == ConfigModel.NumericCompressionMode.SDT;
        boolean sdtCompressed = sdtEnabled && toEmit != null && toEmit.isNumeric();
        double sdtCompressionRatio = computeSdtCompressionRatio();
        OTEvent evt = mapper.map(toEmit, sdtCompressed, sdtCompressionRatio, sdtEnabled, 0L);
        boolean ok = buffer.offer(evt);
        if (ok) {
            if (mode != ConfigModel.NumericCompressionMode.NONE) {
                lastEmittedValueByTag.put(tagPathStr, toEmit.getValue());
            }
            if (mode == ConfigModel.NumericCompressionMode.SDT) {
                totalEventsEmittedSdt.incrementAndGet();
            }
            totalEventsReceived.incrementAndGet();
            rolling.recordEmitted(nowMs);
            recordPerTag(tagPathStr, mode, true, false, false, false);
            if (config.isDebugLogging()) {
                logger.debug("Accepted tag event ({}) -> {}", source, toEmit.getTagPath());
            }
        } else {
            totalEventsDropped.incrementAndGet();
            rolling.recordDropped(nowMs);
            logger.warn("Buffer full, dropped event ({}) -> {}", source, toEmit.getTagPath());
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

    private void recordIngestLatency(long eventTimestampMs, TagEvent te) {
        long nowMs = System.currentTimeMillis();
        long tsMs = eventTimestampMs;
        if (te != null && te.getTimestamp() != null) {
            tsMs = te.getTimestamp().getTime();
        }
        if (tsMs <= 0) {
            return;
        }
        long ingestLatencyMs = Math.max(0L, nowMs - tsMs);
        rollingLatency.recordIngest(nowMs, ingestLatencyMs);
    }

    private void recordSendLatencies(long sendStartMs, List<OTEvent> events) {
        if (events == null || events.isEmpty()) {
            return;
        }
        for (OTEvent e : events) {
            if (e == null) {
                continue;
            }
            if (e.getIngestionTimestamp() > 0) {
                long ingestTsMs = e.getIngestionTimestamp() / 1000L;
                long queueLatencyMs = Math.max(0L, sendStartMs - ingestTsMs);
                rollingLatency.recordQueue(sendStartMs, queueLatencyMs);
            }
            if (e.getEventTime() > 0) {
                long eventTsMs = e.getEventTime() / 1000L;
                long endToEndMs = Math.max(0L, sendStartMs - eventTsMs);
                rollingLatency.recordEndToEnd(sendStartMs, endToEndMs);
            }
        }
    }

    private double computeSdtCompressionRatio() {
        long filtered = totalEventsFilteredSdt.get();
        long emitted = totalEventsEmittedSdt.get();
        long denom = filtered + emitted;
        if (denom <= 0L) {
            return 0.0;
        }
        return (double) filtered / (double) denom;
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
        sb.append("Compression Mode (effective): ").append(config.getNumericCompressionModeEffective()).append("\n");
        sb.append("Events Filtered (deadband/on-change): ").append(totalEventsFilteredDeadband.get()).append("\n");
        sb.append("Events Filtered (SDT): ").append(totalEventsFilteredSdt.get()).append("\n");
        sb.append("Events Forced (SDT max interval): ").append(totalEventsForcedBySdtMaxInterval.get()).append("\n");
        sb.append("SDT Out-of-order Resets: ").append(totalSdtOutOfOrderResets.get()).append("\n");
        sb.append("Total Batches Flushed: ").append(totalBatchesFlushed.get()).append("\n");
        sb.append("Direct Subscriptions: ").append(subscribedListeners.size()).append(" tags\n");
        sb.append("Auto-Paused Direct Subscriptions: ").append(autoPausedDirectSubscriptions).append("\n");
        
        if (lastFlushTime > 0) {
            long secondsAgo = (System.currentTimeMillis() - lastFlushTime) / 1000;
            sb.append("Last Flush: ").append(secondsAgo).append(" seconds ago\n");
        } else {
            sb.append("Last Flush: Never\n");
        }

        // Visual compression diagnostics (rolling window)
        sb.append("\n=== Compression (last ").append(COMPRESSION_WINDOW_MINUTES).append(" minutes) ===\n");
        RollingCompressionMetrics.Snapshot snap = rolling.snapshot();
        sb.append("Incoming/min: ").append(sparkline(snap.incomingPerMin)).append("\n");
        sb.append("Emitted/min : ").append(sparkline(snap.emittedPerMin)).append("\n");
        sb.append("Filtered DB : ").append(sparkline(snap.filteredDeadbandPerMin)).append("\n");
        sb.append("Filtered SDT: ").append(sparkline(snap.filteredSdtPerMin)).append("\n");
        sb.append("Forced (SDT maxInterval): ").append(sparkline(snap.forcedByMaxIntervalPerMin)).append("\n");

        long incomingTotal = snap.sum(snap.incomingPerMin);
        long emittedTotal = snap.sum(snap.emittedPerMin);
        long filteredTotal = snap.sum(snap.filteredDeadbandPerMin) + snap.sum(snap.filteredSdtPerMin);
        sb.append("Window totals: incoming=").append(incomingTotal)
                .append(", emitted=").append(emittedTotal)
                .append(", filtered=").append(filteredTotal)
                .append("\n");
        if (incomingTotal > 0) {
            double ratio = (double) emittedTotal / (double) incomingTotal;
            sb.append("Window reduction: ").append(String.format(java.util.Locale.US, "%.1f%%", (1.0 - ratio) * 100.0))
                    .append(" (emitted ").append(String.format(java.util.Locale.US, "%.1f%%", ratio * 100.0)).append(")\n");
        }

        RollingLatencyMetrics.Snapshot lat = rollingLatency.snapshot();
        sb.append("\n=== Latency (last ").append(COMPRESSION_WINDOW_MINUTES).append(" minutes) ===\n");
        sb.append("Ingest latency ms  : avg=").append(String.format(java.util.Locale.US, "%.1f", lat.ingestAvgMs))
                .append(" p95=").append(lat.ingestP95Ms)
                .append(" p99=").append(lat.ingestP99Ms)
                .append(" max=").append(lat.ingestMaxMs).append("\n");
        sb.append("Queue latency ms   : avg=").append(String.format(java.util.Locale.US, "%.1f", lat.queueAvgMs))
                .append(" p95=").append(lat.queueP95Ms)
                .append(" p99=").append(lat.queueP99Ms)
                .append(" max=").append(lat.queueMaxMs).append("\n");
        sb.append("End-to-end ms      : avg=").append(String.format(java.util.Locale.US, "%.1f", lat.endToEndAvgMs))
                .append(" p95=").append(lat.endToEndP95Ms)
                .append(" p99=").append(lat.endToEndP99Ms)
                .append(" max=").append(lat.endToEndMaxMs).append("\n");

        sb.append(renderTopCompressedTags(10));
        
        return sb.toString();
    }

    /**
     * Snapshot of rolling compression diagnostics for HTTP/JSON consumption.
     */
    public CompressionMetricsSnapshot getCompressionMetricsSnapshot() {
        RollingCompressionMetrics.Snapshot snap = rolling.snapshot();
        RollingLatencyMetrics.Snapshot lat = rollingLatency.snapshot();
        CompressionMetricsSnapshot out = new CompressionMetricsSnapshot();
        out.windowMinutes = COMPRESSION_WINDOW_MINUTES;
        out.modeEffective = String.valueOf(config.getNumericCompressionModeEffective());
        out.incomingPerMin = snap.incomingPerMin;
        out.emittedPerMin = snap.emittedPerMin;
        out.filteredDeadbandPerMin = snap.filteredDeadbandPerMin;
        out.filteredSdtPerMin = snap.filteredSdtPerMin;
        out.forcedByMaxIntervalPerMin = snap.forcedByMaxIntervalPerMin;
        out.droppedPerMin = snap.droppedPerMin;
        out.incomingTotal = snap.sum(snap.incomingPerMin);
        out.emittedTotal = snap.sum(snap.emittedPerMin);
        out.filteredDeadbandTotal = snap.sum(snap.filteredDeadbandPerMin);
        out.filteredSdtTotal = snap.sum(snap.filteredSdtPerMin);
        out.forcedByMaxIntervalTotal = snap.sum(snap.forcedByMaxIntervalPerMin);
        out.droppedTotal = snap.sum(snap.droppedPerMin);
        out.sdtCompressionRatio = computeSdtCompressionRatio();
        out.sdtEmittedTotal = totalEventsEmittedSdt.get();

        out.ingestLatencyAvgMs = lat.ingestAvgMs;
        out.ingestLatencyP95Ms = lat.ingestP95Ms;
        out.ingestLatencyP99Ms = lat.ingestP99Ms;
        out.ingestLatencyMaxMs = lat.ingestMaxMs;

        out.queueLatencyAvgMs = lat.queueAvgMs;
        out.queueLatencyP95Ms = lat.queueP95Ms;
        out.queueLatencyP99Ms = lat.queueP99Ms;
        out.queueLatencyMaxMs = lat.queueMaxMs;

        out.endToEndLatencyAvgMs = lat.endToEndAvgMs;
        out.endToEndLatencyP95Ms = lat.endToEndP95Ms;
        out.endToEndLatencyP99Ms = lat.endToEndP99Ms;
        out.endToEndLatencyMaxMs = lat.endToEndMaxMs;
        out.topTags = buildTopCompressedTags(10);
        return out;
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

    private void recordPerTag(String tagPath, ConfigModel.NumericCompressionMode mode, boolean emitted, boolean filteredDeadband, boolean filteredSdt, boolean forcedMaxInterval) {
        if (tagPath == null || tagPath.isBlank()) {
            return;
        }
        // Only track when compression is active; otherwise it's a lot of noise.
        if (mode == null || mode == ConfigModel.NumericCompressionMode.NONE) {
            return;
        }
        TagCompressionStats s = perTagCompression.get(tagPath);
        if (s == null) {
            if (perTagCompression.size() >= COMPRESSION_TAG_STATS_MAX) {
                return;
            }
            TagCompressionStats created = new TagCompressionStats();
            TagCompressionStats existing = perTagCompression.putIfAbsent(tagPath, created);
            s = existing != null ? existing : created;
        }
        if (emitted) s.emitted.incrementAndGet();
        if (filteredDeadband) s.filteredDeadband.incrementAndGet();
        if (filteredSdt) s.filteredSdt.incrementAndGet();
        if (forcedMaxInterval) s.forcedByMaxInterval.incrementAndGet();
    }

    private String renderTopCompressedTags(int limit) {
        List<TagCompressionSummary> top = buildTopCompressedTags(limit);
        if (top.isEmpty()) {
            return "";
        }
        StringBuilder sb = new StringBuilder();
        sb.append("\nTop tags by filtered volume (best-effort; cap ").append(COMPRESSION_TAG_STATS_MAX).append(")\n");
        for (TagCompressionSummary t : top) {
            sb.append("- ").append(t.tagPath)
              .append(" | emitted=").append(t.emitted)
              .append(" filtered=").append(t.filteredTotal)
              .append(" forced=").append(t.forcedByMaxInterval)
              .append(" (filtered=").append(String.format(java.util.Locale.US, "%.1f%%", t.filteredPct * 100.0)).append(")\n");
        }
        return sb.toString();
    }

    private List<TagCompressionSummary> buildTopCompressedTags(int limit) {
        if (limit <= 0) {
            return java.util.Collections.emptyList();
        }
        List<TagCompressionSummary> out = new ArrayList<>();
        for (Map.Entry<String, TagCompressionStats> e : perTagCompression.entrySet()) {
            String tag = e.getKey();
            TagCompressionStats s = e.getValue();
            if (s == null) continue;
            long emitted = s.emitted.get();
            long filteredDb = s.filteredDeadband.get();
            long filteredSdt = s.filteredSdt.get();
            long forced = s.forcedByMaxInterval.get();
            long filtered = filteredDb + filteredSdt;
            long incoming = emitted + filtered;
            if (incoming <= 0) continue;
            double filteredPct = (double) filtered / (double) incoming;
            out.add(new TagCompressionSummary(tag, emitted, filteredDb, filteredSdt, forced, filteredPct));
        }
        out.sort((a, b) -> {
            int c = Long.compare(b.filteredTotal, a.filteredTotal);
            if (c != 0) return c;
            return Double.compare(b.filteredPct, a.filteredPct);
        });
        if (out.size() > limit) {
            return out.subList(0, limit);
        }
        return out;
    }

    private static String sparkline(long[] values) {
        if (values == null || values.length == 0) {
            return "";
        }
        long max = 0;
        for (long v : values) {
            if (v > max) max = v;
        }
        final char[] blocks = new char[] {'▁','▂','▃','▄','▅','▆','▇','█'};
        StringBuilder sb = new StringBuilder(values.length);
        for (long v : values) {
            int idx = 0;
            if (max > 0) {
                idx = (int) Math.round(((double) v / (double) max) * (blocks.length - 1));
                if (idx < 0) idx = 0;
                if (idx >= blocks.length) idx = blocks.length - 1;
            }
            sb.append(blocks[idx]);
        }
        sb.append("  max=").append(max);
        return sb.toString();
    }

    private static final class TagCompressionStats {
        final AtomicLong emitted = new AtomicLong(0);
        final AtomicLong filteredDeadband = new AtomicLong(0);
        final AtomicLong filteredSdt = new AtomicLong(0);
        final AtomicLong forcedByMaxInterval = new AtomicLong(0);
    }

    public static final class TagCompressionSummary {
        public final String tagPath;
        public final long emitted;
        public final long filteredDeadband;
        public final long filteredSdt;
        public final long filteredTotal;
        public final long forcedByMaxInterval;
        public final double filteredPct;

        TagCompressionSummary(String tagPath, long emitted, long filteredDeadband, long filteredSdt, long forcedByMaxInterval, double filteredPct) {
            this.tagPath = tagPath;
            this.emitted = emitted;
            this.filteredDeadband = filteredDeadband;
            this.filteredSdt = filteredSdt;
            this.filteredTotal = filteredDeadband + filteredSdt;
            this.forcedByMaxInterval = forcedByMaxInterval;
            this.filteredPct = filteredPct;
        }
    }

    public static final class CompressionMetricsSnapshot {
        public int windowMinutes;
        public String modeEffective;

        public long[] incomingPerMin;
        public long[] emittedPerMin;
        public long[] filteredDeadbandPerMin;
        public long[] filteredSdtPerMin;
        public long[] forcedByMaxIntervalPerMin;
        public long[] droppedPerMin;

        public long incomingTotal;
        public long emittedTotal;
        public long filteredDeadbandTotal;
        public long filteredSdtTotal;
        public long forcedByMaxIntervalTotal;
        public long droppedTotal;
        public long sdtEmittedTotal;
        public double sdtCompressionRatio;

        public double ingestLatencyAvgMs;
        public long ingestLatencyP95Ms;
        public long ingestLatencyP99Ms;
        public long ingestLatencyMaxMs;

        public double queueLatencyAvgMs;
        public long queueLatencyP95Ms;
        public long queueLatencyP99Ms;
        public long queueLatencyMaxMs;

        public double endToEndLatencyAvgMs;
        public long endToEndLatencyP95Ms;
        public long endToEndLatencyP99Ms;
        public long endToEndLatencyMaxMs;

        public List<TagCompressionSummary> topTags;
    }

    private static final class RollingLatencyMetrics {
        private final LatencyReservoir ingestReservoir = new LatencyReservoir(4096);
        private final LatencyReservoir queueReservoir = new LatencyReservoir(4096);
        private final LatencyReservoir endToEndReservoir = new LatencyReservoir(4096);

        RollingLatencyMetrics(int windowMinutes) {
            // Currently reservoir-based only; keep ctor signature aligned with compression window config.
        }

        void recordIngest(long nowMs, long latencyMs) {
            ingestReservoir.record(nowMs, latencyMs);
        }

        void recordQueue(long nowMs, long latencyMs) {
            queueReservoir.record(nowMs, latencyMs);
        }

        void recordEndToEnd(long nowMs, long latencyMs) {
            endToEndReservoir.record(nowMs, latencyMs);
        }

        Snapshot snapshot() {
            LatencyReservoir.Stats in = ingestReservoir.snapshot();
            LatencyReservoir.Stats q = queueReservoir.snapshot();
            LatencyReservoir.Stats e2e = endToEndReservoir.snapshot();
            return new Snapshot(
                    in.avg, in.p95, in.p99, in.max,
                    q.avg, q.p95, q.p99, q.max,
                    e2e.avg, e2e.p95, e2e.p99, e2e.max
            );
        }

        static final class Snapshot {
            final double ingestAvgMs;
            final long ingestP95Ms;
            final long ingestP99Ms;
            final long ingestMaxMs;

            final double queueAvgMs;
            final long queueP95Ms;
            final long queueP99Ms;
            final long queueMaxMs;

            final double endToEndAvgMs;
            final long endToEndP95Ms;
            final long endToEndP99Ms;
            final long endToEndMaxMs;

            Snapshot(
                    double ingestAvgMs, long ingestP95Ms, long ingestP99Ms, long ingestMaxMs,
                    double queueAvgMs, long queueP95Ms, long queueP99Ms, long queueMaxMs,
                    double endToEndAvgMs, long endToEndP95Ms, long endToEndP99Ms, long endToEndMaxMs
            ) {
                this.ingestAvgMs = ingestAvgMs;
                this.ingestP95Ms = ingestP95Ms;
                this.ingestP99Ms = ingestP99Ms;
                this.ingestMaxMs = ingestMaxMs;
                this.queueAvgMs = queueAvgMs;
                this.queueP95Ms = queueP95Ms;
                this.queueP99Ms = queueP99Ms;
                this.queueMaxMs = queueMaxMs;
                this.endToEndAvgMs = endToEndAvgMs;
                this.endToEndP95Ms = endToEndP95Ms;
                this.endToEndP99Ms = endToEndP99Ms;
                this.endToEndMaxMs = endToEndMaxMs;
            }
        }
    }

    private static final class LatencyReservoir {
        private static final class Sample {
            final long tsMs;
            final long latencyMs;
            Sample(long tsMs, long latencyMs) {
                this.tsMs = tsMs;
                this.latencyMs = latencyMs;
            }
        }

        static final class Stats {
            final double avg;
            final long p95;
            final long p99;
            final long max;
            Stats(double avg, long p95, long p99, long max) {
                this.avg = avg;
                this.p95 = p95;
                this.p99 = p99;
                this.max = max;
            }
        }

        private final int maxSamples;
        private final java.util.ArrayDeque<Sample> samples;

        LatencyReservoir(int maxSamples) {
            this.maxSamples = Math.max(256, maxSamples);
            this.samples = new java.util.ArrayDeque<>(this.maxSamples);
        }

        synchronized void record(long nowMs, long latencyMs) {
            long safeLatency = Math.max(0L, latencyMs);
            if (samples.size() >= maxSamples) {
                samples.removeFirst();
            }
            samples.addLast(new Sample(nowMs, safeLatency));
        }

        synchronized Stats snapshot() {
            if (samples.isEmpty()) {
                return new Stats(0.0, 0L, 0L, 0L);
            }
            long[] values = new long[samples.size()];
            long sum = 0L;
            long max = 0L;
            int i = 0;
            for (Sample s : samples) {
                long v = s.latencyMs;
                values[i++] = v;
                sum += v;
                if (v > max) {
                    max = v;
                }
            }
            java.util.Arrays.sort(values);
            double avg = (double) sum / (double) values.length;
            long p95 = percentile(values, 0.95);
            long p99 = percentile(values, 0.99);
            return new Stats(avg, p95, p99, max);
        }

        private static long percentile(long[] values, double q) {
            if (values == null || values.length == 0) {
                return 0L;
            }
            int idx = (int) Math.ceil(q * values.length) - 1;
            if (idx < 0) {
                idx = 0;
            }
            if (idx >= values.length) {
                idx = values.length - 1;
            }
            return values[idx];
        }
    }

    private static final class RollingCompressionMetrics {
        private final int windowMinutes;
        private final long[] minuteKeys; // epoch minute for each slot
        private final long[] incoming;
        private final long[] emitted;
        private final long[] filteredDeadband;
        private final long[] filteredSdt;
        private final long[] forcedByMaxInterval;
        private final long[] dropped;

        RollingCompressionMetrics(int windowMinutes) {
            this.windowMinutes = Math.max(1, windowMinutes);
            this.minuteKeys = new long[this.windowMinutes];
            this.incoming = new long[this.windowMinutes];
            this.emitted = new long[this.windowMinutes];
            this.filteredDeadband = new long[this.windowMinutes];
            this.filteredSdt = new long[this.windowMinutes];
            this.forcedByMaxInterval = new long[this.windowMinutes];
            this.dropped = new long[this.windowMinutes];
        }

        void recordIncoming(long nowMs) { add(nowMs, incoming, 1); }
        void recordEmitted(long nowMs) { add(nowMs, emitted, 1); }
        void recordFilteredDeadband(long nowMs) { add(nowMs, filteredDeadband, 1); }
        void recordFilteredSdt(long nowMs) { add(nowMs, filteredSdt, 1); }
        void recordForcedByMaxInterval(long nowMs) { add(nowMs, forcedByMaxInterval, 1); }
        void recordDropped(long nowMs) { add(nowMs, dropped, 1); }

        private synchronized void add(long nowMs, long[] arr, long delta) {
            long minute = nowMs / 60000L;
            int idx = (int) (minute % windowMinutes);
            if (minuteKeys[idx] != minute) {
                // slot rollover
                minuteKeys[idx] = minute;
                incoming[idx] = 0;
                emitted[idx] = 0;
                filteredDeadband[idx] = 0;
                filteredSdt[idx] = 0;
                forcedByMaxInterval[idx] = 0;
                dropped[idx] = 0;
            }
            arr[idx] += delta;
        }

        Snapshot snapshot() {
            return snapshotAt(System.currentTimeMillis());
        }

        synchronized Snapshot snapshotAt(long nowMs) {
            long nowMin = nowMs / 60000L;
            long[] in = new long[windowMinutes];
            long[] em = new long[windowMinutes];
            long[] fd = new long[windowMinutes];
            long[] fs = new long[windowMinutes];
            long[] fm = new long[windowMinutes];
            long[] dr = new long[windowMinutes];

            // Return ordered oldest -> newest
            for (int i = 0; i < windowMinutes; i++) {
                long minute = nowMin - (windowMinutes - 1 - i);
                int idx = (int) (minute % windowMinutes);
                if (minuteKeys[idx] == minute) {
                    in[i] = incoming[idx];
                    em[i] = emitted[idx];
                    fd[i] = filteredDeadband[idx];
                    fs[i] = filteredSdt[idx];
                    fm[i] = forcedByMaxInterval[idx];
                    dr[i] = dropped[idx];
                } else {
                    in[i] = 0;
                    em[i] = 0;
                    fd[i] = 0;
                    fs[i] = 0;
                    fm[i] = 0;
                    dr[i] = 0;
                }
            }
            return new Snapshot(in, em, fd, fs, fm, dr);
        }

        static final class Snapshot {
            final long[] incomingPerMin;
            final long[] emittedPerMin;
            final long[] filteredDeadbandPerMin;
            final long[] filteredSdtPerMin;
            final long[] forcedByMaxIntervalPerMin;
            final long[] droppedPerMin;

            Snapshot(long[] incomingPerMin, long[] emittedPerMin, long[] filteredDeadbandPerMin, long[] filteredSdtPerMin, long[] forcedByMaxIntervalPerMin, long[] droppedPerMin) {
                this.incomingPerMin = incomingPerMin;
                this.emittedPerMin = emittedPerMin;
                this.filteredDeadbandPerMin = filteredDeadbandPerMin;
                this.filteredSdtPerMin = filteredSdtPerMin;
                this.forcedByMaxIntervalPerMin = forcedByMaxIntervalPerMin;
                this.droppedPerMin = droppedPerMin;
            }

            long sum(long[] v) {
                long s = 0;
                if (v == null) return 0;
                for (long x : v) s += x;
                return s;
            }
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

