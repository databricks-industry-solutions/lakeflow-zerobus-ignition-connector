package com.example.ignition.zerobus;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

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
}

