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
 * PostgresClientManager - Manages connections to PostgreSQL (Databricks Lakebase).
 *
 * Responsibilities:
 * - Manage HikariCP connection pool with SSL
 * - Batch insert events to PostgreSQL
 * - Handle connection lifecycle limits (Lakebase: 3-day max, 24-hour idle)
 * - Provide diagnostics and metrics
 */
public class PostgresClientManager {

    private static final Logger logger = LoggerFactory.getLogger(PostgresClientManager.class);

    private final ConfigModel config;
    private volatile HikariDataSource dataSource;
    private final AtomicBoolean initialized = new AtomicBoolean(false);
    private final AtomicBoolean connected = new AtomicBoolean(false);

    // Metrics
    private final AtomicLong totalEventsSent = new AtomicLong(0);
    private final AtomicLong totalBatchesSent = new AtomicLong(0);
    private final AtomicLong totalFailures = new AtomicLong(0);
    private volatile long lastSuccessfulSendTime = 0;
    private volatile String lastError = null;

    // Lakebase connection limits (per Databricks Lakebase docs: 3-day max, 24-hour idle)
    private static final long MAX_CONNECTION_LIFETIME_MS = 3L * 24 * 60 * 60 * 1000; // 3 days
    private static final long IDLE_TIMEOUT_MS = 24L * 60 * 60 * 1000; // 24 hours

    /**
     * INSERT statement for raw_tags table.
     * Column order matches Delta table schema.
     */
    private static final String INSERT_SQL = """
        INSERT INTO %s (
            event_id, event_time, tag_path, tag_provider,
            numeric_value, string_value, boolean_value,
            quality, quality_code, source_system,
            ingestion_timestamp, data_type, alarm_state, alarm_priority,
            sdt_compressed, compression_ratio, sdt_enabled, batch_bytes_sent
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (event_id) DO NOTHING
        """;

    public PostgresClientManager(ConfigModel config) {
        this.config = config;
    }

    /**
     * Initialize the HikariCP connection pool.
     */
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
            HikariConfig hikariConfig = new HikariConfig();

            // JDBC URL with SSL required for Lakebase
            String jdbcUrl = String.format(
                "jdbc:postgresql://%s:%d/%s?sslmode=require",
                config.getPostgresHost(),
                config.getPostgresPort(),
                config.getPostgresDatabase()
            );
            hikariConfig.setJdbcUrl(jdbcUrl);
            hikariConfig.setUsername(config.getPostgresUser());
            hikariConfig.setPassword(config.getPostgresPassword());

            // Pool configuration
            hikariConfig.setMaximumPoolSize(config.getPostgresPoolSize());
            hikariConfig.setMinimumIdle(1);

            // Connection lifetime limits for Lakebase compliance
            hikariConfig.setMaxLifetime(MAX_CONNECTION_LIFETIME_MS);
            hikariConfig.setIdleTimeout(IDLE_TIMEOUT_MS);
            hikariConfig.setConnectionTimeout(config.getConnectionTimeoutMs());

            // Pool name for diagnostics
            hikariConfig.setPoolName("Zerobus-Postgres-Pool");

            // Connection validation
            hikariConfig.setConnectionTestQuery("SELECT 1");

            dataSource = new HikariDataSource(hikariConfig);

            // Validate connection works
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

    /**
     * Shutdown the connection pool.
     */
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

    /**
     * Send a batch of OT events to PostgreSQL.
     */
    public boolean sendOtEvents(List<OTEvent> events) {
        if (!ensureConnected()) {
            logger.warn("Cannot send events - PostgreSQL client not initialized or not connected");
            return false;
        }

        if (events == null || events.isEmpty()) {
            return true;
        }

        logger.debug("Sending batch of {} OT events to PostgreSQL", events.size());

        String insertSql = String.format(INSERT_SQL, config.getPostgresTable());

        try (Connection conn = dataSource.getConnection();
             PreparedStatement stmt = conn.prepareStatement(insertSql)) {

            conn.setAutoCommit(false);

            for (OTEvent event : events) {
                int idx = 1;
                stmt.setString(idx++, event.getEventId());
                stmt.setLong(idx++, event.getEventTime());
                stmt.setString(idx++, event.getTagPath());
                stmt.setString(idx++, event.getTagProvider());

                // Numeric value - handle null
                if (event.hasNumericValue()) {
                    stmt.setDouble(idx++, event.getNumericValue());
                } else {
                    stmt.setNull(idx++, java.sql.Types.DOUBLE);
                }

                // String value
                stmt.setString(idx++, event.getStringValue().isEmpty() ? null : event.getStringValue());

                // Boolean value - handle null
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

                // Alarm priority - handle default 0
                if (event.getAlarmPriority() != 0) {
                    stmt.setInt(idx++, event.getAlarmPriority());
                } else {
                    stmt.setNull(idx++, java.sql.Types.INTEGER);
                }

                stmt.setBoolean(idx++, event.getSdtCompressed());

                // Compression ratio - handle default 0
                if (event.getCompressionRatio() != 0.0) {
                    stmt.setDouble(idx++, event.getCompressionRatio());
                } else {
                    stmt.setNull(idx++, java.sql.Types.DOUBLE);
                }

                stmt.setBoolean(idx++, event.getSdtEnabled());

                // Batch bytes sent
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

            logger.debug("Successfully inserted {} events to PostgreSQL", insertedCount);
            return true;

        } catch (SQLException e) {
            logger.error("Failed to send events to PostgreSQL", e);
            lastError = e.getMessage();
            totalFailures.incrementAndGet();
            connected.set(false);
            return false;
        }
    }

    /**
     * Test the connection to PostgreSQL.
     */
    public Optional<String> testConnection() {
        logger.info("Testing PostgreSQL connection...");

        try {
            // Build a temporary data source for testing
            HikariConfig testConfig = new HikariConfig();
            String jdbcUrl = String.format(
                "jdbc:postgresql://%s:%d/%s?sslmode=require",
                config.getPostgresHost(),
                config.getPostgresPort(),
                config.getPostgresDatabase()
            );
            testConfig.setJdbcUrl(jdbcUrl);
            testConfig.setUsername(config.getPostgresUser());
            testConfig.setPassword(config.getPostgresPassword());
            testConfig.setMaximumPoolSize(1);
            testConfig.setConnectionTimeout(10000);
            testConfig.setPoolName("Zerobus-Postgres-Test");

            try (HikariDataSource testDs = new HikariDataSource(testConfig);
                 Connection conn = testDs.getConnection()) {

                // Verify we can query
                try (var stmt = conn.createStatement();
                     var rs = stmt.executeQuery("SELECT 1")) {
                    if (rs.next()) {
                        logger.info("PostgreSQL connection test successful");
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

    /**
     * Ensure we have a valid connection, attempting reconnection if needed.
     */
    private boolean ensureConnected() {
        if (!config.isEnabled() || !config.isEnablePostgresSink()) {
            return false;
        }

        if (initialized.get() && connected.get()) {
            return true;
        }

        // Attempt to reconnect
        try {
            if (dataSource != null && !dataSource.isClosed()) {
                try (Connection conn = dataSource.getConnection()) {
                    connected.set(true);
                    return true;
                }
            }

            // Full reinitialize
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

    public boolean isReadyToSend() {
        return initialized.get() && connected.get();
    }

    public boolean tryEnsureConnected() {
        return ensureConnected();
    }

    public String getLastError() {
        return lastError;
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
