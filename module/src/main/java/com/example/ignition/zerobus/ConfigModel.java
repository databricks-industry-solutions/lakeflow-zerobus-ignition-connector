package com.example.ignition.zerobus;

import com.example.ignition.zerobus.compression.SdtOverride;

import java.io.Serializable;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;
import java.util.regex.PatternSyntaxException;

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
    
    /**
     * Authentication mode: "service_principal" (default) or "bearer_token".
     * - service_principal: uses oauthClientId + oauthClientSecret (M2M OAuth)
     * - bearer_token: uses a pre-obtained bearer token (PAT, U2M, etc.)
     */
    private String authMode = "service_principal";
    
    /** OAuth2 client ID for authentication */
    private String oauthClientId = "";
    
    /** OAuth2 client secret for authentication */
    private String oauthClientSecret = "";

    /** Databricks account ID for account-level OIDC auth (empty = use workspace OIDC) */
    private String accountId = "";

    /** Pre-obtained bearer token (PAT, U2M access token, etc.) for bearer_token auth mode */
    private String bearerToken = "";
    
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
    
    /** Only send events when value changes (deadband filtering) */
    private boolean onlyOnChange = false;
    
    /** Numeric deadband for change detection (absolute difference) */
    private double numericDeadband = 0.0;

    // === SDT Compression ===

    /** Enable Swinging Door Trending compression for numeric tags. */
    private boolean enableSdtCompression = false;

    /** SDT deviation band (+/-) around a linear interpolation corridor. */
    private double sdtDeviation = 1.0;

    /** Maximum seconds between transmitted points (heartbeat). */
    private int sdtMaxIntervalSeconds = 300;

    /** Per-tag SDT override rules. Evaluated in order; first match wins. */
    private List<SdtOverride> sdtOverrides = new ArrayList<>();

    // === Sink Selection ===

    /** Sink mode: "zerobus" or "lakebase". */
    private String sinkMode = "zerobus";

    /** Enable Zerobus (Delta Lake) sink. Kept for backward compatibility. */
    private boolean enableZerobusSink = true;

    /** Enable PostgreSQL (Lakebase) sink. Kept for backward compatibility. */
    private boolean enablePostgresSink = false;

    // === PostgreSQL (Lakebase) Settings ===

    /** PostgreSQL host (e.g., ep-xxx.databricks.com) */
    private String postgresHost = "";

    /** PostgreSQL port (default 5432) */
    private int postgresPort = 5432;

    /** PostgreSQL database name */
    private String postgresDatabase = "";

    /** PostgreSQL username (role name) */
    private String postgresUser = "";

    /** PostgreSQL password */
    private String postgresPassword = "";

    /** PostgreSQL table name (default raw_tags) */
    private String postgresTable = "raw_tags";

    /** PostgreSQL connection pool size (default 5) */
    private int postgresPoolSize = 5;

    // === API Security ===

    /** Optional API key for authenticating POST requests to /system/zerobus/* endpoints.
     *  When set (non-empty), all POST requests must include Authorization: Bearer &lt;key&gt;. */
    private String ingestApiKey = "";

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
    
    public String getAuthMode() {
        return authMode;
    }
    
    public void setAuthMode(String authMode) {
        this.authMode = authMode;
    }
    
    public String getBearerToken() {
        return bearerToken;
    }
    
    public void setBearerToken(String bearerToken) {
        this.bearerToken = bearerToken;
    }

    public String getAccountId() {
        return accountId;
    }

    public void setAccountId(String accountId) {
        this.accountId = accountId;
    }

    /** @return true when auth mode is "bearer_token" */
    public boolean isBearerTokenMode() {
        return "bearer_token".equals(authMode);
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

    public boolean isEnableSdtCompression() {
        return enableSdtCompression;
    }

    public void setEnableSdtCompression(boolean enableSdtCompression) {
        this.enableSdtCompression = enableSdtCompression;
    }

    public double getSdtDeviation() {
        return sdtDeviation;
    }

    public void setSdtDeviation(double sdtDeviation) {
        this.sdtDeviation = sdtDeviation;
    }

    public int getSdtMaxIntervalSeconds() {
        return sdtMaxIntervalSeconds;
    }

    public void setSdtMaxIntervalSeconds(int sdtMaxIntervalSeconds) {
        this.sdtMaxIntervalSeconds = sdtMaxIntervalSeconds;
    }

    public List<SdtOverride> getSdtOverrides() {
        return sdtOverrides;
    }

    public void setSdtOverrides(List<SdtOverride> sdtOverrides) {
        this.sdtOverrides = sdtOverrides != null ? sdtOverrides : new ArrayList<>();
    }

    /**
     * Find the first SDT override rule that matches the given tag path.
     *
     * @param tagPath full tag path string
     * @return the matching override, or null if no rule matches (use global defaults)
     */
    public SdtOverride findMatchingOverride(String tagPath) {
        if (tagPath == null || sdtOverrides == null || sdtOverrides.isEmpty()) {
            return null;
        }
        for (SdtOverride override : sdtOverrides) {
            if (override != null && override.matches(tagPath)) {
                return override;
            }
        }
        return null;
    }

    public boolean isEnabled() {
        return enabled;
    }
    
    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }
    
    public String getIngestApiKey() {
        return ingestApiKey;
    }

    public void setIngestApiKey(String ingestApiKey) {
        this.ingestApiKey = ingestApiKey;
    }

    public boolean isDebugLogging() {
        return debugLogging;
    }

    public void setDebugLogging(boolean debugLogging) {
        this.debugLogging = debugLogging;
    }

    public boolean isEnableZerobusSink() {
        return enableZerobusSink;
    }

    public void setEnableZerobusSink(boolean enableZerobusSink) {
        this.enableZerobusSink = enableZerobusSink;
        if (enableZerobusSink) {
            this.enablePostgresSink = false;
            this.sinkMode = "zerobus";
        }
    }

    public boolean isEnablePostgresSink() {
        return enablePostgresSink;
    }

    public void setEnablePostgresSink(boolean enablePostgresSink) {
        this.enablePostgresSink = enablePostgresSink;
        if (enablePostgresSink) {
            this.enableZerobusSink = false;
            this.sinkMode = "lakebase";
        }
    }

    public String getSinkMode() {
        return sinkMode;
    }

    public void setSinkMode(String sinkMode) {
        this.sinkMode = sinkMode;
        normalizeSinkConfiguration();
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
        normalizeSinkConfiguration();

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
            if (enableZerobusSink) {
                if (workspaceUrl == null || workspaceUrl.isEmpty()) {
                    errors.add("Workspace URL is required");
                }

                if (zerobusEndpoint == null || zerobusEndpoint.isEmpty()) {
                    errors.add("Zerobus endpoint is required");
                } else {
                    // Workspace URL and Zerobus endpoint must refer to the same workspace (same ID).
                    String urlId = extractWorkspaceIdFromWorkspaceUrl(workspaceUrl);
                    String endpointId = extractWorkspaceIdFromEndpoint(zerobusEndpoint);
                    if (urlId != null && endpointId != null && !urlId.equals(endpointId)) {
                        errors.add("Workspace URL and Zerobus endpoint must be for the same workspace (workspace ID mismatch: " + urlId + " vs " + endpointId + ")");
                    }
                }

                if (isBearerTokenMode()) {
                    if (bearerToken == null || bearerToken.isEmpty()) {
                        errors.add("Bearer token is required when using bearer token auth mode");
                    }
                } else {
                    // service_principal mode (default)
                    if (oauthClientId == null || oauthClientId.isEmpty()) {
                        errors.add("OAuth client ID is required");
                    }

                    if (oauthClientSecret == null || oauthClientSecret.isEmpty()) {
                        errors.add("OAuth client secret is required");
                    }
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

        if (maxQueueSize < 1 || maxQueueSize > 1_000_000) {
            errors.add("Max queue size must be between 1 and 1000000");
        }

        if (maxEventsPerSecond < 1 || maxEventsPerSecond > 1_000_000) {
            errors.add("Max events per second must be between 1 and 1000000");
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

        if (enableSdtCompression) {
            if (sdtDeviation <= 0) {
                errors.add("SDT deviation must be greater than 0 when compression is enabled");
            }
            if (sdtMaxIntervalSeconds <= 0) {
                errors.add("SDT max interval must be greater than 0 when compression is enabled");
            }
        }

        if (sdtOverrides != null) {
            for (int i = 0; i < sdtOverrides.size(); i++) {
                SdtOverride ov = sdtOverrides.get(i);
                if (ov == null) {
                    continue;
                }
                String prefix = "sdtOverrides[" + i + "]: ";
                if (ov.getPattern() == null || ov.getPattern().isEmpty()) {
                    errors.add(prefix + "pattern is required");
                } else {
                    try {
                        Pattern.compile(ov.getPattern());
                    } catch (PatternSyntaxException e) {
                        errors.add(prefix + "invalid regex pattern: " + e.getDescription());
                    }
                }
                if (ov.getDeviation() < 0) {
                    errors.add(prefix + "deviation must be >= 0");
                }
                if (ov.getMaxIntervalSeconds() <= 0) {
                    errors.add(prefix + "maxIntervalSeconds must be > 0");
                }
            }
        }

        // Validate PostgreSQL settings when enabled
        if (enablePostgresSink && enabled) {
            if (postgresHost == null || postgresHost.isEmpty()) {
                errors.add("PostgreSQL host is required when PostgreSQL sink is enabled");
            }
            if (postgresPort <= 0 || postgresPort > 65535) {
                errors.add("PostgreSQL port must be between 1 and 65535");
            }
            if (postgresDatabase == null || postgresDatabase.isEmpty()) {
                errors.add("PostgreSQL database is required when PostgreSQL sink is enabled");
            }
            if (postgresUser == null || postgresUser.isEmpty()) {
                errors.add("PostgreSQL user is required when PostgreSQL sink is enabled");
            }
            if (postgresPassword == null || postgresPassword.isEmpty()) {
                errors.add("PostgreSQL password is required when PostgreSQL sink is enabled");
            }
            if (postgresTable == null || postgresTable.isEmpty()) {
                errors.add("PostgreSQL table is required when PostgreSQL sink is enabled");
            }
            if (postgresPoolSize < 1 || postgresPoolSize > 100) {
                errors.add("PostgreSQL pool size must be between 1 and 100");
            }
        }

        if (!"zerobus".equals(sinkMode) && !"lakebase".equals(sinkMode)) {
            errors.add("Sink mode must be either 'zerobus' or 'lakebase'");
        }

        return errors;
    }

    /**
     * Normalize sink mode + legacy boolean flags.
     *
     * Backward-compatibility behavior:
     * - If sinkMode is missing/blank (older config), infer mode from booleans.
     * - Once mode is known, force booleans to an exclusive configuration.
     */
    public void normalizeSinkConfiguration() {
        String normalizedMode = sinkMode == null ? "" : sinkMode.trim().toLowerCase();

        if (normalizedMode.isEmpty()) {
            // Legacy config migration path (no sinkMode set yet)
            if (enablePostgresSink && !enableZerobusSink) {
                normalizedMode = "lakebase";
            } else {
                // Default and tie-breaker: zerobus
                normalizedMode = "zerobus";
            }
        }

        if ("lakebase".equals(normalizedMode)) {
            sinkMode = "lakebase";
            enableZerobusSink = false;
            enablePostgresSink = true;
            return;
        }

        if ("zerobus".equals(normalizedMode)) {
            sinkMode = "zerobus";
            enableZerobusSink = true;
            enablePostgresSink = false;
            return;
        }

        // Preserve unknown value for validation error, but keep a safe default behavior.
        sinkMode = normalizedMode;
        enableZerobusSink = true;
        enablePostgresSink = false;
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
     * Extract workspace ID from Databricks workspace URL for validation.
     * Azure: https://adb-7405607216190670.10.azuredatabricks.net -> 7405607216190670
     * AWS: host may contain workspace ID in first segment.
     */
    private static String extractWorkspaceIdFromWorkspaceUrl(String workspaceUrl) {
        if (workspaceUrl == null || workspaceUrl.isBlank()) {
            return null;
        }
        try {
            URI uri = URI.create(workspaceUrl.trim());
            String host = uri.getHost();
            if (host == null || host.isEmpty()) {
                return null;
            }
            // Azure: adb-<workspaceId>.10.azuredatabricks.net
            if (host.startsWith("adb-")) {
                int dot = host.indexOf('.', 4);
                return dot > 4 ? host.substring(4, dot) : host.substring(4);
            }
            // AWS: <workspaceId>.cloud.databricks.com or similar; first segment is often the ID
            int dot = host.indexOf('.');
            return dot > 0 ? host.substring(0, dot) : host;
        } catch (Exception e) {
            return null;
        }
    }

    /**
     * Extract workspace ID from Zerobus endpoint host for validation.
     * Format: <workspaceId>.zerobus.<region>.<domain> e.g. 7405607216190670.zerobus.eastus2.azuredatabricks.net
     * Endpoint may be host-only (no scheme) or full URL.
     */
    private static String extractWorkspaceIdFromEndpoint(String zerobusEndpoint) {
        if (zerobusEndpoint == null || zerobusEndpoint.isBlank()) {
            return null;
        }
        try {
            String s = zerobusEndpoint.trim();
            String host = null;
            if (s.contains("://")) {
                URI uri = URI.create(s);
                host = uri.getHost();
            }
            if (host == null || host.isEmpty()) {
                int slash = s.indexOf('/');
                String hostPart = slash > 0 ? s.substring(0, slash) : s;
                int colon = hostPart.indexOf(':');
                host = colon > 0 ? hostPart.substring(0, colon) : hostPart;
            }
            if (host == null || host.isEmpty()) {
                return null;
            }
            int dot = host.indexOf('.');
            return dot > 0 ? host.substring(0, dot) : host;
        } catch (Exception e) {
            return null;
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
            || !Objects.equals(this.authMode, newConfig.authMode)
            || !Objects.equals(this.oauthClientId, newConfig.oauthClientId)
            || !Objects.equals(this.oauthClientSecret, newConfig.oauthClientSecret)
            || !Objects.equals(this.accountId, newConfig.accountId)
            || !Objects.equals(this.bearerToken, newConfig.bearerToken)
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
            || this.onlyOnChange != newConfig.onlyOnChange
            || Double.compare(this.numericDeadband, newConfig.numericDeadband) != 0
            || this.enableSdtCompression != newConfig.enableSdtCompression
            || Double.compare(this.sdtDeviation, newConfig.sdtDeviation) != 0
            || this.sdtMaxIntervalSeconds != newConfig.sdtMaxIntervalSeconds
            || !Objects.equals(this.sdtOverrides, newConfig.sdtOverrides)
            || this.enabled != newConfig.enabled
            || this.debugLogging != newConfig.debugLogging
            || !Objects.equals(this.sinkMode, newConfig.sinkMode)
            || this.enableZerobusSink != newConfig.enableZerobusSink
            || this.enablePostgresSink != newConfig.enablePostgresSink
            || !Objects.equals(this.postgresHost, newConfig.postgresHost)
            || this.postgresPort != newConfig.postgresPort
            || !Objects.equals(this.postgresDatabase, newConfig.postgresDatabase)
            || !Objects.equals(this.postgresUser, newConfig.postgresUser)
            || !Objects.equals(this.postgresPassword, newConfig.postgresPassword)
            || !Objects.equals(this.postgresTable, newConfig.postgresTable)
            || this.postgresPoolSize != newConfig.postgresPoolSize;
    }
    
    /**
     * Update this config from another config (used when applying new settings).
     */
    public void updateFrom(ConfigModel other) {
        this.workspaceUrl = other.workspaceUrl;
        this.zerobusEndpoint = other.zerobusEndpoint;
        this.authMode = other.authMode;
        this.oauthClientId = other.oauthClientId;
        this.oauthClientSecret = other.oauthClientSecret;
        this.accountId = other.accountId;
        this.bearerToken = other.bearerToken;
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
        this.onlyOnChange = other.onlyOnChange;
        this.numericDeadband = other.numericDeadband;
        this.enableSdtCompression = other.enableSdtCompression;
        this.sdtDeviation = other.sdtDeviation;
        this.sdtMaxIntervalSeconds = other.sdtMaxIntervalSeconds;
        this.sdtOverrides = other.sdtOverrides != null ? new ArrayList<>(other.sdtOverrides) : new ArrayList<>();
        this.enabled = other.enabled;
        this.debugLogging = other.debugLogging;
        this.sinkMode = other.sinkMode;
        this.ingestApiKey = other.ingestApiKey;
        this.enableZerobusSink = other.enableZerobusSink;
        this.enablePostgresSink = other.enablePostgresSink;
        this.postgresHost = other.postgresHost;
        this.postgresPort = other.postgresPort;
        this.postgresDatabase = other.postgresDatabase;
        this.postgresUser = other.postgresUser;
        this.postgresPassword = other.postgresPassword;
        this.postgresTable = other.postgresTable;
        this.postgresPoolSize = other.postgresPoolSize;
        normalizeSinkConfiguration();
    }
    
    @Override
    public String toString() {
        return "ConfigModel{" +
                "workspaceUrl='" + workspaceUrl + '\'' +
                ", targetTable='" + targetTable + '\'' +
                ", tagSelectionMode='" + tagSelectionMode + '\'' +
                ", batchSize=" + batchSize +
                ", enabled=" + enabled +
                '}';
    }
}

