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
            lastSentValueByTag.clear();

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

        // Optional filtering: onlyOnChange + numeric deadband.
        // Apply consistently for BOTH direct subscriptions and HTTP ingest.
        if (config.isOnlyOnChange()) {
            String tagPathStr = te.getTagPath() != null ? te.getTagPath() : "";
            Object last = lastSentValueByTag.get(tagPathStr);
            if (!hasMeaningfulChange(last, te.getValue())) {
                if (config.isDebugLogging()) {
                    logger.debug("Skipped tag event (onlyOnChange) ({}) -> {}", source, tagPathStr);
                }
                return true; // not an error; just filtered out
            }
        }

        OTEvent evt = mapper.map(te);
        boolean ok = buffer.offer(evt);
        if (ok) {
            if (config.isOnlyOnChange()) {
                String tagPathStr = te.getTagPath() != null ? te.getTagPath() : "";
                lastSentValueByTag.put(tagPathStr, te.getValue());
            }
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

