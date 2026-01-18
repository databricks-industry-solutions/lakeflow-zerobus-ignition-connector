package com.example.ignition.zerobus;

import com.inductiveautomation.ignition.gateway.localdb.persistence.BooleanField;
import com.inductiveautomation.ignition.gateway.localdb.persistence.DoubleField;
import com.inductiveautomation.ignition.gateway.localdb.persistence.EncodedStringField;
import com.inductiveautomation.ignition.gateway.localdb.persistence.IntField;
import com.inductiveautomation.ignition.gateway.localdb.persistence.LongField;
import com.inductiveautomation.ignition.gateway.localdb.persistence.PersistentRecord;
import com.inductiveautomation.ignition.gateway.localdb.persistence.RecordMeta;
import com.inductiveautomation.ignition.gateway.localdb.persistence.StringField;
import simpleorm.dataset.SFieldFlags;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Ignition 8.3 PersistentRecord for configuration persistence.
 *
 * Note: Ignition 8.3 removed the old Wicket FormMeta-based UI generation, so this record is
 * used only for persistence. The UI is served at /system/zerobus/configure.
 */
public class ZerobusSettings83 extends PersistentRecord {
    public static final RecordMeta<ZerobusSettings83> META = new RecordMeta<>(
        ZerobusSettings83.class,
        "ZerobusSettings"
    );

    // Module Control
    public static final BooleanField Enabled = new BooleanField(META, "Enabled", SFieldFlags.SMANDATORY);
    public static final BooleanField DebugLogging = new BooleanField(META, "DebugLogging");

    // Databricks Connection
    public static final StringField WorkspaceUrl = new StringField(META, "WorkspaceUrl", SFieldFlags.SMANDATORY);
    public static final StringField ZerobusEndpoint = new StringField(META, "ZerobusEndpoint", SFieldFlags.SMANDATORY);
    public static final StringField OauthClientId = new StringField(META, "OauthClientId", SFieldFlags.SMANDATORY);
    public static final EncodedStringField OauthClientSecret = new EncodedStringField(META, "OauthClientSecret");

    // Unity Catalog / Mapping
    public static final StringField TargetTable = new StringField(META, "TargetTable", SFieldFlags.SMANDATORY);
    public static final StringField SourceSystemId = new StringField(META, "SourceSystemId");

    // Tag Selection
    public static final BooleanField EnableDirectSubscriptions = new BooleanField(META, "EnableDirectSubscriptions");
    public static final StringField TagSelectionMode = new StringField(META, "TagSelectionMode");
    public static final StringField TagFolderPath = new StringField(META, "TagFolderPath");
    public static final StringField TagPathPattern = new StringField(META, "TagPathPattern");
    public static final StringField ExplicitTagPaths = new StringField(META, "ExplicitTagPaths"); // comma-separated
    public static final BooleanField IncludeSubfolders = new BooleanField(META, "IncludeSubfolders");

    // Performance
    public static final IntField BatchSize = new IntField(META, "BatchSize");
    public static final LongField BatchFlushIntervalMs = new LongField(META, "BatchFlushIntervalMs");
    public static final IntField MaxQueueSize = new IntField(META, "MaxQueueSize");
    public static final IntField MaxEventsPerSecond = new IntField(META, "MaxEventsPerSecond");

    // Store-and-forward (disk spool)
    public static final BooleanField EnableStoreAndForward = new BooleanField(META, "EnableStoreAndForward");
    public static final StringField SpoolDirectory = new StringField(META, "SpoolDirectory");
    public static final LongField SpoolMaxBytes = new LongField(META, "SpoolMaxBytes");
    public static final DoubleField SpoolHighWatermarkPct = new DoubleField(META, "SpoolHighWatermarkPct");
    public static final DoubleField SpoolLowWatermarkPct = new DoubleField(META, "SpoolLowWatermarkPct");
    public static final LongField SpoolReadMaxBytes = new LongField(META, "SpoolReadMaxBytes");

    // Reliability
    public static final IntField MaxRetries = new IntField(META, "MaxRetries");
    public static final LongField RetryBackoffMs = new LongField(META, "RetryBackoffMs");
    public static final LongField ConnectionTimeoutMs = new LongField(META, "ConnectionTimeoutMs");
    public static final LongField RequestTimeoutMs = new LongField(META, "RequestTimeoutMs");

    // Filtering
    public static final BooleanField IncludeQuality = new BooleanField(META, "IncludeQuality");
    public static final BooleanField OnlyOnChange = new BooleanField(META, "OnlyOnChange");
    public static final DoubleField NumericDeadband = new DoubleField(META, "NumericDeadband");

    static {
        // Defaults aligned with ConfigModel defaults
        Enabled.setDefault(false);
        DebugLogging.setDefault(false);
        WorkspaceUrl.setDefault("");
        ZerobusEndpoint.setDefault("");
        OauthClientId.setDefault("");
        OauthClientSecret.setDefault("");
        TargetTable.setDefault("");
        SourceSystemId.setDefault("ignition-gateway");
        EnableDirectSubscriptions.setDefault(true);
        TagSelectionMode.setDefault("explicit");
        TagFolderPath.setDefault("");
        TagPathPattern.setDefault("");
        IncludeSubfolders.setDefault(true);
        BatchSize.setDefault(200);
        BatchFlushIntervalMs.setDefault(500L);
        MaxQueueSize.setDefault(10000);
        MaxEventsPerSecond.setDefault(10000);
        EnableStoreAndForward.setDefault(false);
        SpoolDirectory.setDefault("data/zerobus-spool");
        SpoolMaxBytes.setDefault(1024L * 1024 * 1024);
        SpoolHighWatermarkPct.setDefault(0.85);
        SpoolLowWatermarkPct.setDefault(0.70);
        SpoolReadMaxBytes.setDefault(2L * 1024 * 1024);
        MaxRetries.setDefault(3);
        RetryBackoffMs.setDefault(1000L);
        ConnectionTimeoutMs.setDefault(30000L);
        RequestTimeoutMs.setDefault(60000L);
        IncludeQuality.setDefault(true);
        OnlyOnChange.setDefault(true);
        NumericDeadband.setDefault(0.0);
    }

    @Override
    public RecordMeta<ZerobusSettings83> getMeta() {
        return META;
    }

    public ConfigModel toConfigModel() {
        ConfigModel config = new ConfigModel();
        config.setEnabled(getBoolean(Enabled));
        config.setDebugLogging(getBoolean(DebugLogging));
        config.setWorkspaceUrl(getString(WorkspaceUrl));
        config.setZerobusEndpoint(getString(ZerobusEndpoint));
        config.setOauthClientId(getString(OauthClientId));
        config.setOauthClientSecret(getString(OauthClientSecret));
        config.setTargetTable(getString(TargetTable));
        config.setSourceSystemId(getString(SourceSystemId));
        config.setEnableDirectSubscriptions(getBoolean(EnableDirectSubscriptions));
        config.setTagSelectionMode(getString(TagSelectionMode));
        config.setTagFolderPath(getString(TagFolderPath));
        config.setTagPathPattern(getString(TagPathPattern));
        config.setIncludeSubfolders(getBoolean(IncludeSubfolders));

        String tagPathsStr = getString(ExplicitTagPaths);
        List<String> tagPaths = new ArrayList<>();
        if (tagPathsStr != null && !tagPathsStr.isEmpty()) {
            tagPaths = Arrays.asList(tagPathsStr.split(","));
        }
        config.setExplicitTagPaths(tagPaths);

        config.setBatchSize(getInt(BatchSize));
        config.setBatchFlushIntervalMs(getLong(BatchFlushIntervalMs));
        config.setMaxQueueSize(getInt(MaxQueueSize));
        config.setMaxEventsPerSecond(getInt(MaxEventsPerSecond));
        config.setEnableStoreAndForward(getBoolean(EnableStoreAndForward));
        config.setSpoolDirectory(getString(SpoolDirectory));
        config.setSpoolMaxBytes(getLong(SpoolMaxBytes));
        config.setSpoolHighWatermarkPct(getDouble(SpoolHighWatermarkPct));
        config.setSpoolLowWatermarkPct(getDouble(SpoolLowWatermarkPct));
        config.setSpoolReadMaxBytes(getLong(SpoolReadMaxBytes));
        config.setMaxRetries(getInt(MaxRetries));
        config.setRetryBackoffMs(getLong(RetryBackoffMs));
        config.setConnectionTimeoutMs(getLong(ConnectionTimeoutMs));
        config.setRequestTimeoutMs(getLong(RequestTimeoutMs));
        config.setIncludeQuality(getBoolean(IncludeQuality));
        config.setOnlyOnChange(getBoolean(OnlyOnChange));
        config.setNumericDeadband(getDouble(NumericDeadband));
        return config;
    }

    public void fromConfigModel(ConfigModel config) {
        setBoolean(Enabled, config.isEnabled());
        setBoolean(DebugLogging, config.isDebugLogging());
        setString(WorkspaceUrl, config.getWorkspaceUrl());
        setString(ZerobusEndpoint, config.getZerobusEndpoint());
        setString(OauthClientId, config.getOauthClientId());
        setString(OauthClientSecret, config.getOauthClientSecret());
        setString(TargetTable, config.getTargetTable());
        setString(SourceSystemId, config.getSourceSystemId());
        setBoolean(EnableDirectSubscriptions, config.isEnableDirectSubscriptions());
        setString(TagSelectionMode, config.getTagSelectionMode());
        setString(TagFolderPath, config.getTagFolderPath());
        setString(TagPathPattern, config.getTagPathPattern());
        setBoolean(IncludeSubfolders, config.isIncludeSubfolders());
        setString(ExplicitTagPaths, String.join(",", config.getExplicitTagPaths()));

        setInt(BatchSize, config.getBatchSize());
        setLong(BatchFlushIntervalMs, config.getBatchFlushIntervalMs());
        setInt(MaxQueueSize, config.getMaxQueueSize());
        setInt(MaxEventsPerSecond, config.getMaxEventsPerSecond());
        setBoolean(EnableStoreAndForward, config.isEnableStoreAndForward());
        setString(SpoolDirectory, config.getSpoolDirectory());
        setLong(SpoolMaxBytes, config.getSpoolMaxBytes());
        setDouble(SpoolHighWatermarkPct, config.getSpoolHighWatermarkPct());
        setDouble(SpoolLowWatermarkPct, config.getSpoolLowWatermarkPct());
        setLong(SpoolReadMaxBytes, config.getSpoolReadMaxBytes());
        setInt(MaxRetries, config.getMaxRetries());
        setLong(RetryBackoffMs, config.getRetryBackoffMs());
        setLong(ConnectionTimeoutMs, config.getConnectionTimeoutMs());
        setLong(RequestTimeoutMs, config.getRequestTimeoutMs());
        setBoolean(IncludeQuality, config.isIncludeQuality());
        setBoolean(OnlyOnChange, config.isOnlyOnChange());
        setDouble(NumericDeadband, config.getNumericDeadband());
    }
}


