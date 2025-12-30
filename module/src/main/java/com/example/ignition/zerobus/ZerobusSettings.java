package com.example.ignition.zerobus;

import com.example.ignition.zerobus.web.MaskedPasswordEditorSource;
import com.inductiveautomation.ignition.gateway.localdb.persistence.*;
import simpleorm.dataset.SFieldFlags;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * ZerobusSettings - PersistentRecord for storing Zerobus connector configuration in Gateway database.
 *
 * This record is automatically mapped to Ignition's internal database and provides:
 * - Persistent storage across Gateway restarts
 * - Automatic UI generation in Gateway Config web interface
 * - Integration with Gateway backup/restore
 * - Secure credential storage
 *
 * The Gateway Config UI will appear at: Config → System → Settings → Zerobus Connector
 */
public class ZerobusSettings extends PersistentRecord {

    /**
     * Record metadata - defines the table name and field mappings
     */
    public static final RecordMeta<ZerobusSettings> META = new RecordMeta<>(
        ZerobusSettings.class,
        "ZerobusSettings"
    ).setNounKey("ZerobusSettings.Noun")
     .setNounPluralKey("ZerobusSettings.Noun.Plural");

    // === Module Control ===

    public static final BooleanField Enabled = new BooleanField(META, "Enabled", SFieldFlags.SMANDATORY);

    public static final BooleanField DebugLogging = new BooleanField(META, "DebugLogging");

    // === Databricks Connection Settings ===

    public static final StringField WorkspaceUrl = new StringField(META, "WorkspaceUrl", SFieldFlags.SMANDATORY);

    public static final StringField ZerobusEndpoint = new StringField(META, "ZerobusEndpoint", SFieldFlags.SMANDATORY);

    public static final StringField OauthClientId = new StringField(META, "OauthClientId", SFieldFlags.SMANDATORY);

    // NOTE: Do NOT mark as SMANDATORY in the UI, because we want to allow "leave blank to keep existing secret"
    // on edit. We enforce "required on create" in ZerobusSettingsPage.onBeforeCommit().
    public static final EncodedStringField OauthClientSecret = new EncodedStringField(META, "OauthClientSecret");

    // === Unity Catalog Settings ===

    public static final StringField TargetTable = new StringField(META, "TargetTable", SFieldFlags.SMANDATORY);

    public static final StringField SourceSystemId = new StringField(META, "SourceSystemId");

    // === Tag Selection Settings ===

    public static final BooleanField EnableDirectSubscriptions = new BooleanField(META, "EnableDirectSubscriptions");

    public static final StringField TagSelectionMode = new StringField(META, "TagSelectionMode");

    public static final StringField TagFolderPath = new StringField(META, "TagFolderPath");

    public static final StringField TagPathPattern = new StringField(META, "TagPathPattern");

    // Store explicit tag paths as comma-separated string
    public static final StringField ExplicitTagPaths = new StringField(META, "ExplicitTagPaths");

    public static final BooleanField IncludeSubfolders = new BooleanField(META, "IncludeSubfolders");

    // === Batching & Performance Settings ===

    public static final IntField BatchSize = new IntField(META, "BatchSize");

    public static final LongField BatchFlushIntervalMs = new LongField(META, "BatchFlushIntervalMs");

    public static final IntField MaxQueueSize = new IntField(META, "MaxQueueSize");

    public static final IntField MaxEventsPerSecond = new IntField(META, "MaxEventsPerSecond");

    // === Store-and-Forward (disk spool) ===
    public static final BooleanField EnableStoreAndForward = new BooleanField(META, "EnableStoreAndForward");
    public static final StringField SpoolDirectory = new StringField(META, "SpoolDirectory");
    public static final LongField SpoolMaxBytes = new LongField(META, "SpoolMaxBytes");
    public static final DoubleField SpoolHighWatermarkPct = new DoubleField(META, "SpoolHighWatermarkPct");
    public static final DoubleField SpoolLowWatermarkPct = new DoubleField(META, "SpoolLowWatermarkPct");
    public static final LongField SpoolReadMaxBytes = new LongField(META, "SpoolReadMaxBytes");

    // === Reliability Settings ===

    public static final IntField MaxRetries = new IntField(META, "MaxRetries");

    public static final LongField RetryBackoffMs = new LongField(META, "RetryBackoffMs");

    public static final LongField ConnectionTimeoutMs = new LongField(META, "ConnectionTimeoutMs");

    public static final LongField RequestTimeoutMs = new LongField(META, "RequestTimeoutMs");

    // === Data Mapping Settings ===

    public static final BooleanField IncludeQuality = new BooleanField(META, "IncludeQuality");

    public static final BooleanField OnlyOnChange = new BooleanField(META, "OnlyOnChange");

    public static final DoubleField NumericDeadband = new DoubleField(META, "NumericDeadband");

    // === Category Definitions for UI Grouping ===

    static {
        // Configure i18n keys for all fields
        // Module Control
        Enabled.getFormMeta()
            .setFieldNameKey("ZerobusSettings.Enabled.Name")
            .setFieldDescriptionKey("ZerobusSettings.Enabled.desc");
        DebugLogging.getFormMeta()
            .setFieldNameKey("ZerobusSettings.DebugLogging.Name")
            .setFieldDescriptionKey("ZerobusSettings.DebugLogging.desc");

        // Databricks Connection
        WorkspaceUrl.getFormMeta()
            .setFieldNameKey("ZerobusSettings.WorkspaceUrl.Name")
            .setFieldDescriptionKey("ZerobusSettings.WorkspaceUrl.desc");
        ZerobusEndpoint.getFormMeta()
            .setFieldNameKey("ZerobusSettings.ZerobusEndpoint.Name")
            .setFieldDescriptionKey("ZerobusSettings.ZerobusEndpoint.desc");
        OauthClientId.getFormMeta()
            .setFieldNameKey("ZerobusSettings.OauthClientId.Name")
            .setFieldDescriptionKey("ZerobusSettings.OauthClientId.desc");
        OauthClientSecret.getFormMeta()
            .setFieldNameKey("ZerobusSettings.OauthClientSecret.Name")
            .setFieldDescriptionKey("ZerobusSettings.OauthClientSecret.desc")
            .setEditorSource(new MaskedPasswordEditorSource(55));

        // Unity Catalog
        TargetTable.getFormMeta()
            .setFieldNameKey("ZerobusSettings.TargetTable.Name")
            .setFieldDescriptionKey("ZerobusSettings.TargetTable.desc");
        SourceSystemId.getFormMeta()
            .setFieldNameKey("ZerobusSettings.SourceSystemId.Name")
            .setFieldDescriptionKey("ZerobusSettings.SourceSystemId.desc");

        // Tag Selection
        EnableDirectSubscriptions.getFormMeta()
            .setFieldNameKey("ZerobusSettings.EnableDirectSubscriptions.Name")
            .setFieldDescriptionKey("ZerobusSettings.EnableDirectSubscriptions.desc");
        TagSelectionMode.getFormMeta()
            .setFieldNameKey("ZerobusSettings.TagSelectionMode.Name")
            .setFieldDescriptionKey("ZerobusSettings.TagSelectionMode.desc");
        TagFolderPath.getFormMeta()
            .setFieldNameKey("ZerobusSettings.TagFolderPath.Name")
            .setFieldDescriptionKey("ZerobusSettings.TagFolderPath.desc");
        TagPathPattern.getFormMeta()
            .setFieldNameKey("ZerobusSettings.TagPathPattern.Name")
            .setFieldDescriptionKey("ZerobusSettings.TagPathPattern.desc");
        ExplicitTagPaths.getFormMeta()
            .setFieldNameKey("ZerobusSettings.ExplicitTagPaths.Name")
            .setFieldDescriptionKey("ZerobusSettings.ExplicitTagPaths.desc");
        IncludeSubfolders.getFormMeta()
            .setFieldNameKey("ZerobusSettings.IncludeSubfolders.Name")
            .setFieldDescriptionKey("ZerobusSettings.IncludeSubfolders.desc");

        // Performance & Batching
        BatchSize.getFormMeta()
            .setFieldNameKey("ZerobusSettings.BatchSize.Name")
            .setFieldDescriptionKey("ZerobusSettings.BatchSize.desc");
        BatchFlushIntervalMs.getFormMeta()
            .setFieldNameKey("ZerobusSettings.BatchFlushIntervalMs.Name")
            .setFieldDescriptionKey("ZerobusSettings.BatchFlushIntervalMs.desc");
        MaxQueueSize.getFormMeta()
            .setFieldNameKey("ZerobusSettings.MaxQueueSize.Name")
            .setFieldDescriptionKey("ZerobusSettings.MaxQueueSize.desc");
        MaxEventsPerSecond.getFormMeta()
            .setFieldNameKey("ZerobusSettings.MaxEventsPerSecond.Name")
            .setFieldDescriptionKey("ZerobusSettings.MaxEventsPerSecond.desc");

        // Store-and-forward
        EnableStoreAndForward.getFormMeta()
            .setFieldNameKey("ZerobusSettings.EnableStoreAndForward.Name")
            .setFieldDescriptionKey("ZerobusSettings.EnableStoreAndForward.desc");
        SpoolDirectory.getFormMeta()
            .setFieldNameKey("ZerobusSettings.SpoolDirectory.Name")
            .setFieldDescriptionKey("ZerobusSettings.SpoolDirectory.desc");
        SpoolMaxBytes.getFormMeta()
            .setFieldNameKey("ZerobusSettings.SpoolMaxBytes.Name")
            .setFieldDescriptionKey("ZerobusSettings.SpoolMaxBytes.desc");
        SpoolHighWatermarkPct.getFormMeta()
            .setFieldNameKey("ZerobusSettings.SpoolHighWatermarkPct.Name")
            .setFieldDescriptionKey("ZerobusSettings.SpoolHighWatermarkPct.desc");
        SpoolLowWatermarkPct.getFormMeta()
            .setFieldNameKey("ZerobusSettings.SpoolLowWatermarkPct.Name")
            .setFieldDescriptionKey("ZerobusSettings.SpoolLowWatermarkPct.desc");
        SpoolReadMaxBytes.getFormMeta()
            .setFieldNameKey("ZerobusSettings.SpoolReadMaxBytes.Name")
            .setFieldDescriptionKey("ZerobusSettings.SpoolReadMaxBytes.desc");

        // Reliability
        MaxRetries.getFormMeta()
            .setFieldNameKey("ZerobusSettings.MaxRetries.Name")
            .setFieldDescriptionKey("ZerobusSettings.MaxRetries.desc");
        RetryBackoffMs.getFormMeta()
            .setFieldNameKey("ZerobusSettings.RetryBackoffMs.Name")
            .setFieldDescriptionKey("ZerobusSettings.RetryBackoffMs.desc");
        ConnectionTimeoutMs.getFormMeta()
            .setFieldNameKey("ZerobusSettings.ConnectionTimeoutMs.Name")
            .setFieldDescriptionKey("ZerobusSettings.ConnectionTimeoutMs.desc");
        RequestTimeoutMs.getFormMeta()
            .setFieldNameKey("ZerobusSettings.RequestTimeoutMs.Name")
            .setFieldDescriptionKey("ZerobusSettings.RequestTimeoutMs.desc");

        // Data Mapping
        IncludeQuality.getFormMeta()
            .setFieldNameKey("ZerobusSettings.IncludeQuality.Name")
            .setFieldDescriptionKey("ZerobusSettings.IncludeQuality.desc");
        OnlyOnChange.getFormMeta()
            .setFieldNameKey("ZerobusSettings.OnlyOnChange.Name")
            .setFieldDescriptionKey("ZerobusSettings.OnlyOnChange.desc");
        NumericDeadband.getFormMeta()
            .setFieldNameKey("ZerobusSettings.NumericDeadband.Name")
            .setFieldDescriptionKey("ZerobusSettings.NumericDeadband.desc");

        // Set default values
        // Module Control Category
        Enabled.setDefault(false);
        DebugLogging.setDefault(false);

        // Databricks Connection Category
        WorkspaceUrl.setDefault("");
        ZerobusEndpoint.setDefault("");
        OauthClientId.setDefault("");
        OauthClientSecret.setDefault("");

        // Unity Catalog Category
        TargetTable.setDefault("");
        SourceSystemId.setDefault("ignition-gateway");

        // Tag Selection Category
        EnableDirectSubscriptions.setDefault(true);
        TagSelectionMode.setDefault("explicit");
        TagFolderPath.setDefault("");
        TagPathPattern.setDefault("");
        IncludeSubfolders.setDefault(true);

        // Performance Category
        BatchSize.setDefault(200);
        BatchFlushIntervalMs.setDefault(500L);
        MaxQueueSize.setDefault(10000);
        MaxEventsPerSecond.setDefault(10000);

        // Store-and-forward defaults
        EnableStoreAndForward.setDefault(false);
        SpoolDirectory.setDefault("data/zerobus-spool");
        SpoolMaxBytes.setDefault(1024L * 1024 * 1024);
        SpoolHighWatermarkPct.setDefault(0.85);
        SpoolLowWatermarkPct.setDefault(0.70);
        SpoolReadMaxBytes.setDefault(2L * 1024 * 1024);

        // Reliability Category
        MaxRetries.setDefault(3);
        RetryBackoffMs.setDefault(1000L);
        ConnectionTimeoutMs.setDefault(30000L);
        RequestTimeoutMs.setDefault(60000L);

        // Data Mapping Category
        IncludeQuality.setDefault(true);
        OnlyOnChange.setDefault(true);
        NumericDeadband.setDefault(0.0);
    }

    // Note: Category grouping can be added later with a custom StatusPageHook
    // For now, all fields will appear in a single list in the Gateway Config UI

    @Override
    public RecordMeta<ZerobusSettings> getMeta() {
        return META;
    }

    /**
     * Convert this PersistentRecord to a ConfigModel for use by the module.
     *
     * @return ConfigModel instance populated from this record
     */
    public ConfigModel toConfigModel() {
        ConfigModel config = new ConfigModel();

        // Module Control
        config.setEnabled(getBoolean(Enabled));
        config.setDebugLogging(getBoolean(DebugLogging));

        // Databricks Connection
        config.setWorkspaceUrl(getString(WorkspaceUrl));
        config.setZerobusEndpoint(getString(ZerobusEndpoint));
        config.setOauthClientId(getString(OauthClientId));
        config.setOauthClientSecret(getString(OauthClientSecret));

        // Unity Catalog
        config.setTargetTable(getString(TargetTable));
        config.setSourceSystemId(getString(SourceSystemId));

        // Tag Selection
        config.setEnableDirectSubscriptions(getBoolean(EnableDirectSubscriptions));
        config.setTagSelectionMode(getString(TagSelectionMode));
        config.setTagFolderPath(getString(TagFolderPath));
        config.setTagPathPattern(getString(TagPathPattern));
        config.setIncludeSubfolders(getBoolean(IncludeSubfolders));

        // Explicit tag paths (stored as comma-separated string)
        String tagPathsStr = getString(ExplicitTagPaths);
        List<String> tagPaths = new ArrayList<>();
        if (tagPathsStr != null && !tagPathsStr.isEmpty()) {
            tagPaths = Arrays.asList(tagPathsStr.split(","));
        }
        config.setExplicitTagPaths(tagPaths);

        // Batching & Performance
        config.setBatchSize(getInt(BatchSize));
        config.setBatchFlushIntervalMs(getLong(BatchFlushIntervalMs));
        config.setMaxQueueSize(getInt(MaxQueueSize));
        config.setMaxEventsPerSecond(getInt(MaxEventsPerSecond));

        // Store-and-forward
        config.setEnableStoreAndForward(getBoolean(EnableStoreAndForward));
        config.setSpoolDirectory(getString(SpoolDirectory));
        config.setSpoolMaxBytes(getLong(SpoolMaxBytes));
        config.setSpoolHighWatermarkPct(getDouble(SpoolHighWatermarkPct));
        config.setSpoolLowWatermarkPct(getDouble(SpoolLowWatermarkPct));
        config.setSpoolReadMaxBytes(getLong(SpoolReadMaxBytes));

        // Reliability
        config.setMaxRetries(getInt(MaxRetries));
        config.setRetryBackoffMs(getLong(RetryBackoffMs));
        config.setConnectionTimeoutMs(getLong(ConnectionTimeoutMs));
        config.setRequestTimeoutMs(getLong(RequestTimeoutMs));

        // Data Mapping
        config.setIncludeQuality(getBoolean(IncludeQuality));
        config.setOnlyOnChange(getBoolean(OnlyOnChange));
        config.setNumericDeadband(getDouble(NumericDeadband));

        return config;
    }

    /**
     * Update this PersistentRecord from a ConfigModel.
     *
     * @param config ConfigModel to copy values from
     */
    public void fromConfigModel(ConfigModel config) {
        // Module Control
        setBoolean(Enabled, config.isEnabled());
        setBoolean(DebugLogging, config.isDebugLogging());

        // Databricks Connection
        setString(WorkspaceUrl, config.getWorkspaceUrl());
        setString(ZerobusEndpoint, config.getZerobusEndpoint());
        setString(OauthClientId, config.getOauthClientId());
        setString(OauthClientSecret, config.getOauthClientSecret());

        // Unity Catalog
        setString(TargetTable, config.getTargetTable());
        setString(SourceSystemId, config.getSourceSystemId());

        // Tag Selection
        setBoolean(EnableDirectSubscriptions, config.isEnableDirectSubscriptions());
        setString(TagSelectionMode, config.getTagSelectionMode());
        setString(TagFolderPath, config.getTagFolderPath());
        setString(TagPathPattern, config.getTagPathPattern());
        setBoolean(IncludeSubfolders, config.isIncludeSubfolders());

        // Explicit tag paths (store as comma-separated string)
        String tagPathsStr = String.join(",", config.getExplicitTagPaths());
        setString(ExplicitTagPaths, tagPathsStr);

        // Batching & Performance
        setInt(BatchSize, config.getBatchSize());
        setLong(BatchFlushIntervalMs, config.getBatchFlushIntervalMs());
        setInt(MaxQueueSize, config.getMaxQueueSize());
        setInt(MaxEventsPerSecond, config.getMaxEventsPerSecond());

        // Store-and-forward
        setBoolean(EnableStoreAndForward, config.isEnableStoreAndForward());
        setString(SpoolDirectory, config.getSpoolDirectory());
        setLong(SpoolMaxBytes, config.getSpoolMaxBytes());
        setDouble(SpoolHighWatermarkPct, config.getSpoolHighWatermarkPct());
        setDouble(SpoolLowWatermarkPct, config.getSpoolLowWatermarkPct());
        setLong(SpoolReadMaxBytes, config.getSpoolReadMaxBytes());

        // Reliability
        setInt(MaxRetries, config.getMaxRetries());
        setLong(RetryBackoffMs, config.getRetryBackoffMs());
        setLong(ConnectionTimeoutMs, config.getConnectionTimeoutMs());
        setLong(RequestTimeoutMs, config.getRequestTimeoutMs());

        // Data Mapping
        setBoolean(IncludeQuality, config.isIncludeQuality());
        setBoolean(OnlyOnChange, config.isOnlyOnChange());
        setDouble(NumericDeadband, config.getNumericDeadband());
    }

}
