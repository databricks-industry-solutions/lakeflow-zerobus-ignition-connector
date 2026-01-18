package com.example.ignition.zerobus;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * ConfigPanel - Gateway configuration for the Zerobus module.
 * 
 * IMPORTANT: This is a Gateway-scope module, NOT a Vision/Swing client module.
 * 
 * For Ignition 8.3 Gateway configuration, there are two modern approaches:
 * 
 * OPTION 1: Persistent Records (Recommended for this module)
 * =========================================================
 * Store configuration in Gateway database using PersistentRecord:
 * 
 * Implementation:
 * - Create a PersistentRecord class for settings
 * - Register with Gateway persistence interface
 * - Access via Gateway Config → Settings page
 * - No custom UI needed - Ignition generates forms automatically
 * 
 * Reference: slack-alarm-notification example
 * File: SlackNotificationProfileSettings.java
 * 
 * Code structure:
 * ```java
 * public class ZerobusSettings extends PersistentRecord {
 *     public static final RecordMeta<ZerobusSettings> META = 
 *         new RecordMeta<>(ZerobusSettings.class, "ZerobusSettings");
 *     
 *     public static final StringField WorkspaceUrl = new StringField(META, "WorkspaceUrl");
 *     public static final StringField ZerobusEndpoint = new StringField(META, "ZerobusEndpoint");
 *     // ... other fields
 * }
 * ```
 * 
 * OPTION 2: REST API + React Web UI
 * ===================================
 * Modern web-based configuration page:
 * 
 * Implementation:
 * - Create REST endpoints for configuration CRUD
 * - Build React UI for Gateway Config section
 * - Use Ignition web framework
 * 
 * Reference: webui-webpage example
 * Components needed:
 * - Gateway REST resources
 * - React components in web/ directory
 * - Mount point registration
 * 
 * Dependencies (NOT Vision/Swing):
 * ```gradle
 * // For web UI, NOT client UI:
 * compileOnly "com.inductiveautomation.ignitionsdk:gateway-api:8.3.0"
 * // React/TypeScript built separately in web/ folder
 * ```
 * 
 * ============================================================================
 * WHY NOT SWING/VISION?
 * ============================================================================
 * - Vision (`vision-client`) is for RUNTIME client UI (HMI screens)
 * - This module needs GATEWAY CONFIG UI (web-based in 8.3)
 * - Gateway Config is accessed at http://gateway:8088/config (web browser)
 * - NOT accessed from Vision clients running on workstations
 * 
 * ============================================================================
 * CURRENT STATUS
 * ============================================================================
 * The ZerobusGatewayHook already has methods for configuration management:
 * - loadConfiguration() - loads from persistence
 * - saveConfiguration() - saves to persistence  
 * - testConnection() - validates settings
 * 
 * To complete:
 * 1. Create ZerobusSettings extends PersistentRecord
 * 2. Register in setup() method
 * 3. Ignition will auto-generate config UI
 * 
 * Estimated time: 4-6 hours with persistence approach
 * ============================================================================
 */
public class ConfigPanel {
    
    private static final Logger logger = LoggerFactory.getLogger(ConfigPanel.class);
    
    private ConfigModel configModel;
    private ZerobusGatewayHook gatewayHook;
    
    /**
     * Constructor.
     * 
     * @param gatewayHook Reference to the gateway hook for accessing services
     */
    public ConfigPanel(ZerobusGatewayHook gatewayHook) {
        this.gatewayHook = gatewayHook;
        this.configModel = gatewayHook.getConfigModel();
    }
    
    /**
     * Test Databricks connection.
     * This method is functional and can be called programmatically.
     */
    public boolean testConnection() {
        logger.info("Testing connection...");
        
        try {
            // Validate configuration first
            java.util.List<String> errors = configModel.validate();
            if (!errors.isEmpty()) {
                logger.error("Configuration validation failed: {}", String.join(", ", errors));
                return false;
            }
            
            // Test connection
            boolean success = gatewayHook.testConnection();
            
            if (success) {
                logger.info("Connection test successful");
            } else {
                logger.error("Connection test failed - check Gateway logs");
            }
            
            return success;
            
        } catch (Exception e) {
            logger.error("Error testing connection", e);
            return false;
        }
    }
    
    /**
     * Save configuration.
     * This method is functional and can be called programmatically.
     */
    public boolean saveConfiguration() {
        logger.info("Saving configuration...");
        
        try {
            // Validate configuration
            java.util.List<String> errors = configModel.validate();
            if (!errors.isEmpty()) {
                logger.error("Validation failed: {}", String.join(", ", errors));
                return false;
            }
            
            // Save configuration
            gatewayHook.saveConfiguration(configModel);
            logger.info("Configuration saved successfully");
            
            return true;
            
        } catch (Exception e) {
            logger.error("Error saving configuration", e);
            return false;
        }
    }
    
    /**
     * Refresh diagnostics.
     * This method is functional and can be called programmatically.
     */
    public String refreshDiagnostics() {
        logger.debug("Refreshing diagnostics...");
        
        try {
            String diagnostics = gatewayHook.getDiagnosticsInfo();
            logger.debug("Diagnostics refreshed");
            return diagnostics;
            
        } catch (Exception e) {
            logger.error("Error refreshing diagnostics", e);
            return "Error: " + e.getMessage();
        }
    }
    
    /**
     * Get current configuration.
     */
    public ConfigModel getConfiguration() {
        return configModel;
    }
    
    /**
     * Update configuration.
     */
    public void updateConfiguration(ConfigModel newConfig) {
        this.configModel = newConfig;
    }
}
