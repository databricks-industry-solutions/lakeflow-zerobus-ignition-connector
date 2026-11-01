package com.example.ignition.zerobus;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for {@link PostgresClientManager#buildInsertSql(ConfigModel)} — the
 * config-driven INSERT statement used by the Lakebase sink.
 *
 * These lock in the two dimensions that vary by config (timestamp mode and
 * ON CONFLICT target) while guaranteeing the 18-column list and the 18
 * placeholder binds stay aligned with the bind loop in sendOtEvents().
 */
public class PostgresInsertSqlTest {

    private static int countOccurrences(String haystack, String needle) {
        int count = 0, i = 0;
        while ((i = haystack.indexOf(needle, i)) >= 0) {
            count++;
            i += needle.length();
        }
        return count;
    }

    @Test
    public void defaultsPreserveLegacyBehavior() {
        ConfigModel cfg = new ConfigModel();
        String sql = PostgresClientManager.buildInsertSql(cfg);

        assertTrue(sql.contains("ON CONFLICT (event_id) DO NOTHING"),
                "Default conflict target must remain the single event_id column");
        assertFalse(sql.contains("to_timestamp"),
                "Default (EPOCH_MICROS) mode must bind raw epoch, not wrap in to_timestamp");
        // 18 bound parameters, all bare '?'
        assertEquals(18, countOccurrences(sql, "?"),
                "Must have exactly 18 placeholders to match the bind loop");
    }

    @Test
    public void timestamptzModeWrapsBothTimeColumns() {
        ConfigModel cfg = new ConfigModel();
        cfg.setPostgresTimestampMode(ConfigModel.PostgresTimestampMode.TIMESTAMPTZ);
        String sql = PostgresClientManager.buildInsertSql(cfg);

        // Exactly the two epoch columns (event_time, ingestion_timestamp) are converted.
        assertEquals(2, countOccurrences(sql, "to_timestamp(?/1000000.0)"),
                "TIMESTAMPTZ mode must convert exactly the two epoch-micros columns");
        // Total binds unchanged: 16 bare '?' + 2 inside to_timestamp() = 18.
        assertEquals(18, countOccurrences(sql, "?"),
                "Bind count must stay 18 regardless of timestamp mode");
    }

    @Test
    public void compositeConflictTargetForChronoTable() {
        ConfigModel cfg = new ConfigModel();
        cfg.setPostgresConflictColumns("event_time, event_id");
        String sql = PostgresClientManager.buildInsertSql(cfg);

        assertTrue(sql.contains("ON CONFLICT (event_time, event_id) DO NOTHING"),
                "Composite conflict target (required by a partitioned ChronoTable) must be honored");
    }

    @Test
    public void lakeTsProfileCombinesBothKnobs() {
        // The exact combination a LakeTS ChronoTable target needs.
        ConfigModel cfg = new ConfigModel();
        cfg.setPostgresTable("ignition_tag_events");
        cfg.setPostgresTimestampMode(ConfigModel.PostgresTimestampMode.TIMESTAMPTZ);
        cfg.setPostgresConflictColumns("event_time, event_id");
        String sql = String.format(PostgresClientManager.buildInsertSql(cfg), cfg.getPostgresTable());

        assertTrue(sql.startsWith("INSERT INTO ignition_tag_events ("));
        assertEquals(2, countOccurrences(sql, "to_timestamp(?/1000000.0)"));
        assertTrue(sql.contains("ON CONFLICT (event_time, event_id) DO NOTHING"));
        assertEquals(18, countOccurrences(sql, "?"));
    }

    @Test
    public void blankConflictColumnsFallBackToEventId() {
        ConfigModel cfg = new ConfigModel();
        cfg.setPostgresConflictColumns("   ");
        assertEquals("event_id", cfg.getPostgresConflictColumns(),
                "Blank conflict columns must fall back to event_id");
        String sql = PostgresClientManager.buildInsertSql(cfg);
        assertTrue(sql.contains("ON CONFLICT (event_id) DO NOTHING"));
    }
}
