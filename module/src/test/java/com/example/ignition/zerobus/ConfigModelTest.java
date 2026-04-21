package com.example.ignition.zerobus;

import com.example.ignition.zerobus.compression.SdtOverride;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

import java.util.Arrays;
import java.util.List;

/**
 * Unit tests for ConfigModel
 */
public class ConfigModelTest {
    
    private ConfigModel config;
    
    @BeforeEach
    public void setUp() {
        config = new ConfigModel();
    }
    
    @Test
    public void testDefaultValues() {
        assertFalse(config.isEnabled(), "Module should be disabled by default");
        assertEquals("", config.getWorkspaceUrl());
        assertEquals(500, config.getBatchSize());
        assertEquals(2000, config.getBatchFlushIntervalMs());
    }
    
    @Test
    public void testTableNameParsing() {
        config.setTargetTable("catalog1.schema1.table1");
        
        assertEquals("catalog1", config.getCatalogName());
        assertEquals("schema1", config.getSchemaName());
        assertEquals("table1", config.getTableName());
    }
    
    @Test
    public void testValidationWithMissingFields() {
        // When disabled, ConfigModel allows saving partial config so operators can incrementally configure.
        config.setEnabled(true);
        List<String> errors = config.validate();

        assertFalse(errors.isEmpty(), "Should have validation errors when enabled");
        assertTrue(errors.stream().anyMatch(e -> e.contains("Workspace URL")));
        assertTrue(errors.stream().anyMatch(e -> e.contains("Zerobus endpoint")));
        assertTrue(errors.stream().anyMatch(e -> e.contains("OAuth client ID")));
    }
    
    @Test
    public void testValidationWithValidConfig() {
        config.setWorkspaceUrl("https://workspace.databricks.com");
        config.setZerobusEndpoint("https://workspace.databricks.com/api/2.0/lakeflow/ingest");
        config.setOauthClientId("client-id");
        config.setOauthClientSecret("client-secret");
        config.setTargetTable("dev.bronze.events");
        config.setTagSelectionMode("folder");
        config.setTagFolderPath("[default]Production");
        
        List<String> errors = config.validate();
        
        assertTrue(errors.isEmpty(), "Valid config should have no errors");
    }
    
    @Test
    public void testValidationWithInvalidBatchSize() {
        config.setWorkspaceUrl("https://workspace.databricks.com");
        config.setZerobusEndpoint("https://workspace.databricks.com/api/2.0/lakeflow/ingest");
        config.setOauthClientId("client-id");
        config.setOauthClientSecret("client-secret");
        config.setTargetTable("dev.bronze.events");
        config.setTagSelectionMode("folder");
        config.setTagFolderPath("[default]Production");
        config.setBatchSize(20000); // Invalid: > 10000
        
        List<String> errors = config.validate();
        
        assertTrue(errors.stream().anyMatch(e -> e.contains("Batch size")));
    }
    
    @Test
    public void testRequiresRestart() {
        ConfigModel newConfig = new ConfigModel();
        
        // Same config - no restart needed
        assertFalse(config.requiresRestart(newConfig));
        
        // Different workspace URL - restart needed
        newConfig.setWorkspaceUrl("https://different.databricks.com");
        assertTrue(config.requiresRestart(newConfig));
        
        // Different batch size only - restart needed (batch size affects runtime batching behavior)
        newConfig = new ConfigModel();
        newConfig.setBatchSize(1000);
        assertTrue(config.requiresRestart(newConfig));
    }
    
    @Test
    public void testUpdateFrom() {
        ConfigModel newConfig = new ConfigModel();
        newConfig.setWorkspaceUrl("https://new-workspace.databricks.com");
        newConfig.setTargetTable("new.schema.table");
        newConfig.setBatchSize(1000);
        newConfig.setEnabled(true);
        
        config.updateFrom(newConfig);
        
        assertEquals("https://new-workspace.databricks.com", config.getWorkspaceUrl());
        assertEquals("new.schema.table", config.getTargetTable());
        assertEquals("new", config.getCatalogName());
        assertEquals("schema", config.getSchemaName());
        assertEquals("table", config.getTableName());
        assertEquals(1000, config.getBatchSize());
        assertTrue(config.isEnabled());
    }
    
    @Test
    public void testSdtDefaultValues() {
        assertFalse(config.isEnableSdtCompression(), "SDT should be disabled by default");
        assertEquals(1.0, config.getSdtDeviation());
        assertEquals(300, config.getSdtMaxIntervalSeconds());
        assertEquals("zerobus", config.getSinkMode());
        assertTrue(config.isEnableZerobusSink());
        assertFalse(config.isEnablePostgresSink());
    }

    @Test
    public void testSinkModeSetterEnforcesExclusiveFlags() {
        config.setSinkMode("lakebase");
        assertEquals("lakebase", config.getSinkMode());
        assertTrue(config.isEnablePostgresSink());
        assertFalse(config.isEnableZerobusSink());

        config.setSinkMode("zerobus");
        assertEquals("zerobus", config.getSinkMode());
        assertTrue(config.isEnableZerobusSink());
        assertFalse(config.isEnablePostgresSink());
    }

    @Test
    public void testLegacyFlagsNormalizeToLakebaseWhenModeMissing() {
        config.setSinkMode("");
        config.setEnableZerobusSink(false);
        config.setEnablePostgresSink(true);

        config.normalizeSinkConfiguration();

        assertEquals("lakebase", config.getSinkMode());
        assertTrue(config.isEnablePostgresSink());
        assertFalse(config.isEnableZerobusSink());
    }

    @Test
    public void testLakebaseModeValidationDoesNotRequireZerobusFields() {
        config.setEnabled(true);
        config.setSinkMode("lakebase");
        config.setPostgresHost("ep-example.databricks.com");
        config.setPostgresPort(5432);
        config.setPostgresDatabase("databricks_postgres");
        config.setPostgresUser("postgres_user");
        config.setPostgresPassword("postgres_secret");
        config.setPostgresTable("raw_tags");
        config.setPostgresPoolSize(5);
        config.setEnableDirectSubscriptions(false);

        List<String> errors = config.validate();
        assertFalse(errors.stream().anyMatch(e -> e.contains("Workspace URL")));
        assertFalse(errors.stream().anyMatch(e -> e.contains("Zerobus endpoint")));
        assertFalse(errors.stream().anyMatch(e -> e.contains("OAuth client")));
    }

    @Test
    public void testInvalidSinkModeValidation() {
        config.setSinkMode("invalid_mode");
        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("Sink mode must be either")));
    }

    @Test
    public void testSdtValidationDeviationMustBePositive() {
        config.setEnableSdtCompression(true);
        config.setSdtDeviation(0.0);

        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("SDT deviation")));
    }

    @Test
    public void testSdtValidationMaxIntervalMustBePositive() {
        config.setEnableSdtCompression(true);
        config.setSdtDeviation(1.0);
        config.setSdtMaxIntervalSeconds(0);

        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("SDT max interval")));
    }

    @Test
    public void testSdtValidationPassesWhenDisabled() {
        config.setEnableSdtCompression(false);
        config.setSdtDeviation(-1.0); // invalid but ignored because SDT is off

        List<String> errors = config.validate();
        assertFalse(errors.stream().anyMatch(e -> e.contains("SDT")));
    }

    @Test
    public void testSdtRequiresRestart() {
        ConfigModel newConfig = new ConfigModel();
        assertFalse(config.requiresRestart(newConfig));

        newConfig.setEnableSdtCompression(true);
        assertTrue(config.requiresRestart(newConfig));
    }

    @Test
    public void testSdtUpdateFrom() {
        ConfigModel other = new ConfigModel();
        other.setEnableSdtCompression(true);
        other.setSdtDeviation(2.5);
        other.setSdtMaxIntervalSeconds(600);

        config.updateFrom(other);

        assertTrue(config.isEnableSdtCompression());
        assertEquals(2.5, config.getSdtDeviation());
        assertEquals(600, config.getSdtMaxIntervalSeconds());
    }

    @Test
    public void testTagSelectionModeValidation() {
        config.setWorkspaceUrl("https://workspace.databricks.com");
        config.setZerobusEndpoint("https://workspace.databricks.com/api/2.0/lakeflow/ingest");
        config.setOauthClientId("client-id");
        config.setOauthClientSecret("client-secret");
        config.setTargetTable("dev.bronze.events");
        config.setEnabled(true);
        config.setEnableDirectSubscriptions(true);
        
        // Folder mode without folder path
        config.setTagSelectionMode("folder");
        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("folder path")));
        
        // Pattern mode without pattern
        config.setTagSelectionMode("pattern");
        errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("pattern")));
        
        // Explicit mode without paths
        config.setTagSelectionMode("explicit");
        errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("explicit")));
    }

    @Test
    public void testWorkspaceIdMismatchValidation() {
        config.setEnabled(true);
        config.setWorkspaceUrl("https://adb-1111111111111111.10.azuredatabricks.net");
        config.setZerobusEndpoint("2222222222222222.zerobus.eastus2.azuredatabricks.net");
        config.setOauthClientId("client-id");
        config.setOauthClientSecret("client-secret");
        config.setTargetTable("dev.bronze.events");
        config.setTagSelectionMode("folder");
        config.setTagFolderPath("[default]Production");

        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("Workspace URL and Zerobus endpoint") && e.contains("mismatch")),
                "Should fail when workspace ID in URL does not match endpoint: " + errors);
    }

    @Test
    public void testWorkspaceIdMatchPasses() {
        config.setEnabled(true);
        config.setWorkspaceUrl("https://adb-7405607216190670.10.azuredatabricks.net");
        config.setZerobusEndpoint("7405607216190670.zerobus.eastus2.azuredatabricks.net");
        config.setOauthClientId("client-id");
        config.setOauthClientSecret("client-secret");
        config.setTargetTable("dev.bronze.events");
        config.setTagSelectionMode("folder");
        config.setTagFolderPath("[default]Production");

        List<String> errors = config.validate();
        assertFalse(errors.stream().anyMatch(e -> e.contains("mismatch")),
                "Should pass when workspace IDs match: " + errors);
    }

    @Test
    public void testMaxQueueSizeValidation() {
        config.setWorkspaceUrl("https://workspace.databricks.com");
        config.setZerobusEndpoint("workspace.zerobus.region.databricks.com");
        config.setOauthClientId("client-id");
        config.setOauthClientSecret("client-secret");
        config.setTargetTable("dev.bronze.events");
        config.setTagSelectionMode("folder");
        config.setTagFolderPath("[default]Production");
        config.setMaxQueueSize(0);

        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("Max queue size")));

        config.setMaxQueueSize(2_000_000);
        errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("Max queue size")));
    }

    @Test
    public void testMaxEventsPerSecondValidation() {
        config.setWorkspaceUrl("https://workspace.databricks.com");
        config.setZerobusEndpoint("workspace.zerobus.region.databricks.com");
        config.setOauthClientId("client-id");
        config.setOauthClientSecret("client-secret");
        config.setTargetTable("dev.bronze.events");
        config.setTagSelectionMode("folder");
        config.setTagFolderPath("[default]Production");
        config.setMaxEventsPerSecond(0);

        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("Max events per second")));

        config.setMaxEventsPerSecond(2_000_000);
        errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("Max events per second")));
    }

    // === SDT Override validation tests ===

    @Test
    public void testSdtOverrideValidRegex() {
        config.setSdtOverrides(List.of(
            new SdtOverride(".*WindSpeed.*", 0.5, 10)
        ));
        List<String> errors = config.validate();
        assertFalse(errors.stream().anyMatch(e -> e.contains("sdtOverrides")),
                "Valid override should produce no errors: " + errors);
    }

    @Test
    public void testSdtOverrideInvalidRegex() {
        config.setSdtOverrides(List.of(
            new SdtOverride("[unclosed", 0.5, 10)
        ));
        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("sdtOverrides[0]") && e.contains("invalid regex")),
                "Invalid regex should produce an error: " + errors);
    }

    @Test
    public void testSdtOverrideEmptyPattern() {
        config.setSdtOverrides(List.of(
            new SdtOverride("", 0.5, 10)
        ));
        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("sdtOverrides[0]") && e.contains("pattern is required")),
                "Empty pattern should produce an error: " + errors);
    }

    @Test
    public void testSdtOverrideNegativeDeviation() {
        config.setSdtOverrides(List.of(
            new SdtOverride(".*Wind.*", -1.0, 10)
        ));
        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("sdtOverrides[0]") && e.contains("deviation must be >= 0")),
                "Negative deviation should produce an error: " + errors);
    }

    @Test
    public void testSdtOverrideZeroDeviationAllowed() {
        config.setSdtOverrides(List.of(
            new SdtOverride(".*Status.*", 0.0, 600)
        ));
        List<String> errors = config.validate();
        assertFalse(errors.stream().anyMatch(e -> e.contains("sdtOverrides[0]") && e.contains("deviation")),
                "Zero deviation should be allowed: " + errors);
    }

    @Test
    public void testSdtOverrideZeroMaxInterval() {
        config.setSdtOverrides(List.of(
            new SdtOverride(".*Wind.*", 0.5, 0)
        ));
        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("sdtOverrides[0]") && e.contains("maxIntervalSeconds must be > 0")),
                "Zero maxIntervalSeconds should produce an error: " + errors);
    }

    @Test
    public void testSdtOverrideMultipleErrors() {
        config.setSdtOverrides(Arrays.asList(
            new SdtOverride(".*Valid.*", 0.5, 10),
            new SdtOverride("[bad", -1.0, 0)
        ));
        List<String> errors = config.validate();
        assertTrue(errors.stream().anyMatch(e -> e.contains("sdtOverrides[1]") && e.contains("invalid regex")));
        assertTrue(errors.stream().anyMatch(e -> e.contains("sdtOverrides[1]") && e.contains("deviation")));
        assertTrue(errors.stream().anyMatch(e -> e.contains("sdtOverrides[1]") && e.contains("maxIntervalSeconds")));
        assertFalse(errors.stream().anyMatch(e -> e.contains("sdtOverrides[0]")),
                "Valid override should not produce errors");
    }

    @Test
    public void testSdtOverrideRequiresRestart() {
        ConfigModel newConfig = new ConfigModel();
        assertFalse(config.requiresRestart(newConfig));

        newConfig.setSdtOverrides(List.of(
            new SdtOverride(".*Wind.*", 0.5, 10)
        ));
        assertTrue(config.requiresRestart(newConfig),
                "Changing sdtOverrides should require restart");
    }

    @Test
    public void testSdtOverrideUpdateFrom() {
        ConfigModel other = new ConfigModel();
        List<SdtOverride> overrides = Arrays.asList(
            new SdtOverride(".*Wind.*", 0.5, 10),
            new SdtOverride(".*Temp.*", 0.2, 300)
        );
        other.setSdtOverrides(overrides);

        config.updateFrom(other);

        assertEquals(2, config.getSdtOverrides().size());
        assertEquals(".*Wind.*", config.getSdtOverrides().get(0).getPattern());
        assertEquals(".*Temp.*", config.getSdtOverrides().get(1).getPattern());
    }

    @Test
    public void testSdtOverrideDefaultsEmpty() {
        assertNotNull(config.getSdtOverrides());
        assertTrue(config.getSdtOverrides().isEmpty());
    }
}

