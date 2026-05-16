package com.example.ignition.zerobus;

import com.example.ignition.zerobus.proto.OTEvent;
import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.SQLException;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Postgres client manager for Lakebase sink mode.
 */
public class PostgresClientManager {

    private static final Logger logger = LoggerFactory.getLogger(PostgresClientManager.class);

    private final ConfigModel config;
    private volatile HikariDataSource dataSource;
    private final AtomicBoolean initialized = new AtomicBoolean(false);
    private final AtomicBoolean connected = new AtomicBoolean(false);

    private final AtomicLong totalEventsSent = new AtomicLong(0);
    private final AtomicLong totalBatchesSent = new AtomicLong(0);
    private final AtomicLong totalFailures = new AtomicLong(0);
    private volatile long lastSuccessfulSendTime = 0;
    private volatile String lastError = null;

    private static final long MAX_CONNECTION_LIFETIME_MS = 3L * 24 * 60 * 60 * 1000;
    private static final long IDLE_TIMEOUT_MS = 24L * 60 * 60 * 1000;
    private static final String POSTGRES_DRIVER_CLASS = "org.postgresql.Driver";

    private static final String INSERT_SQL =
            "INSERT INTO %s ("
                    + "event_id, event_time, tag_path, tag_provider, "
                    + "numeric_value, string_value, boolean_value, "
                    + "quality, quality_code, source_system, "
                    + "ingestion_timestamp, data_type, alarm_state, alarm_priority, "
                    + "sdt_compressed, compression_ratio, sdt_enabled, batch_bytes_sent"
                    + ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                    + "ON CONFLICT (event_id) DO NOTHING";

    public PostgresClientManager(ConfigModel config) {
        this.config = config;
    }

    public void initialize() throws Exception {
        if (initialized.get()) {
            logger.warn("PostgresClientManager already initialized");
            return;
        }

        logger.info("Initializing PostgreSQL client...");
        logger.info("  Host: {}", config.getPostgresHost());
        logger.info("  Port: {}", config.getPostgresPort());
        logger.info("  Database: {}", config.getPostgresDatabase());
        logger.info("  Table: {}", config.getPostgresTable());
        logger.info("  Pool Size: {}", config.getPostgresPoolSize());

        try {
            // Ignition module classloaders do not always auto-register JDBC drivers with DriverManager.
            Class.forName(POSTGRES_DRIVER_CLASS, true, getClass().getClassLoader());
            HikariConfig hikariConfig = new HikariConfig();
            String jdbcUrl = String.format(
                    "jdbc:postgresql://%s:%d/%s?sslmode=require",
                    config.getPostgresHost(),
                    config.getPostgresPort(),
                    config.getPostgresDatabase()
            );
            hikariConfig.setJdbcUrl(jdbcUrl);
            hikariConfig.setDriverClassName(POSTGRES_DRIVER_CLASS);
            hikariConfig.setUsername(config.getPostgresUser());
            hikariConfig.setPassword(config.getPostgresPassword());
            hikariConfig.setMaximumPoolSize(config.getPostgresPoolSize());
            hikariConfig.setMinimumIdle(1);
            hikariConfig.setMaxLifetime(MAX_CONNECTION_LIFETIME_MS);
            hikariConfig.setIdleTimeout(IDLE_TIMEOUT_MS);
            hikariConfig.setConnectionTimeout(config.getConnectionTimeoutMs());
            hikariConfig.setPoolName("Zerobus-Postgres-Pool");
            hikariConfig.setConnectionTestQuery("SELECT 1");
            dataSource = new HikariDataSource(hikariConfig);

            try (Connection conn = dataSource.getConnection()) {
                logger.info("PostgreSQL connection validated successfully");
            }

            initialized.set(true);
            connected.set(true);
            logger.info("PostgreSQL client initialized successfully");
        } catch (Exception e) {
            logger.error("Failed to initialize PostgreSQL client", e);
            lastError = e.getMessage();
            throw e;
        }
    }

    public void shutdown() {
        if (!initialized.get()) {
            return;
        }
        logger.info("Shutting down PostgreSQL client...");
        try {
            if (dataSource != null && !dataSource.isClosed()) {
                dataSource.close();
            }
        } catch (Exception e) {
            logger.warn("Error closing PostgreSQL connection pool", e);
        } finally {
            dataSource = null;
            initialized.set(false);
            connected.set(false);
        }
        logger.info("PostgreSQL client shut down successfully");
    }

    public boolean sendOtEvents(List<OTEvent> events) {
        if (!ensureConnected()) {
            logger.warn("Cannot send events - PostgreSQL client not initialized or not connected");
            return false;
        }
        if (events == null || events.isEmpty()) {
            return true;
        }

        String insertSql = String.format(INSERT_SQL, config.getPostgresTable());
        try (Connection conn = dataSource.getConnection(); PreparedStatement stmt = conn.prepareStatement(insertSql)) {
            conn.setAutoCommit(false);
            for (OTEvent event : events) {
                int idx = 1;
                stmt.setString(idx++, event.getEventId());
                stmt.setLong(idx++, event.getEventTime());
                stmt.setString(idx++, event.getTagPath());
                stmt.setString(idx++, event.getTagProvider());
                if (event.hasNumericValue()) {
                    stmt.setDouble(idx++, event.getNumericValue());
                } else {
                    stmt.setNull(idx++, java.sql.Types.DOUBLE);
                }
                stmt.setString(idx++, event.getStringValue().isEmpty() ? null : event.getStringValue());
                if (event.hasBooleanValue()) {
                    stmt.setBoolean(idx++, event.getBooleanValue());
                } else {
                    stmt.setNull(idx++, java.sql.Types.BOOLEAN);
                }
                stmt.setString(idx++, event.getQuality());
                stmt.setInt(idx++, event.getQualityCode());
                stmt.setString(idx++, event.getSourceSystem());
                stmt.setLong(idx++, event.getIngestionTimestamp());
                stmt.setString(idx++, event.getDataType().isEmpty() ? null : event.getDataType());
                stmt.setString(idx++, event.getAlarmState().isEmpty() ? null : event.getAlarmState());
                if (event.getAlarmPriority() != 0) {
                    stmt.setInt(idx++, event.getAlarmPriority());
                } else {
                    stmt.setNull(idx++, java.sql.Types.INTEGER);
                }
                stmt.setBoolean(idx++, event.getSdtCompressed());
                if (event.getCompressionRatio() != 0.0) {
                    stmt.setDouble(idx++, event.getCompressionRatio());
                } else {
                    stmt.setNull(idx++, java.sql.Types.DOUBLE);
                }
                stmt.setBoolean(idx++, event.getSdtEnabled());
                if (event.getBatchBytesSent() != 0) {
                    stmt.setLong(idx++, event.getBatchBytesSent());
                } else {
                    stmt.setNull(idx++, java.sql.Types.BIGINT);
                }
                stmt.addBatch();
            }

            int[] results = stmt.executeBatch();
            conn.commit();

            int insertedCount = 0;
            for (int result : results) {
                if (result >= 0 || result == PreparedStatement.SUCCESS_NO_INFO) {
                    insertedCount++;
                }
            }
            totalEventsSent.addAndGet(insertedCount);
            totalBatchesSent.incrementAndGet();
            lastSuccessfulSendTime = System.currentTimeMillis();
            return true;
        } catch (SQLException e) {
            logger.error("Failed to send events to PostgreSQL", e);
            lastError = e.getMessage();
            totalFailures.incrementAndGet();
            connected.set(false);
            return false;
        }
    }

    public Optional<String> testConnection() {
        logger.info("Testing PostgreSQL connection...");
        try {
            Class.forName(POSTGRES_DRIVER_CLASS, true, getClass().getClassLoader());
            HikariConfig testConfig = new HikariConfig();
            String jdbcUrl = String.format(
                    "jdbc:postgresql://%s:%d/%s?sslmode=require",
                    config.getPostgresHost(),
                    config.getPostgresPort(),
                    config.getPostgresDatabase()
            );
            testConfig.setJdbcUrl(jdbcUrl);
            testConfig.setDriverClassName(POSTGRES_DRIVER_CLASS);
            testConfig.setUsername(config.getPostgresUser());
            testConfig.setPassword(config.getPostgresPassword());
            testConfig.setMaximumPoolSize(1);
            testConfig.setConnectionTimeout(10000);
            testConfig.setPoolName("Zerobus-Postgres-Test");

            try (HikariDataSource testDs = new HikariDataSource(testConfig);
                 Connection conn = testDs.getConnection()) {
                try (var stmt = conn.createStatement(); var rs = stmt.executeQuery("SELECT 1")) {
                    if (rs.next()) {
                        return Optional.empty();
                    }
                }
            }
            return Optional.of("Query returned no results");
        } catch (Exception e) {
            logger.error("PostgreSQL connection test failed", e);
            lastError = e.getMessage();
            return Optional.of(e.getMessage() != null ? e.getMessage() : e.getClass().getSimpleName());
        }
    }

    private boolean ensureConnected() {
        if (!config.isEnabled() || !config.isEnablePostgresSink()) {
            return false;
        }
        if (initialized.get() && connected.get()) {
            return true;
        }
        try {
            if (dataSource != null && !dataSource.isClosed()) {
                try (Connection conn = dataSource.getConnection()) {
                    connected.set(true);
                    return true;
                }
            }
            shutdown();
            initialize();
            return connected.get();
        } catch (Exception e) {
            logger.error("Failed to reconnect to PostgreSQL", e);
            lastError = e.getMessage();
            connected.set(false);
            return false;
        }
    }

    public boolean isReadyToSend() {
        return initialized.get() && connected.get();
    }

    public boolean tryEnsureConnected() {
        return ensureConnected();
    }

    private static final ZoneId AEDT_ZONE = ZoneId.of("Australia/Sydney");
    private static final DateTimeFormatter AEDT_FMT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss z").withZone(AEDT_ZONE);

    private String formatTimestamp(long epochMs) {
        long secondsAgo = (System.currentTimeMillis() - epochMs) / 1000;
        String aedt = AEDT_FMT.format(Instant.ofEpochMilli(epochMs));
        return secondsAgo + " seconds ago (" + aedt + ")";
    }

    public String getDiagnostics() {
        StringBuilder sb = new StringBuilder();
        sb.append("=== PostgreSQL Client Diagnostics ===\n");
        sb.append("Initialized: ").append(initialized.get()).append("\n");
        sb.append("Connected: ").append(connected.get()).append("\n");
        sb.append("Host: ").append(config.getPostgresHost()).append("\n");
        sb.append("Port: ").append(config.getPostgresPort()).append("\n");
        sb.append("Database: ").append(config.getPostgresDatabase()).append("\n");
        sb.append("Table: ").append(config.getPostgresTable()).append("\n");
        if (dataSource != null && !dataSource.isClosed()) {
            sb.append("Pool - Active: ").append(dataSource.getHikariPoolMXBean().getActiveConnections()).append("\n");
            sb.append("Pool - Idle: ").append(dataSource.getHikariPoolMXBean().getIdleConnections()).append("\n");
            sb.append("Pool - Total: ").append(dataSource.getHikariPoolMXBean().getTotalConnections()).append("\n");
        }
        sb.append("Total Events Sent: ").append(totalEventsSent.get()).append("\n");
        sb.append("Total Batches Sent: ").append(totalBatchesSent.get()).append("\n");
        sb.append("Total Failures: ").append(totalFailures.get()).append("\n");
        if (lastSuccessfulSendTime > 0) {
            sb.append("Last Successful Send: ").append(formatTimestamp(lastSuccessfulSendTime)).append("\n");
        } else {
            sb.append("Last Successful Send: Never\n");
        }
        if (lastError != null) {
            sb.append("Last Error: ").append(lastError).append("\n");
        }
        sb.append("Diagnostics Generated: ").append(AEDT_FMT.format(Instant.now())).append("\n");
        return sb.toString();
    }
}
