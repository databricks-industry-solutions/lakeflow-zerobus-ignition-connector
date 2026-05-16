package com.example.ignition.zerobus;

import java.io.Serializable;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;

/**
 * ConfigModel - POJO for module configuration settings.
 * 
 * Holds all user-configurable parameters for the Zerobus integration:
 * - Databricks connection details (endpoint, credentials)
 * - Target Unity Catalog table
 * - Tag selection criteria
 * - Batching and performance settings
 * - Enable/disable flag
 */
public class ConfigModel implements Serializable {
    
    private static final long serialVersionUID = 1L;
    
    // === Databricks Connection Settings ===
    
    /** Databricks workspace URL (e.g., https://my-workspace.cloud.databricks.com) */
    private String workspaceUrl = "";
    
    /** Zerobus Ingest endpoint URL */
    private String zerobusEndpoint = "";
    
    /** OAuth2 client ID for authentication */
    private String oauthClientId = "";
    
    /** OAuth2 client secret for authentication */
    private String oauthClientSecret = "";

    // === Sink Selection Settings ===

    /**
     * Sink mode selector.
     * - zerobus: send OT events via Zerobus ingest API
     * - lakebase: write OT events to PostgreSQL (Lakebase)
     */
    public enum SinkMode {
        zerobus,
        lakebase
    }

    /** Active sink mode. */
    private SinkMode sinkMode = SinkMode.zerobus;

    /** Feature flags for sink activation (kept for backward compatibility with existing config payloads). */
    private boolean enableZerobusSink = true;
    private boolean enablePostgresSink = false;

    // === PostgreSQL / Lakebase Settings ===

    /** PostgreSQL host (for Lakebase mode). */
    private String postgresHost = "";

    /** PostgreSQL port (for Lakebase mode). */
    private int postgresPort = 5432;

    /** PostgreSQL database name (for Lakebase mode). */
    private String postgresDatabase = "";

    /** PostgreSQL username (for Lakebase mode). */
    private String postgresUser = "";

    /** PostgreSQL password (for Lakebase mode). */
    private String postgresPassword = "";

    /** PostgreSQL fully-qualified target table (schema.table) for OT inserts. */
    private String postgresTable = "raw_tags";

    /** PostgreSQL connection pool size. */
    private int postgresPoolSize = 5;
    
    // === Unity Catalog Settings ===
    
    /** Target Unity Catalog table (format: catalog.schema.table) */
    private String targetTable = "";
    
    /** Catalog name */
    private String catalogName = "";
    
    /** Schema name */
    private String schemaName = "";
    
    /** Table name */
    private String tableName = "";
    
    // === Tag Selection Settings ===
    
    /**
     * When true, the module subscribes directly to tags using Gateway TagManager.
     * When false, the module will NOT subscribe to tags and will ingest only via HTTP endpoints
     * (/system/zerobus/ingest and /ingest/batch), e.g. from Event Streams or scripts.
     */
    private boolean enableDirectSubscriptions = true;

    /** Tag selection mode: "folder", "pattern", "explicit" */
    private String tagSelectionMode = "explicit";
    
    /** Tag folder path for folder mode (e.g., "[default]Tag Group/") */
    private String tagFolderPath = "";
    
    /** Tag path pattern for pattern mode (supports wildcards) */
    private String tagPathPattern = "";
    
    /** Explicit list of tag paths for explicit mode */
    private List<String> explicitTagPaths = new ArrayList<>();
    
    /** Include subfolders when using folder mode */
    private boolean includeSubfolders = true;
    
    // === Batching & Performance Settings ===
    
    /** Maximum number of events per batch */
    private int batchSize = 500;
    
    /** Maximum time to wait before flushing batch (milliseconds) */
    private long batchFlushIntervalMs = 2000;
    
    /** Maximum events in memory queue before applying backpressure */
    private int maxQueueSize = 10000;
    
    /** Maximum events per second (rate limiting) */
    private int maxEventsPerSecond = 1000;

    // === Store-and-Forward (disk spool) ===

    /**
     * When enabled, events are buffered to disk when the sink is unavailable (OT-style store-and-forward).
     * This allows surviving transient network / auth outages without data loss (at-least-once).
     */
    private boolean enableStoreAndForward = false;

    /** Spool directory (absolute or relative to Ignition install dir). */
    private String spoolDirectory = "data/zerobus-spool";

    /** Maximum spool backlog size in bytes before rejecting new events. */
    private long spoolMaxBytes = 1024L * 1024 * 1024; // 1 GiB default

    /** High watermark percentage (0-1). If backlog exceeds this, apply backpressure (pause subscriptions). */
    private double spoolHighWatermarkPct = 0.85;

    /** Low watermark percentage (0-1). If backlog drops below this, resume subscriptions. */
    private double spoolLowWatermarkPct = 0.70;

    /** Maximum bytes to read from spool per flush attempt (safety cap). */
    private long spoolReadMaxBytes = 2L * 1024 * 1024; // 2 MiB
    
    // === Reliability Settings ===
    
    /** Number of retry attempts for failed sends */
    private int maxRetries = 3;
    
    /** Initial retry backoff delay (milliseconds) */
    private long retryBackoffMs = 1000;
    
    /** Connection timeout (milliseconds) */
    private long connectionTimeoutMs = 30000;
    
    /** Request timeout (milliseconds) */
    private long requestTimeoutMs = 60000;
    
    // === Data Mapping Settings ===
    
    /** Source system identifier (for source_system field) */
    private String sourceSystemId = "ignition-gateway";
    
    /** Include tag quality in events */
    private boolean includeQuality = true;

    /**
     * Numeric compression mode for edge-side reduction.
     *
     * Backward compatibility:
     * - If unset (null), the effective mode is derived from {@link #onlyOnChange}:
     *   - onlyOnChange=true  -> DEADBAND
     *   - onlyOnChange=false -> NONE
     */
    public enum NumericCompressionMode {
        NONE,
        DEADBAND,
        SDT
    }

    /**
     * Numeric compression mode.
     *
     * IMPORTANT: keep nullable so we can detect "unset" and preserve backward compatibility
     * with configs that only set {@link #onlyOnChange}.
     */
    private NumericCompressionMode numericCompressionMode = null;

    /**
     * Legacy flag (deprecated): only send events when value changes.
     * Prefer {@link #numericCompressionMode} going forward.
     */
    private boolean onlyOnChange = false;

    /** Numeric deadband for change detection (absolute difference). Used when mode = DEADBAND. */
    private double numericDeadband = 0.0;

    /** SDT deviation (engineering units). Used when mode = SDT. Must be > 0. */
    private double numericSdtDeviation = 0.0;

    /**
     * SDT maximum interval between emitted points (ms). Used when mode = SDT.
     * 0 disables max-interval forcing.
     */
    private long numericSdtMaxIntervalMs = 0L;

    /**
     * SDT minimum interval between emitted points (ms). Used when mode = SDT.
     * 0 disables min-interval suppression.
     *
     * This is analogous to PI "CompMin": suppress points that arrive too soon after the last emitted point.
     */
    private long numericSdtMinIntervalMs = 0L;

    /**
     * Optional per-tag deadband rules (applies only to numeric values).
     * The first matching rule wins; if none match, {@link #numericDeadband} is used.
     *
     * This allows per-signal tuning (e.g., temperature vs pressure vs flow) without changing tag groups.
     */
    private List<DeadbandRule> numericDeadbandRules = new ArrayList<>();

    /**
     * Per-tag numeric compression rules (first match wins).
     * Prefer this over {@link #numericDeadbandRules} for new configurations.
     */
    private List<NumericCompressionRule> numericCompressionRules = new ArrayList<>();

    // === Module Control ===
    
    /** Enable/disable the entire module */
    private boolean enabled = false;
    
    /** Enable verbose debug logging */
    private boolean debugLogging = false;
    
    // === Constructors ===
    
    public ConfigModel() {
        // Default constructor
    }
    
    // === Getters and Setters ===
    
    public String getWorkspaceUrl() {
        return workspaceUrl;
    }
    
    public void setWorkspaceUrl(String workspaceUrl) {
        this.workspaceUrl = workspaceUrl;
    }
    
    public String getZerobusEndpoint() {
        return zerobusEndpoint;
    }
    
    public void setZerobusEndpoint(String zerobusEndpoint) {
        this.zerobusEndpoint = zerobusEndpoint;
    }
    
    public String getOauthClientId() {
        return oauthClientId;
    }
    
    public void setOauthClientId(String oauthClientId) {
        this.oauthClientId = oauthClientId;
    }
    
    public String getOauthClientSecret() {
        return oauthClientSecret;
    }
    
    public void setOauthClientSecret(String oauthClientSecret) {
        this.oauthClientSecret = oauthClientSecret;
    }

    public SinkMode getSinkMode() {
        return sinkMode;
    }

    public void setSinkMode(SinkMode sinkMode) {
        this.sinkMode = (sinkMode == null) ? SinkMode.zerobus : sinkMode;
    }

    public boolean isEnableZerobusSink() {
        return enableZerobusSink;
    }

    public void setEnableZerobusSink(boolean enableZerobusSink) {
        this.enableZerobusSink = enableZerobusSink;
    }

    public boolean isEnablePostgresSink() {
        return enablePostgresSink;
    }

    public void setEnablePostgresSink(boolean enablePostgresSink) {
        this.enablePostgresSink = enablePostgresSink;
    }

    public String getPostgresHost() {
        return postgresHost;
    }

    public void setPostgresHost(String postgresHost) {
        this.postgresHost = postgresHost;
    }

    public int getPostgresPort() {
        return postgresPort;
    }

    public void setPostgresPort(int postgresPort) {
        this.postgresPort = postgresPort;
    }

    public String getPostgresDatabase() {
        return postgresDatabase;
    }

    public void setPostgresDatabase(String postgresDatabase) {
        this.postgresDatabase = postgresDatabase;
    }

    public String getPostgresUser() {
        return postgresUser;
    }

    public void setPostgresUser(String postgresUser) {
        this.postgresUser = postgresUser;
    }

    public String getPostgresPassword() {
        return postgresPassword;
    }

    public void setPostgresPassword(String postgresPassword) {
        this.postgresPassword = postgresPassword;
    }

    public String getPostgresTable() {
        return postgresTable;
    }

    public void setPostgresTable(String postgresTable) {
        this.postgresTable = postgresTable;
    }

    public int getPostgresPoolSize() {
        return postgresPoolSize;
    }

    public void setPostgresPoolSize(int postgresPoolSize) {
        this.postgresPoolSize = postgresPoolSize;
    }
    
    public String getTargetTable() {
        return targetTable;
    }
    
    public void setTargetTable(String targetTable) {
        this.targetTable = targetTable;
        parseTableName();
    }
    
    public String getCatalogName() {
        return catalogName;
    }
    
    public String getSchemaName() {
        return schemaName;
    }
    
    public String getTableName() {
        return tableName;
    }
    
    public String getTagSelectionMode() {
        return tagSelectionMode;
    }
    
    public void setTagSelectionMode(String tagSelectionMode) {
        this.tagSelectionMode = tagSelectionMode;
    }

    public boolean isEnableDirectSubscriptions() {
        return enableDirectSubscriptions;
    }

    public void setEnableDirectSubscriptions(boolean enableDirectSubscriptions) {
        this.enableDirectSubscriptions = enableDirectSubscriptions;
    }
    
    public String getTagFolderPath() {
        return tagFolderPath;
    }
    
    public void setTagFolderPath(String tagFolderPath) {
        this.tagFolderPath = tagFolderPath;
    }
    
    public String getTagPathPattern() {
        return tagPathPattern;
    }
    
    public void setTagPathPattern(String tagPathPattern) {
        this.tagPathPattern = tagPathPattern;
    }
    
    public List<String> getExplicitTagPaths() {
        return explicitTagPaths;
    }
    
    public void setExplicitTagPaths(List<String> explicitTagPaths) {
        this.explicitTagPaths = explicitTagPaths;
    }
    
    public boolean isIncludeSubfolders() {
        return includeSubfolders;
    }
    
    public void setIncludeSubfolders(boolean includeSubfolders) {
        this.includeSubfolders = includeSubfolders;
    }
    
    public int getBatchSize() {
        return batchSize;
    }
    
    public void setBatchSize(int batchSize) {
        this.batchSize = batchSize;
    }
    
    public long getBatchFlushIntervalMs() {
        return batchFlushIntervalMs;
    }
    
    public void setBatchFlushIntervalMs(long batchFlushIntervalMs) {
        this.batchFlushIntervalMs = batchFlushIntervalMs;
    }
    
    public int getMaxQueueSize() {
        return maxQueueSize;
    }
    
    public void setMaxQueueSize(int maxQueueSize) {
        this.maxQueueSize = maxQueueSize;
    }
    
    public int getMaxEventsPerSecond() {
        return maxEventsPerSecond;
    }
    
    public void setMaxEventsPerSecond(int maxEventsPerSecond) {
        this.maxEventsPerSecond = maxEventsPerSecond;
    }

    public boolean isEnableStoreAndForward() {
        return enableStoreAndForward;
    }

    public void setEnableStoreAndForward(boolean enableStoreAndForward) {
        this.enableStoreAndForward = enableStoreAndForward;
    }

    public String getSpoolDirectory() {
        return spoolDirectory;
    }

    public void setSpoolDirectory(String spoolDirectory) {
        this.spoolDirectory = spoolDirectory;
    }

    public long getSpoolMaxBytes() {
        return spoolMaxBytes;
    }

    public void setSpoolMaxBytes(long spoolMaxBytes) {
        this.spoolMaxBytes = spoolMaxBytes;
    }

    public double getSpoolHighWatermarkPct() {
        return spoolHighWatermarkPct;
    }

    public void setSpoolHighWatermarkPct(double spoolHighWatermarkPct) {
        this.spoolHighWatermarkPct = spoolHighWatermarkPct;
    }

    public double getSpoolLowWatermarkPct() {
        return spoolLowWatermarkPct;
    }

    public void setSpoolLowWatermarkPct(double spoolLowWatermarkPct) {
        this.spoolLowWatermarkPct = spoolLowWatermarkPct;
    }

    public long getSpoolReadMaxBytes() {
        return spoolReadMaxBytes;
    }

    public void setSpoolReadMaxBytes(long spoolReadMaxBytes) {
        this.spoolReadMaxBytes = spoolReadMaxBytes;
    }
    
    public int getMaxRetries() {
        return maxRetries;
    }
    
    public void setMaxRetries(int maxRetries) {
        this.maxRetries = maxRetries;
    }
    
    public long getRetryBackoffMs() {
        return retryBackoffMs;
    }
    
    public void setRetryBackoffMs(long retryBackoffMs) {
        this.retryBackoffMs = retryBackoffMs;
    }
    
    public long getConnectionTimeoutMs() {
        return connectionTimeoutMs;
    }
    
    public void setConnectionTimeoutMs(long connectionTimeoutMs) {
        this.connectionTimeoutMs = connectionTimeoutMs;
    }
    
    public long getRequestTimeoutMs() {
        return requestTimeoutMs;
    }
    
    public void setRequestTimeoutMs(long requestTimeoutMs) {
        this.requestTimeoutMs = requestTimeoutMs;
    }
    
    public String getSourceSystemId() {
        return sourceSystemId;
    }
    
    public void setSourceSystemId(String sourceSystemId) {
        this.sourceSystemId = sourceSystemId;
    }
    
    public boolean isIncludeQuality() {
        return includeQuality;
    }
    
    public void setIncludeQuality(boolean includeQuality) {
        this.includeQuality = includeQuality;
    }

    public NumericCompressionMode getNumericCompressionMode() {
        return numericCompressionMode;
    }

    public void setNumericCompressionMode(NumericCompressionMode numericCompressionMode) {
        this.numericCompressionMode = numericCompressionMode;
    }

    /**
     * Effective numeric compression mode with backward compatibility for older configs.
     */
    public NumericCompressionMode getNumericCompressionModeEffective() {
        if (numericCompressionMode != null) {
            return numericCompressionMode;
        }
        // Legacy behavior: onlyOnChange implies deadband filtering.
        return onlyOnChange ? NumericCompressionMode.DEADBAND : NumericCompressionMode.NONE;
    }
    
    public boolean isOnlyOnChange() {
        return onlyOnChange;
    }
    
    public void setOnlyOnChange(boolean onlyOnChange) {
        this.onlyOnChange = onlyOnChange;
    }
    
    public double getNumericDeadband() {
        return numericDeadband;
    }
    
    public void setNumericDeadband(double numericDeadband) {
        this.numericDeadband = numericDeadband;
    }

    public double getNumericSdtDeviation() {
        return numericSdtDeviation;
    }

    public void setNumericSdtDeviation(double numericSdtDeviation) {
        this.numericSdtDeviation = numericSdtDeviation;
    }

    public long getNumericSdtMaxIntervalMs() {
        return numericSdtMaxIntervalMs;
    }

    public void setNumericSdtMaxIntervalMs(long numericSdtMaxIntervalMs) {
        this.numericSdtMaxIntervalMs = numericSdtMaxIntervalMs;
    }

    public long getNumericSdtMinIntervalMs() {
        return numericSdtMinIntervalMs;
    }

    public void setNumericSdtMinIntervalMs(long numericSdtMinIntervalMs) {
        this.numericSdtMinIntervalMs = numericSdtMinIntervalMs;
    }

    public List<NumericCompressionRule> getNumericCompressionRules() {
        return numericCompressionRules;
    }

    public void setNumericCompressionRules(List<NumericCompressionRule> numericCompressionRules) {
        this.numericCompressionRules = (numericCompressionRules == null) ? new ArrayList<>() : numericCompressionRules;
    }

    /**
     * Effective numeric compression policy for a given tag path.
     * First matching rule wins; otherwise uses global defaults.
     */
    public NumericCompressionPolicy getNumericCompressionPolicyForTag(String tagPath) {
        String tp = (tagPath == null) ? "" : tagPath;

        // Start with global defaults.
        NumericCompressionMode mode = getNumericCompressionModeEffective();
        NumericCompressionPolicy base = new NumericCompressionPolicy(
                mode,
                numericDeadband,
                numericSdtDeviation,
                numericSdtMaxIntervalMs,
                numericSdtMinIntervalMs
        );

        // New rules (preferred).
        if (numericCompressionRules != null) {
            for (NumericCompressionRule r : numericCompressionRules) {
                if (r != null && r.matches(tp)) {
                    return r.toPolicyOrFallback(base);
                }
            }
        }

        // Backward-compatible per-tag deadband rules (only meaningful when using deadband mode).
        if (base.mode == NumericCompressionMode.DEADBAND) {
            double db = getNumericDeadbandForTag(tp);
            return new NumericCompressionPolicy(
                    NumericCompressionMode.DEADBAND,
                    db,
                    base.sdtDeviation,
                    base.sdtMaxIntervalMs,
                    base.sdtMinIntervalMs
            );
        }

        return base;
    }

    public List<DeadbandRule> getNumericDeadbandRules() {
        return numericDeadbandRules;
    }

    public void setNumericDeadbandRules(List<DeadbandRule> numericDeadbandRules) {
        this.numericDeadbandRules = (numericDeadbandRules == null) ? new ArrayList<>() : numericDeadbandRules;
    }

    /**
     * Resolve the numeric deadband to apply for a specific tag path.
     * Uses the first matching rule in {@link #numericDeadbandRules}; otherwise falls back to {@link #numericDeadband}.
     */
    public double getNumericDeadbandForTag(String tagPath) {
        String tp = (tagPath == null) ? "" : tagPath;
        if (numericDeadbandRules != null) {
            for (DeadbandRule r : numericDeadbandRules) {
                if (r != null && r.matches(tp)) {
                    return r.getDeadband();
                }
            }
        }
        return numericDeadband;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }
    public boolean isDebugLogging() {
        return debugLogging;
    }
    
    public void setDebugLogging(boolean debugLogging) {
        this.debugLogging = debugLogging;
    }
    
    // === Helper Methods ===
    
    /**
     * Parse the targetTable string into catalog, schema, and table components.
     * Expected format: "catalog.schema.table"
     */
    private void parseTableName() {
        if (targetTable != null && !targetTable.isEmpty()) {
            String[] parts = targetTable.split("\\.");
            if (parts.length == 3) {
                this.catalogName = parts[0];
                this.schemaName = parts[1];
                this.tableName = parts[2];
            }
        }
    }
    
    /**
     * Validate the configuration.
     * 
     * @return List of validation error messages (empty if valid)
     */
    public List<String> validate() {
        List<String> errors = new ArrayList<>();

        // Auto-correct common path issues (especially in Docker restores) before validating.
        // This mutates the in-memory ConfigModel and is intentionally best-effort.
        autoCorrectPaths();

        // Gson deserialization sets fields directly (it does not call setters),
        // so catalog/schema/table may be empty even when targetTable is present.
        // Ensure we derive catalog/schema/table from targetTable before validating.
        if ((catalogName == null || catalogName.isEmpty()
                || schemaName == null || schemaName.isEmpty()
                || tableName == null || tableName.isEmpty())
                && targetTable != null && !targetTable.isEmpty()) {
            parseTableName();
        }
        
        // When the module is disabled, allow saving partial configs so users can incrementally configure.
        // When enabled, enforce required fields.
        if (enabled) {
            SinkMode effectiveSinkMode = (sinkMode == null) ? SinkMode.zerobus : sinkMode;
            if (effectiveSinkMode == SinkMode.lakebase || enablePostgresSink) {
                if (postgresHost == null || postgresHost.isEmpty()) {
                    errors.add("PostgreSQL host is required in Lakebase mode");
                }
                if (postgresPort <= 0) {
                    errors.add("PostgreSQL port must be > 0 in Lakebase mode");
                }
                if (postgresDatabase == null || postgresDatabase.isEmpty()) {
                    errors.add("PostgreSQL database is required in Lakebase mode");
                }
                if (postgresUser == null || postgresUser.isEmpty()) {
                    errors.add("PostgreSQL user is required in Lakebase mode");
                }
                if (postgresPassword == null || postgresPassword.isEmpty()) {
                    errors.add("PostgreSQL password is required in Lakebase mode");
                }
                if (postgresTable == null || postgresTable.isEmpty()) {
                    errors.add("PostgreSQL table is required in Lakebase mode");
                }
                if (postgresPoolSize <= 0) {
                    errors.add("PostgreSQL pool size must be > 0");
                }
            } else {
                if (workspaceUrl == null || workspaceUrl.isEmpty()) {
                    errors.add("Workspace URL is required");
                }

                if (zerobusEndpoint == null || zerobusEndpoint.isEmpty()) {
                    errors.add("Zerobus endpoint is required");
                }

                if (oauthClientId == null || oauthClientId.isEmpty()) {
                    errors.add("OAuth client ID is required");
                }

                if (oauthClientSecret == null || oauthClientSecret.isEmpty()) {
                    errors.add("OAuth client secret is required");
                }

                if (targetTable == null || targetTable.isEmpty()) {
                    errors.add("Target table is required");
                } else if (catalogName.isEmpty() || schemaName.isEmpty() || tableName.isEmpty()) {
                    errors.add("Target table must be in format: catalog.schema.table");
                }
            }

            // Only validate tag selection when direct subscriptions are enabled.
            if (enableDirectSubscriptions) {
                if ("folder".equals(tagSelectionMode) && (tagFolderPath == null || tagFolderPath.isEmpty())) {
                    errors.add("Tag folder path is required when using folder selection mode");
                }

                if ("pattern".equals(tagSelectionMode) && (tagPathPattern == null || tagPathPattern.isEmpty())) {
                    errors.add("Tag path pattern is required when using pattern selection mode");
                }

                if ("explicit".equals(tagSelectionMode) && (explicitTagPaths == null || explicitTagPaths.isEmpty())) {
                    errors.add("At least one tag path is required when using explicit selection mode");
                }
            }
        }
        
        if (batchSize <= 0 || batchSize > 10000) {
            errors.add("Batch size must be between 1 and 10000");
        }
        
        if (batchFlushIntervalMs < 100 || batchFlushIntervalMs > 60000) {
            errors.add("Batch flush interval must be between 100ms and 60000ms");
        }

        if (enableStoreAndForward) {
            if (spoolMaxBytes < (10L * 1024 * 1024)) {
                errors.add("Spool max bytes must be at least 10MB when store-and-forward is enabled");
            }
            if (spoolHighWatermarkPct <= 0.0 || spoolHighWatermarkPct >= 1.0) {
                errors.add("Spool high watermark must be between 0 and 1");
            }
            if (spoolLowWatermarkPct <= 0.0 || spoolLowWatermarkPct >= 1.0) {
                errors.add("Spool low watermark must be between 0 and 1");
            }
            if (spoolLowWatermarkPct >= spoolHighWatermarkPct) {
                errors.add("Spool low watermark must be less than high watermark");
            }

            // Validate spool directory is usable (no silent runtime fallback).
            try {
                if (spoolDirectory == null || spoolDirectory.isBlank()) {
                    errors.add("Spool directory is required when store-and-forward is enabled");
                } else {
                    // Same resolution logic as DiskSpool: absolute path or relative to working dir.
                    Path p = Path.of(spoolDirectory);
                    if (!p.isAbsolute()) {
                        p = new java.io.File(spoolDirectory).toPath().toAbsolutePath().normalize();
                    }
                    Files.createDirectories(p);
                    if (!Files.isDirectory(p)) {
                        errors.add("Spool directory path is not a directory: " + p);
                    } else if (!Files.isWritable(p)) {
                        errors.add("Spool directory is not writable: " + p);
                    }
                }
            } catch (Exception e) {
                errors.add("Spool directory is not usable: " + (e.getMessage() == null ? e.getClass().getSimpleName() : e.getMessage()));
            }
        }

        // Numeric compression validation (edge-side reduction).
        NumericCompressionMode effMode = getNumericCompressionModeEffective();

        if (effMode == NumericCompressionMode.DEADBAND) {
            if (numericDeadband < 0.0) {
                errors.add("numericDeadband must be >= 0");
            }
        } else if (effMode == NumericCompressionMode.SDT) {
            if (numericSdtDeviation <= 0.0) {
                errors.add("numericSdtDeviation must be > 0 when numericCompressionMode is SDT");
            }
            if (numericSdtMaxIntervalMs < 0L) {
                errors.add("numericSdtMaxIntervalMs must be >= 0");
            }
            if (numericSdtMinIntervalMs < 0L) {
                errors.add("numericSdtMinIntervalMs must be >= 0");
            }
            if (numericSdtMaxIntervalMs > 0L && numericSdtMinIntervalMs > numericSdtMaxIntervalMs) {
                errors.add("numericSdtMinIntervalMs must be <= numericSdtMaxIntervalMs when maxInterval is enabled");
            }
        }

        // Per-tag numeric compression rules validation.
        if (numericCompressionRules != null && !numericCompressionRules.isEmpty()) {
            for (int i = 0; i < numericCompressionRules.size(); i++) {
                NumericCompressionRule r = numericCompressionRules.get(i);
                if (r == null) {
                    continue;
                }
                if (r.tagPathRegex == null || r.tagPathRegex.isBlank()) {
                    errors.add("numericCompressionRules[" + i + "].tagPathRegex is required (non-empty)");
                    continue;
                }
                NumericCompressionMode m = (r.mode != null) ? r.mode : effMode;
                if (m == NumericCompressionMode.DEADBAND) {
                    if (r.deadband < 0.0) {
                        errors.add("numericCompressionRules[" + i + "].deadband must be >= 0");
                    }
                } else if (m == NumericCompressionMode.SDT) {
                    if (r.sdtDeviation <= 0.0) {
                        errors.add("numericCompressionRules[" + i + "].sdtDeviation must be > 0");
                    }
                    if (r.sdtMaxIntervalMs < 0L) {
                        errors.add("numericCompressionRules[" + i + "].sdtMaxIntervalMs must be >= 0");
                    }
                    if (r.sdtMinIntervalMs < 0L) {
                        errors.add("numericCompressionRules[" + i + "].sdtMinIntervalMs must be >= 0");
                    }
                    if (r.sdtMaxIntervalMs > 0L && r.sdtMinIntervalMs > r.sdtMaxIntervalMs) {
                        errors.add("numericCompressionRules[" + i + "].sdtMinIntervalMs must be <= sdtMaxIntervalMs when maxInterval is enabled");
                    }
                }
                try {
                    r.compile();
                } catch (Exception e) {
                    errors.add("numericCompressionRules[" + i + "].tagPathRegex is invalid regex: " + r.tagPathRegex);
                }
            }
        }

        // Backward-compatible per-tag deadband rules validation (only meaningful under deadband mode).
        if (effMode == NumericCompressionMode.DEADBAND && numericDeadbandRules != null && !numericDeadbandRules.isEmpty()) {
            for (int i = 0; i < numericDeadbandRules.size(); i++) {
                DeadbandRule r = numericDeadbandRules.get(i);
                if (r == null) {
                    continue;
                }
                if (r.tagPathRegex == null || r.tagPathRegex.isBlank()) {
                    errors.add("numericDeadbandRules[" + i + "].tagPathRegex is required (non-empty)");
                    continue;
                }
                if (r.deadband < 0.0) {
                    errors.add("numericDeadbandRules[" + i + "].deadband must be >= 0");
                }
                try {
                    // Validate regex compiles (also caches compiled pattern for runtime).
                    r.compile();
                } catch (Exception e) {
                    errors.add("numericDeadbandRules[" + i + "].tagPathRegex is invalid regex: " + r.tagPathRegex);
                }
            }
        }
        
        return errors;
    }

    /**
     * Best-effort normalization to keep configs portable across:
     * - local installs
     * - Docker containers (Ignition typically lives under /usr/local/bin/ignition)
     * - restored .gwbk configs that may include absolute host paths
     *
     * Rules:
     * - Default to a relative path under Ignition install dir: "data/zerobus-spool"
     * - If spoolDirectory points at "/usr/local/(bin/)?ignition/data/<X>", rewrite to "data/<X>"
     * - If spoolDirectory points at "/usr/local/ignition/data/<X>" (common mistake), rewrite to "data/<X>"
     */
    public void autoCorrectPaths() {
        // Keep default relative path unless explicitly overridden.
        if (spoolDirectory == null || spoolDirectory.isBlank()) {
            spoolDirectory = "data/zerobus-spool";
            return;
        }

        String raw = spoolDirectory.trim();

        // Prefer a portable relative path when the user provided an absolute path under Ignition's data dir.
        String[] prefixes = new String[] {
            "/usr/local/ignition/data/",
            "/usr/local/bin/ignition/data/"
        };
        for (String pfx : prefixes) {
            if (raw.startsWith(pfx)) {
                String tail = raw.substring(pfx.length());
                spoolDirectory = tail.isBlank() ? "data/zerobus-spool" : ("data/" + tail);
                return;
            }
        }

        // Otherwise, keep as-is (but normalize the common docker install mismatch).
        if (raw.startsWith("/usr/local/ignition/")) {
            spoolDirectory = raw.replaceFirst("^/usr/local/ignition/", "/usr/local/bin/ignition/");
        } else {
            spoolDirectory = raw;
        }
    }
    
    /**
     * Check if the new configuration requires a service restart.
     * 
     * @param newConfig The new configuration to compare against
     * @return true if services need to be restarted
     */
    public boolean requiresRestart(ConfigModel newConfig) {
        return !Objects.equals(this.workspaceUrl, newConfig.workspaceUrl)
            || !Objects.equals(this.zerobusEndpoint, newConfig.zerobusEndpoint)
            || !Objects.equals(this.oauthClientId, newConfig.oauthClientId)
            || !Objects.equals(this.oauthClientSecret, newConfig.oauthClientSecret)
            || this.sinkMode != newConfig.sinkMode
            || this.enableZerobusSink != newConfig.enableZerobusSink
            || this.enablePostgresSink != newConfig.enablePostgresSink
            || !Objects.equals(this.postgresHost, newConfig.postgresHost)
            || this.postgresPort != newConfig.postgresPort
            || !Objects.equals(this.postgresDatabase, newConfig.postgresDatabase)
            || !Objects.equals(this.postgresUser, newConfig.postgresUser)
            || !Objects.equals(this.postgresPassword, newConfig.postgresPassword)
            || !Objects.equals(this.postgresTable, newConfig.postgresTable)
            || this.postgresPoolSize != newConfig.postgresPoolSize
            || !Objects.equals(this.targetTable, newConfig.targetTable)
            || this.enableDirectSubscriptions != newConfig.enableDirectSubscriptions
            || !Objects.equals(this.tagSelectionMode, newConfig.tagSelectionMode)
            || !Objects.equals(this.tagFolderPath, newConfig.tagFolderPath)
            || !Objects.equals(this.tagPathPattern, newConfig.tagPathPattern)
            || !Objects.equals(this.explicitTagPaths, newConfig.explicitTagPaths)
            || this.includeSubfolders != newConfig.includeSubfolders
            || this.batchSize != newConfig.batchSize
            || this.batchFlushIntervalMs != newConfig.batchFlushIntervalMs
            || this.maxQueueSize != newConfig.maxQueueSize
            || this.maxEventsPerSecond != newConfig.maxEventsPerSecond
            || this.enableStoreAndForward != newConfig.enableStoreAndForward
            || !Objects.equals(this.spoolDirectory, newConfig.spoolDirectory)
            || this.spoolMaxBytes != newConfig.spoolMaxBytes
            || Double.compare(this.spoolHighWatermarkPct, newConfig.spoolHighWatermarkPct) != 0
            || Double.compare(this.spoolLowWatermarkPct, newConfig.spoolLowWatermarkPct) != 0
            || this.spoolReadMaxBytes != newConfig.spoolReadMaxBytes
            || this.maxRetries != newConfig.maxRetries
            || this.retryBackoffMs != newConfig.retryBackoffMs
            || this.connectionTimeoutMs != newConfig.connectionTimeoutMs
            || this.requestTimeoutMs != newConfig.requestTimeoutMs
            || !Objects.equals(this.sourceSystemId, newConfig.sourceSystemId)
            || this.includeQuality != newConfig.includeQuality
            || !Objects.equals(this.numericCompressionMode, newConfig.numericCompressionMode)
            || this.onlyOnChange != newConfig.onlyOnChange
            || Double.compare(this.numericDeadband, newConfig.numericDeadband) != 0
            || Double.compare(this.numericSdtDeviation, newConfig.numericSdtDeviation) != 0
            || this.numericSdtMaxIntervalMs != newConfig.numericSdtMaxIntervalMs
            || this.numericSdtMinIntervalMs != newConfig.numericSdtMinIntervalMs
            || !Objects.equals(this.numericDeadbandRules, newConfig.numericDeadbandRules)
            || !Objects.equals(this.numericCompressionRules, newConfig.numericCompressionRules)
            || this.enabled != newConfig.enabled
            || this.debugLogging != newConfig.debugLogging;
    }
    
    /**
     * Update this config from another config (used when applying new settings).
     */
    public void updateFrom(ConfigModel other) {
        this.workspaceUrl = other.workspaceUrl;
        this.zerobusEndpoint = other.zerobusEndpoint;
        this.oauthClientId = other.oauthClientId;
        this.oauthClientSecret = other.oauthClientSecret;
        this.sinkMode = other.sinkMode;
        this.enableZerobusSink = other.enableZerobusSink;
        this.enablePostgresSink = other.enablePostgresSink;
        this.postgresHost = other.postgresHost;
        this.postgresPort = other.postgresPort;
        this.postgresDatabase = other.postgresDatabase;
        this.postgresUser = other.postgresUser;
        this.postgresPassword = other.postgresPassword;
        this.postgresTable = other.postgresTable;
        this.postgresPoolSize = other.postgresPoolSize;
        this.targetTable = other.targetTable;
        this.parseTableName();
        this.enableDirectSubscriptions = other.enableDirectSubscriptions;
        this.tagSelectionMode = other.tagSelectionMode;
        this.tagFolderPath = other.tagFolderPath;
        this.tagPathPattern = other.tagPathPattern;
        this.explicitTagPaths = new ArrayList<>(other.explicitTagPaths);
        this.includeSubfolders = other.includeSubfolders;
        this.batchSize = other.batchSize;
        this.batchFlushIntervalMs = other.batchFlushIntervalMs;
        this.maxQueueSize = other.maxQueueSize;
        this.maxEventsPerSecond = other.maxEventsPerSecond;
        this.enableStoreAndForward = other.enableStoreAndForward;
        this.spoolDirectory = other.spoolDirectory;
        this.spoolMaxBytes = other.spoolMaxBytes;
        this.spoolHighWatermarkPct = other.spoolHighWatermarkPct;
        this.spoolLowWatermarkPct = other.spoolLowWatermarkPct;
        this.spoolReadMaxBytes = other.spoolReadMaxBytes;
        this.maxRetries = other.maxRetries;
        this.retryBackoffMs = other.retryBackoffMs;
        this.connectionTimeoutMs = other.connectionTimeoutMs;
        this.requestTimeoutMs = other.requestTimeoutMs;
        this.sourceSystemId = other.sourceSystemId;
        this.includeQuality = other.includeQuality;
        this.numericCompressionMode = other.numericCompressionMode;
        this.onlyOnChange = other.onlyOnChange;
        this.numericDeadband = other.numericDeadband;
        this.numericSdtDeviation = other.numericSdtDeviation;
        this.numericSdtMaxIntervalMs = other.numericSdtMaxIntervalMs;
        this.numericSdtMinIntervalMs = other.numericSdtMinIntervalMs;
        this.numericDeadbandRules = (other.numericDeadbandRules == null) ? new ArrayList<>() : new ArrayList<>(other.numericDeadbandRules);
        this.numericCompressionRules = (other.numericCompressionRules == null) ? new ArrayList<>() : new ArrayList<>(other.numericCompressionRules);
        this.enabled = other.enabled;
        this.debugLogging = other.debugLogging;
    }
    
    @Override
    public String toString() {
        return "ConfigModel{" +
                "workspaceUrl='" + workspaceUrl + '\'' +
                ", sinkMode=" + sinkMode +
                ", targetTable='" + targetTable + '\'' +
                ", tagSelectionMode='" + tagSelectionMode + '\'' +
                ", batchSize=" + batchSize +
                ", enabled=" + enabled +
                '}';
    }

    public static final class NumericCompressionPolicy implements Serializable {
        private static final long serialVersionUID = 1L;

        public final NumericCompressionMode mode;
        public final double deadband;
        public final double sdtDeviation;
        public final long sdtMaxIntervalMs;
        public final long sdtMinIntervalMs;

        public NumericCompressionPolicy(
                NumericCompressionMode mode,
                double deadband,
                double sdtDeviation,
                long sdtMaxIntervalMs,
                long sdtMinIntervalMs
        ) {
            this.mode = (mode == null) ? NumericCompressionMode.NONE : mode;
            this.deadband = deadband;
            this.sdtDeviation = sdtDeviation;
            this.sdtMaxIntervalMs = sdtMaxIntervalMs;
            this.sdtMinIntervalMs = sdtMinIntervalMs;
        }

        @Override
        public String toString() {
            return "NumericCompressionPolicy{" +
                    "mode=" + mode +
                    ", deadband=" + deadband +
                    ", sdtDeviation=" + sdtDeviation +
                    ", sdtMaxIntervalMs=" + sdtMaxIntervalMs +
                    ", sdtMinIntervalMs=" + sdtMinIntervalMs +
                    '}';
        }
    }

    /**
     * A rule that maps a tag path regex to a numeric compression policy.
     * First matching rule wins.
     */
    public static final class NumericCompressionRule implements Serializable {
        private static final long serialVersionUID = 1L;

        private String tagPathRegex = "";
        private NumericCompressionMode mode = null;

        // Parameters (used depending on mode)
        private double deadband = 0.0;
        private double sdtDeviation = 0.0;
        private long sdtMaxIntervalMs = 0L;
        private long sdtMinIntervalMs = 0L;

        private transient Pattern compiled;

        public NumericCompressionRule() {}

        public NumericCompressionRule(String tagPathRegex, NumericCompressionMode mode) {
            this.tagPathRegex = tagPathRegex;
            this.mode = mode;
        }

        public String getTagPathRegex() {
            return tagPathRegex;
        }

        public void setTagPathRegex(String tagPathRegex) {
            this.tagPathRegex = tagPathRegex;
            this.compiled = null;
        }

        public NumericCompressionMode getMode() {
            return mode;
        }

        public void setMode(NumericCompressionMode mode) {
            this.mode = mode;
        }

        public double getDeadband() {
            return deadband;
        }

        public void setDeadband(double deadband) {
            this.deadband = deadband;
        }

        public double getSdtDeviation() {
            return sdtDeviation;
        }

        public void setSdtDeviation(double sdtDeviation) {
            this.sdtDeviation = sdtDeviation;
        }

        public long getSdtMaxIntervalMs() {
            return sdtMaxIntervalMs;
        }

        public void setSdtMaxIntervalMs(long sdtMaxIntervalMs) {
            this.sdtMaxIntervalMs = sdtMaxIntervalMs;
        }

        public long getSdtMinIntervalMs() {
            return sdtMinIntervalMs;
        }

        public void setSdtMinIntervalMs(long sdtMinIntervalMs) {
            this.sdtMinIntervalMs = sdtMinIntervalMs;
        }

        boolean matches(String tagPath) {
            if (tagPathRegex == null || tagPathRegex.isBlank()) {
                return false;
            }
            Pattern p = compiled;
            if (p == null) {
                p = compile();
            }
            return p.matcher(tagPath).matches();
        }

        Pattern compile() {
            Pattern p = Pattern.compile(tagPathRegex);
            this.compiled = p;
            return p;
        }

        NumericCompressionPolicy toPolicyOrFallback(NumericCompressionPolicy fallback) {
            NumericCompressionMode m = (this.mode != null) ? this.mode : (fallback != null ? fallback.mode : NumericCompressionMode.NONE);
            double db = (m == NumericCompressionMode.DEADBAND) ? this.deadband : (fallback != null ? fallback.deadband : 0.0);
            double dev = (m == NumericCompressionMode.SDT) ? this.sdtDeviation : (fallback != null ? fallback.sdtDeviation : 0.0);
            long maxInt = (m == NumericCompressionMode.SDT) ? this.sdtMaxIntervalMs : (fallback != null ? fallback.sdtMaxIntervalMs : 0L);
            long minInt = (m == NumericCompressionMode.SDT) ? this.sdtMinIntervalMs : (fallback != null ? fallback.sdtMinIntervalMs : 0L);
            return new NumericCompressionPolicy(m, db, dev, maxInt, minInt);
        }

        @Override
        public String toString() {
            return "NumericCompressionRule{" +
                    "tagPathRegex='" + tagPathRegex + '\'' +
                    ", mode=" + mode +
                    ", deadband=" + deadband +
                    ", sdtDeviation=" + sdtDeviation +
                    ", sdtMaxIntervalMs=" + sdtMaxIntervalMs +
                    ", sdtMinIntervalMs=" + sdtMinIntervalMs +
                    '}';
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (o == null || getClass() != o.getClass()) return false;
            NumericCompressionRule that = (NumericCompressionRule) o;
            return Double.compare(this.deadband, that.deadband) == 0
                    && Double.compare(this.sdtDeviation, that.sdtDeviation) == 0
                    && this.sdtMaxIntervalMs == that.sdtMaxIntervalMs
                    && this.sdtMinIntervalMs == that.sdtMinIntervalMs
                    && Objects.equals(this.tagPathRegex, that.tagPathRegex)
                    && this.mode == that.mode;
        }

        @Override
        public int hashCode() {
            return Objects.hash(tagPathRegex, mode, deadband, sdtDeviation, sdtMaxIntervalMs, sdtMinIntervalMs);
        }
    }

    /**
     * A rule that maps a tag path regex to an absolute numeric deadband.
     * Example:
     * - tagPathRegex: "^\\[default\\].*\\/Temp\\/.*$"
     * - deadband: 0.1
     */
    public static final class DeadbandRule implements Serializable {
        private static final long serialVersionUID = 1L;

        private String tagPathRegex = "";
        private double deadband = 0.0;

        private transient Pattern compiled;

        public DeadbandRule() {}

        public DeadbandRule(String tagPathRegex, double deadband) {
            this.tagPathRegex = tagPathRegex;
            this.deadband = deadband;
        }

        public String getTagPathRegex() {
            return tagPathRegex;
        }

        public void setTagPathRegex(String tagPathRegex) {
            this.tagPathRegex = tagPathRegex;
            this.compiled = null;
        }

        public double getDeadband() {
            return deadband;
        }

        public void setDeadband(double deadband) {
            this.deadband = deadband;
        }

        boolean matches(String tagPath) {
            if (tagPathRegex == null || tagPathRegex.isBlank()) {
                return false;
            }
            Pattern p = compiled;
            if (p == null) {
                p = compile();
            }
            return p.matcher(tagPath).matches();
        }

        Pattern compile() {
            Pattern p = Pattern.compile(tagPathRegex);
            this.compiled = p;
            return p;
        }

        @Override
        public String toString() {
            return "DeadbandRule{tagPathRegex='" + tagPathRegex + "', deadband=" + deadband + "}";
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (o == null || getClass() != o.getClass()) return false;
            DeadbandRule that = (DeadbandRule) o;
            return Double.compare(this.deadband, that.deadband) == 0
                    && Objects.equals(this.tagPathRegex, that.tagPathRegex);
        }

        @Override
        public int hashCode() {
            return Objects.hash(tagPathRegex, deadband);
        }
    }
}

