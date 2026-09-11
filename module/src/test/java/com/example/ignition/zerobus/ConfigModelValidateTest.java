package com.example.ignition.zerobus;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Tests for the LakeTS ChronoTable guard in {@link ConfigModel#validate()}.
 *
 * TIMESTAMPTZ mode targets a partitioned ChronoTable, whose ON CONFLICT key must
 * include the partition column (event_time). Without it, every INSERT fails at
 * runtime with "no unique or exclusion constraint matching the ON CONFLICT
 * specification" — so validate() must reject that combination at save time.
 */
public class ConfigModelValidateTest {

    /** A ConfigModel that is otherwise valid for the Lakebase sink. */
    private static ConfigModel lakebaseConfig() {
        ConfigModel cfg = new ConfigModel();
        cfg.setEnabled(true);
        cfg.setSinkMode(ConfigModel.SinkMode.lakebase);
        cfg.setEnablePostgresSink(true);
        cfg.setPostgresHost("host.example.com");
        cfg.setPostgresPort(5432);
        cfg.setPostgresDatabase("databricks_postgres");
        cfg.setPostgresUser("ignition_writer");
        cfg.setPostgresPassword("pw");
        cfg.setPostgresTable("ignition_tag_events");
        cfg.setPostgresPoolSize(4);
        return cfg;
    }

    /** True if the ChronoTable guard error (not the generic format error) is present. */
    private static boolean guardFired(List<String> errors) {
        return errors.stream().anyMatch(e -> e.contains("TIMESTAMPTZ") && e.contains("event_time"));
    }

    @Test
    public void timestamptzWithoutEventTimeConflictIsRejected() {
        ConfigModel cfg = lakebaseConfig();
        cfg.setPostgresTimestampMode(ConfigModel.PostgresTimestampMode.TIMESTAMPTZ);
        // default conflict columns = "event_id" (missing the partition column)
        assertEquals("event_id", cfg.getPostgresConflictColumns());
        assertTrue(guardFired(cfg.validate()),
                "TIMESTAMPTZ + event_id-only conflict target must be rejected at validate()");
    }

    @Test
    public void timestamptzWithCompositeConflictIsAccepted() {
        ConfigModel cfg = lakebaseConfig();
        cfg.setPostgresTimestampMode(ConfigModel.PostgresTimestampMode.TIMESTAMPTZ);
        cfg.setPostgresConflictColumns("event_time, event_id");
        assertFalse(guardFired(cfg.validate()),
                "TIMESTAMPTZ with event_time in the conflict key must pass the guard");
    }

    @Test
    public void epochMicrosWithEventIdIsAccepted() {
        ConfigModel cfg = lakebaseConfig();
        // stock raw-tags profile: EPOCH_MICROS + event_id — the guard must not fire
        assertFalse(guardFired(cfg.validate()),
                "Legacy EPOCH_MICROS + event_id must not trip the ChronoTable guard");
    }

    @Test
    public void eventTimeDetectionIgnoresCaseAndWhitespace() {
        ConfigModel cfg = lakebaseConfig();
        cfg.setPostgresTimestampMode(ConfigModel.PostgresTimestampMode.TIMESTAMPTZ);
        cfg.setPostgresConflictColumns(" EVENT_TIME , event_id ");
        assertFalse(guardFired(cfg.validate()),
                "event_time detection must be case- and whitespace-insensitive");
    }
}
