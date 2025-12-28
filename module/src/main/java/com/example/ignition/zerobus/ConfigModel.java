package com.example.ignition.zerobus;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

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
        
        return errors;
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
            || this.maxRetries != newConfig.maxRetries
            || this.retryBackoffMs != newConfig.retryBackoffMs
            || this.connectionTimeoutMs != newConfig.connectionTimeoutMs
            || this.requestTimeoutMs != newConfig.requestTimeoutMs
            || !Objects.equals(this.sourceSystemId, newConfig.sourceSystemId)
            || this.includeQuality != newConfig.includeQuality
            || this.onlyOnChange != newConfig.onlyOnChange
            || Double.compare(this.numericDeadband, newConfig.numericDeadband) != 0
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
        this.maxRetries = other.maxRetries;
        this.retryBackoffMs = other.retryBackoffMs;
        this.connectionTimeoutMs = other.connectionTimeoutMs;
        this.requestTimeoutMs = other.requestTimeoutMs;
        this.sourceSystemId = other.sourceSystemId;
        this.includeQuality = other.includeQuality;
        this.onlyOnChange = other.onlyOnChange;
        this.numericDeadband = other.numericDeadband;
        this.enabled = other.enabled;
        this.debugLogging = other.debugLogging;
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

