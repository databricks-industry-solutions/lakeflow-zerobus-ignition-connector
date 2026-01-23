package com.example.ignition.zerobus;

import com.example.ignition.zerobus.web.TagEventPayload;
import com.example.ignition.zerobus.web.ZerobusConfigResource;
import com.example.ignition.zerobus.web.ZerobusConfigResourceHolder;
import com.example.ignition.zerobus.web.ZerobusConfigServlet;
import com.example.ignition.zerobus.web.ZerobusConfigureRedirectPanel;
import com.example.ignition.zerobus.web.ZerobusSettingsPage;
import com.example.ignition.zerobus.pipeline.ZerobusPipelineFactory;
import com.inductiveautomation.ignition.common.BundleUtil;
import com.inductiveautomation.ignition.common.licensing.LicenseState;
import com.inductiveautomation.ignition.gateway.localdb.persistence.PersistenceInterface;
import com.inductiveautomation.ignition.gateway.model.AbstractGatewayModuleHook;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import com.inductiveautomation.ignition.gateway.web.models.ConfigCategory;
import com.inductiveautomation.ignition.gateway.web.models.DefaultConfigTab;
import com.inductiveautomation.ignition.gateway.web.models.IConfigTab;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import simpleorm.dataset.SQuery;

import java.util.Collections;
import java.util.List;

/**
 * ZerobusGatewayHook - Main entry point for the Ignition-Zerobus connector module.
 * 
 * This module subscribes to Ignition tags and streams their values to Databricks
 * Delta tables via the Zerobus Ingest API using the Databricks Zerobus Java SDK.
 * 
 * Lifecycle (Ignition 8.3.2):
 * - setup(GatewayContext): Initialize context and prepare resources
 * - startup(LicenseState): Start services and activate module
 * - shutdown(): Stop services and cleanup
 */
public class ZerobusGatewayHook extends AbstractGatewayModuleHook implements ZerobusRuntime {

    private static final Logger logger = LoggerFactory.getLogger(ZerobusGatewayHook.class);
    private static final String I18N_BUNDLE = "zerobus";
    private static final String I18N_BASE_NAME = "com.example.ignition.zerobus.zerobus";

    /**
     * Configuration category for Gateway Config navigation.
     * Uses "system" as the category name to appear in the existing System section.
     */
    public static final ConfigCategory CONFIG_CATEGORY =
        new ConfigCategory("system", "Zerobus Connector");

    /**
     * Configuration tab entry for the settings page.
     * Links the ZerobusSettingsPage to the navigation menu under System.
     *
     * Hardcoding "Settings" since BundleUtil doesn't work. Field labels work via Wicket resources.
     */
    public static final IConfigTab CONFIG_ENTRY = DefaultConfigTab.builder()
        .category(CONFIG_CATEGORY)
        .name("zerobus")
        // DefaultConfigTab uses Wicket ResourceModel -> BundleUtil.getString("bundle.key") format.
        // So we must prefix the key with the bundle name to resolve from zerobus.properties.
        .i18n(I18N_BUNDLE + ".Zerobus.nav.settings.title")
        .page(ZerobusConfigureRedirectPanel.class)
        .terms("zerobus databricks connector settings configuration")
        .build();

    private GatewayContext gatewayContext;
    private ZerobusClientManager zerobusClientManager;
    private TagSubscriptionService tagSubscriptionService;
    private ConfigModel configModel;
    private ZerobusConfigResource restResource;

    /**
     * (Re)create service objects if they are missing. This can happen after config apply/restart operations.
     * Must be called while holding this instance monitor if concurrent restarts are possible.
     */
    private void ensureServicesInitialized() {
        if (gatewayContext == null) {
            throw new IllegalStateException("GatewayContext is not initialized");
        }
        if (configModel == null) {
            configModel = new ConfigModel();
        }

        // Pipeline wiring depends on ZerobusClientManager; recreate as a unit if anything is missing.
        if (zerobusClientManager == null || tagSubscriptionService == null) {
            zerobusClientManager = new ZerobusClientManager(configModel);
            ZerobusPipelineFactory.PipelineComponents comps =
                    ZerobusPipelineFactory.create(configModel, zerobusClientManager);
            tagSubscriptionService = new TagSubscriptionService(
                    gatewayContext, configModel, comps.mapper, comps.buffer, comps.sink
            );
        }
    }
    
    /**
     * Setup - called first during module initialization.
     * Store the gateway context for later use.
     */
    @Override
    public void setup(GatewayContext context) {
        this.gatewayContext = context;
        ZerobusGatewayHookHolder.set(this);

        // Register PersistentRecord for configuration storage
        try {
            context.getSchemaUpdater().updatePersistentRecords(ZerobusSettings.META);
            logger.info("ZerobusSettings PersistentRecord registered");
        } catch (Exception e) {
            logger.error("Failed to register ZerobusSettings PersistentRecord", e);
        }

        // Register i18n bundle for navigation + shared strings.
        // Field labels are handled separately via FormMeta keys + ZerobusSettings.properties / ZerobusSettingsPage.properties.
        try {
            BundleUtil.get().addBundle(I18N_BUNDLE, ZerobusGatewayHook.class.getClassLoader(), I18N_BASE_NAME);
            logger.info("Zerobus i18n bundle registered (BundleUtil): {} -> {}", I18N_BUNDLE, I18N_BASE_NAME);

            // Smoke test: these must be non-null for nav/title rendering
            logger.info("Bundle test: {}={}",
                I18N_BUNDLE + ".Zerobus.nav.settings.title",
                BundleUtil.get().getString(I18N_BUNDLE + ".Zerobus.nav.settings.title")
            );
            logger.info("Bundle test: {}={}",
                I18N_BUNDLE + ".Zerobus.nav.settings.panelTitle",
                BundleUtil.get().getString(I18N_BUNDLE + ".Zerobus.nav.settings.panelTitle")
            );
        } catch (Exception e) {
            logger.error("Failed to register zerobus i18n bundle", e);
        }

        // Register configuration servlet
        try {
            // Create REST resource and set it for servlet use
            this.restResource = new ZerobusConfigResource(context, this);
            ZerobusConfigResourceHolder.set(restResource);

            // Register servlet with Ignition's WebResourceManager.
            // We support both Ignition 8.1/8.2 (javax.servlet) and 8.3+ (jakarta.servlet) by selecting at runtime.
            Class<?> servletClass = ZerobusConfigServlet.pickServletClass();
            context.getWebResourceManager()
                .getClass()
                .getMethod("addServlet", String.class, Class.class)
                .invoke(context.getWebResourceManager(), "zerobus", servletClass);

            logger.info("Configuration servlet registered: 'zerobus' → /system/zerobus");
        } catch (Throwable t) {
            // Don't prevent the module from registering if servlet registration fails.
            logger.error("Failed to register configuration servlet (module will still load)", t);
        }

        logger.info("Zerobus Gateway Module setup complete");
    }
    
    /**
     * Module startup - called when the module is installed or Gateway starts.
     * NOTE: startup() is abstract in AbstractGatewayModuleHook - do NOT call super.startup()
     */
    @Override
    public void startup(LicenseState licenseState) {
        logger.info("Starting Zerobus Gateway Module...");
        
        try {
            // Initialize configuration model
            this.configModel = new ConfigModel();
            loadConfiguration();
            
            // Initialize Zerobus client manager
            this.zerobusClientManager = new ZerobusClientManager(configModel);
            
            // Initialize tag subscription service (pipeline wiring is external)
            ZerobusPipelineFactory.PipelineComponents comps = ZerobusPipelineFactory.create(configModel, zerobusClientManager);
            this.tagSubscriptionService = new TagSubscriptionService(gatewayContext, configModel, comps.mapper, comps.buffer, comps.sink);
            
            // Note: REST servlet is registered in setup() method
            
            // Only start services if module is enabled
            if (configModel.isEnabled()) {
                try {
                    startServices();
                } catch (IllegalArgumentException iae) {
                    // Invalid config should not fault the module. Keep it running but stop services.
                    logger.error("Zerobus configuration is invalid; services will remain stopped until fixed: {}", iae.getMessage());
                } catch (Exception e) {
                    logger.error("Failed to start Zerobus services; module will remain loaded but services are stopped.", e);
                }
            }
            
            logger.info("Zerobus Gateway Module started successfully");
            
        } catch (Exception e) {
            logger.error("Failed to start Zerobus Gateway Module", e);
            // Don't fault the module due to a startup exception; keep it loaded so the UI can be used to fix config.
        }
    }
    
    /**
     * Module shutdown - called when the module is uninstalled or Gateway stops.
     * NOTE: shutdown() is abstract in AbstractGatewayModuleHook - do NOT call super.shutdown()
     */
    @Override
    public void shutdown() {
        logger.info("Shutting down Zerobus Gateway Module...");

        try {
            ZerobusGatewayHookHolder.set(null);
            // Unregister i18n resource bundle
            try {
                BundleUtil.get().removeBundle(I18N_BUNDLE);
                logger.info("Zerobus i18n bundle unregistered: {}", I18N_BUNDLE);
            } catch (Exception e) {
                logger.warn("Error unregistering zerobus bundle: {}", e.getMessage());
            }

            // Unregister servlet
            if (gatewayContext != null) {
                try {
                    gatewayContext.getWebResourceManager()
                        .getClass()
                        .getMethod("removeServlet", String.class)
                        .invoke(gatewayContext.getWebResourceManager(), "zerobus");
                    logger.info("Configuration servlet unregistered");
                } catch (Throwable t) {
                    logger.warn("Error unregistering servlet: {}", t.getMessage());
                }
            }

            // Stop tag subscriptions
            if (tagSubscriptionService != null) {
                tagSubscriptionService.shutdown();
                tagSubscriptionService = null;
            }

            // Close Zerobus client
            if (zerobusClientManager != null) {
                zerobusClientManager.shutdown();
                zerobusClientManager = null;
            }

            logger.info("Zerobus Gateway Module shut down successfully");

        } catch (Exception e) {
            logger.error("Error during module shutdown", e);
        }
    }
    
    /**
     * Start the Zerobus client and tag subscription services.
     */
    private void startServices() throws Exception {
        logger.info("Starting Zerobus services...");

        // Defensive: restart paths can null these out.
        ensureServicesInitialized();

        // Always start buffering/ingest service first so "sink down" does not prevent ingestion.
        tagSubscriptionService.start();

        // Best-effort: try to connect the sink. Failures should not stop ingestion; events will buffer.
        try {
            zerobusClientManager.initialize();
        } catch (Exception e) {
            logger.error("Zerobus sink is unavailable during startup. Ingestion will continue and buffer until the sink recovers.", e);
        }
        
        logger.info("Zerobus services started");
    }
    
    /**
     * Load configuration from persistent storage.
     *
     * Reads ZerobusSettings from the Gateway's internal database and populates
     * the ConfigModel. If no saved settings exist, uses defaults from ConfigModel.
     */
    private void loadConfiguration() {
        logger.debug("Loading configuration from persistent storage...");

        try {
            PersistenceInterface persistence = gatewayContext.getPersistenceInterface();
            SQuery<ZerobusSettings> query = new SQuery<>(ZerobusSettings.META);
            List<ZerobusSettings> records = persistence.query(query);

            if (!records.isEmpty()) {
                // Load configuration from first record (should only be one)
                ZerobusSettings settings = records.get(0);
                this.configModel = settings.toConfigModel();
                // Auto-correct common Docker path mismatches on load so services can start immediately.
                this.configModel.autoCorrectPaths();
                logger.info("Configuration loaded from database");
            } else {
                // No saved configuration - use defaults
                logger.info("No saved configuration found, using defaults");

                // Create initial settings record with defaults
                ZerobusSettings settings = persistence.createNew(ZerobusSettings.META);
                settings.fromConfigModel(this.configModel);
                persistence.save(settings);
                logger.info("Created default configuration in database");
            }
        } catch (Exception e) {
            logger.error("Failed to load configuration from database, using defaults", e);
            // configModel already initialized with defaults in startup()
        }
    }
    
    /**
     * Save configuration to persistent storage.
     *
     * Updates the ZerobusSettings record in the Gateway database and restarts
     * services if necessary.
     *
     * @param newConfig The new configuration to save
     */
    public void saveConfiguration(ConfigModel newConfig) {
        logger.info("Saving configuration to persistent storage...");

        try {
            // Check if restart is needed before updating
            boolean needsRestart = configModel.requiresRestart(newConfig);

            // Persist to the gateway DB.
            //
            // IMPORTANT (Ignition 8.1): servlet threads can already have an open Persistence session.
            // Touching PersistenceInterface on that thread can throw:
            //   "Attempting to open new session, but session already open for this thread."
            //
            // To keep /system/zerobus/config usable from the embedded HTML UI + REST calls, we
            // perform persistence work on a fresh thread and wait briefly for completion.
            persistConfigOffThread(newConfig);
            logger.info("Configuration saved to database");

            // Update in-memory config
            this.configModel.updateFrom(newConfig);

            // Restart services if needed
            if (needsRestart && configModel.isEnabled()) {
                try {
                    // Shutdown existing services
                    if (tagSubscriptionService != null) {
                        tagSubscriptionService.shutdown();
                    }
                    if (zerobusClientManager != null) {
                        zerobusClientManager.shutdown();
                    }

                    // Start services with new configuration
                    try {
                        startServices();
                        logger.info("Services restarted with new configuration");
                    } catch (IllegalArgumentException iae) {
                        logger.error("New configuration is invalid; services will remain stopped until fixed: {}", iae.getMessage());
                    }

                } catch (Exception e) {
                    logger.error("Failed to restart services with new configuration; services will remain stopped.", e);
                }
            } else if (!needsRestart) {
                // Even when a restart isn't required, if the module is enabled and services are down,
                // start them to avoid requiring the operator to manually restart the gateway.
                if (configModel.isEnabled() && (tagSubscriptionService == null || !tagSubscriptionService.isRunning())) {
                    try {
                        startServices();
                        logger.info("Configuration updated; services started");
                    } catch (Exception e) {
                        logger.error("Configuration updated but services could not be started", e);
                    }
                } else {
                    logger.info("Configuration updated, no service restart required");
                }
            } else {
                logger.info("Configuration saved, services not started (module disabled)");
            }

        } catch (Exception e) {
            logger.error("Failed to save configuration to database", e);
            String msg = e.getMessage();
            throw new RuntimeException(
                "Configuration save failed" + (msg == null || msg.isBlank() ? "" : (": " + msg)),
                e
            );
        }
    }

    private void persistConfigOffThread(ConfigModel newConfig) throws Exception {
        final Exception[] holder = new Exception[1];
        Thread t = new Thread(() -> {
            try {
                PersistenceInterface persistence = gatewayContext.getPersistenceInterface();

                // Get or create settings record
                SQuery<ZerobusSettings> query = new SQuery<>(ZerobusSettings.META);
                List<ZerobusSettings> records = persistence.query(query);
                ZerobusSettings settings;

                if (records.isEmpty()) {
                    settings = persistence.createNew(ZerobusSettings.META);
                    logger.debug("Creating new settings record");
                } else {
                    settings = records.get(0);
                    logger.debug("Updating existing settings record");
                }

                // Update record from config model
                settings.fromConfigModel(newConfig);
                persistence.save(settings);
            } catch (Exception e) {
                holder[0] = e;
            }
        }, "Zerobus-PersistConfig");
        t.setDaemon(true);
        t.start();
        // Persistence should be quick; bound the wait so we don't wedge gateway web threads.
        t.join(5_000L);
        if (t.isAlive()) {
            t.interrupt();
            throw new RuntimeException("Configuration save failed: timed out persisting settings");
        }
        if (holder[0] != null) {
            throw holder[0];
        }
    }

    /**
     * Apply a new configuration to the running module without touching persistence.
     *
     * This is intended for use by the Gateway Config UI lifecycle (RecordEditForm onAfterCommit),
     * where a PersistenceSession is already open on the request thread. Calling persistence APIs
     * from that thread can trigger "session already open" errors.
     */
    public void applyRuntimeConfiguration(ConfigModel newConfig) {
        try {
            boolean needsRestart = configModel.requiresRestart(newConfig);

            // Update in-memory config immediately so /system/zerobus/config reflects UI changes.
            this.configModel.updateFrom(newConfig);

            // If disabled, ensure services are stopped.
            if (!configModel.isEnabled()) {
                if (tagSubscriptionService != null) {
                    tagSubscriptionService.shutdown();
                }
                if (zerobusClientManager != null) {
                    zerobusClientManager.shutdown();
                }
                logger.info("Runtime configuration applied; services stopped (module disabled)");
                return;
            }

            if (!needsRestart) {
                logger.info("Runtime configuration applied; no service restart required");
                return;
            }

            // Restart services with new configuration
            try {
                if (tagSubscriptionService != null) {
                    tagSubscriptionService.shutdown();
                }
                if (zerobusClientManager != null) {
                    zerobusClientManager.shutdown();
                }

                try {
                    startServices();
                    logger.info("Runtime configuration applied; services restarted");
                } catch (IllegalArgumentException iae) {
                    logger.error("Runtime configuration is invalid; services will remain stopped until fixed: {}", iae.getMessage());
                }
            } catch (Exception e) {
                logger.error("Failed applying runtime configuration; services will remain stopped.", e);
            }
        } catch (Exception e) {
            logger.error("Failed applying runtime configuration", e);
        }
    }
    
    /**
     * Test connection to Zerobus with current configuration.
     * Used by the config UI to validate settings.
     */
    public boolean testConnection() {
        logger.info("Testing Zerobus connection...");
        
        try {
            ZerobusClientManager testClient = new ZerobusClientManager(configModel);
            testClient.initialize();
            boolean success = testClient.testConnection();
            testClient.shutdown();
            
            logger.info("Connection test " + (success ? "succeeded" : "failed"));
            return success;
            
        } catch (Exception e) {
            logger.error("Connection test failed", e);
            return false;
        }
    }

    @Override
    public boolean restartServices() {
        if (configModel == null || !configModel.isEnabled()) {
            logger.warn("Cannot restart services: module is disabled or config not initialized");
            return false;
        }
        synchronized (this) {
            try {
                logger.info("Restarting Zerobus services on request...");
                if (tagSubscriptionService != null) {
                    tagSubscriptionService.shutdown();
                }
                if (zerobusClientManager != null) {
                    zerobusClientManager.shutdown();
                }
                tagSubscriptionService = null;
                zerobusClientManager = null;
                startServices(); // will recreate services via ensureServicesInitialized()
                logger.info("Zerobus services restarted successfully");
                return true;
            } catch (Exception e) {
                logger.error("Failed to restart Zerobus services", e);
                return false;
            }
        }
    }
    
    /**
     * Get module identifier.
     */
    @Override
    public boolean isFreeModule() {
        // Must match module.xml <freeModule>true</freeModule>
        return true;
    }

    /**
     * Register configuration panels for the Gateway Config UI.
     * This makes the Zerobus settings page appear in the Gateway web interface.
     *
     * @return List of configuration tabs to display
     */
    @Override
    public List<? extends IConfigTab> getConfigPanels() {
        return Collections.singletonList(CONFIG_ENTRY);
    }
    
    /**
     * Get configuration model for UI access.
     */
    public ConfigModel getConfigModel() {
        return configModel;
    }
    
    /**
     * Get the gateway context.
     */
    public GatewayContext getGatewayContext() {
        return gatewayContext;
    }
    
    /**
     * Get Zerobus client manager.
     */
    public ZerobusClientManager getZerobusClientManager() {
        return zerobusClientManager;
    }
    
    /**
     * Get diagnostics information.
     */
    public String getDiagnostics() {
        return getDiagnosticsInfo();
    }
    
    /**
     * Get diagnostics information.
     */
    public String getDiagnosticsInfo() {
        StringBuilder info = new StringBuilder();
        info.append("=== Zerobus Module Diagnostics ===\n");
        try {
            info.append("Module Enabled: ").append(configModel != null && configModel.isEnabled()).append("\n");

            if (zerobusClientManager != null) {
                info.append("\n").append(zerobusClientManager.getDiagnostics());
            } else {
                info.append("\nInitialized: false\nConnected: false\n");
            }

            if (tagSubscriptionService != null) {
                info.append("\n").append(tagSubscriptionService.getDiagnostics());
            } else {
                info.append("\nRunning: false\nDirect Subscriptions: 0 tags\n");
            }
        } catch (Exception e) {
            // Never let diagnostics break the HTTP endpoint; return best-effort output.
            info.append("\nDiagnostics Error: ").append(e.getClass().getSimpleName()).append(": ").append(e.getMessage()).append("\n");
        }
        return info.toString();
    }
    
    /**
     * Ingest a single tag event from Event Streams.
     * 
     * @param payload Tag event payload from Event Streams
     * @return true if event was accepted, false if queue is full
     */
    public boolean ingestTagEvent(TagEventPayload payload) {
        if (tagSubscriptionService == null) {
            logger.warn("Cannot ingest event: tag subscription service not initialized");
            return false;
        }
        
        if (!configModel.isEnabled()) {
            logger.warn("Cannot ingest event: module is disabled");
            return false;
        }
        
        return tagSubscriptionService.ingestEvent(payload);
    }
    
    /**
     * Ingest a batch of tag events from Event Streams.
     * 
     * @param payloads Array of tag event payloads from Event Streams
     * @return number of events accepted
     */
    public int ingestTagEventBatch(TagEventPayload[] payloads) {
        if (tagSubscriptionService == null) {
            logger.warn("Cannot ingest batch: tag subscription service not initialized");
            return 0;
        }
        
        if (!configModel.isEnabled()) {
            logger.warn("Cannot ingest batch: module is disabled");
            return 0;
        }
        
        return tagSubscriptionService.ingestEventBatch(payloads);
    }
}
