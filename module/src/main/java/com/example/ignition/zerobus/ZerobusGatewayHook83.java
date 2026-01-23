package com.example.ignition.zerobus;

import com.example.ignition.zerobus.web.ZerobusConfigResourceHolder;
import com.example.ignition.zerobus.web.ZerobusConfigServlet;
import com.example.ignition.zerobus.web.TagEventPayload;
import com.example.ignition.zerobus.web.ZerobusConfigResource;
import com.example.ignition.zerobus.pipeline.ZerobusPipelineFactory;
import com.inductiveautomation.ignition.common.licensing.LicenseState;
import com.inductiveautomation.ignition.gateway.model.AbstractGatewayModuleHook;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import com.inductiveautomation.ignition.gateway.web.WebResourceManager;
import com.inductiveautomation.ignition.gateway.web.nav.NavigationModel;
import com.inductiveautomation.ignition.gateway.web.systemjs.SystemJsModule;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Ignition 8.3+ gateway hook.
 *
 * Ignition 8.3 removed the Wicket-based config UI APIs. Instead, modules integrate into the left navigation
 * using the new NavigationModel + SystemJsModule mechanism.
 *
 * This hook registers ONE nav entry under Services that loads a minimal SystemJS module which embeds our
 * existing HTML config page (/system/zerobus/configure) that includes inline diagnostics.
 */
public class ZerobusGatewayHook83 extends AbstractGatewayModuleHook implements ZerobusRuntime {
    private static final Logger logger = LoggerFactory.getLogger(ZerobusGatewayHook83.class);

    private GatewayContext gatewayContext;
    private ZerobusClientManager zerobusClientManager;
    private TagSubscriptionService tagSubscriptionService;
    private ConfigModel configModel;
    private ZerobusConfigResource restResource;
    private final AtomicBoolean restartInProgress = new AtomicBoolean(false);

    // 8.3 web-ui module registration
    private static final String MOUNT_ALIAS = "zerobus";
    private static final String UI_JS_URL = "/res/" + MOUNT_ALIAS + "/js/web-ui/zerobus.js";
    private static final String NAV_URL = "/services/zerobus";
    private static final String NAV_COMPONENT_ID = "ZerobusConfig";

    @Override
    public void setup(GatewayContext context) {
        this.gatewayContext = context;

        this.configModel = new ConfigModel();
        try {
            // Ensure our PersistentRecord schema exists before any persistence queries.
            // Without this, /system/zerobus/config will always show defaults and saves will fail.
            context.getSchemaUpdater().updatePersistentRecords(ZerobusSettings83.META);
            loadConfiguration();
        } catch (Exception e) {
            logger.error("Failed to load configuration; using defaults", e);
        }

        // Register the servlet endpoints under /system/zerobus/*
        try {
            restResource = new ZerobusConfigResource(context, this);
            ZerobusConfigResourceHolder.set(restResource);

            Class<?> servletClass = ZerobusConfigServlet.pickServletClass();
            @SuppressWarnings("unchecked")
            Class<? extends jakarta.servlet.http.HttpServlet> clazz =
                (Class<? extends jakarta.servlet.http.HttpServlet>) servletClass;
            // IMPORTANT (8.3): addServlet takes a servlet name, not a URL mapping. Ignition maps it as /system/<name>/*
            context.getWebResourceManager().addServlet("zerobus", clazz);
            logger.info("Registered Zerobus servlet: /system/zerobus/* (8.3)");
        } catch (Throwable t) {
            logger.error("Failed to register Zerobus servlet endpoints", t);
        }

        // Add ONE left-nav entry under Platform -> System that opens our embedded config UI.
        try {
            WebResourceManager web = context.getWebResourceManager();
            SystemJsModule jsModule = new SystemJsModule("com.example.ignition.zerobus", UI_JS_URL);
            web.getSystemJsModuleRegistry().add(jsModule);

            NavigationModel nav = web.getNavigationModel();
            nav.getPlatform().addCategory("system", cat -> cat
                .addPage("Zerobus Config", page -> page
                    .title("Zerobus Config")
                    .mount(NAV_URL, NAV_COMPONENT_ID, jsModule)
                    .position(150)
                    .build()
                )
                .build()
            );

            logger.info("Registered 8.3 navigation entry: Platform -> System -> Zerobus Config ({})", NAV_URL);
        } catch (Throwable t) {
            logger.error("Failed to register 8.3 navigation entry", t);
        }
    }

    @Override
    public void startup(LicenseState licenseState) {
        logger.info("Starting Zerobus Gateway Module (8.3)...");
        try {
            if (configModel != null && configModel.isEnabled()) {
                try {
                    startServices();
                } catch (IllegalArgumentException iae) {
                    logger.error("Zerobus configuration is invalid; services will remain stopped until fixed: {}", iae.getMessage());
                } catch (Exception e) {
                    logger.error("Failed to start Zerobus services; services are stopped.", e);
                }
            }
            logger.info("Zerobus Gateway Module started successfully (8.3)");
        } catch (Exception e) {
            logger.error("Failed to start Zerobus Gateway Module (8.3)", e);
        }
    }

    @Override
    public void shutdown() {
        logger.info("Shutting down Zerobus Gateway Module (8.3)...");
        try {
            if (tagSubscriptionService != null) {
                tagSubscriptionService.shutdown();
                tagSubscriptionService = null;
            }
            if (zerobusClientManager != null) {
                zerobusClientManager.shutdown();
                zerobusClientManager = null;
            }
        } catch (Exception e) {
            logger.warn("Error shutting down services", e);
        } finally {
            ZerobusConfigResourceHolder.clear();
        }
    }

    @Override
    public Optional<String> getMountPathAlias() {
        return Optional.of(MOUNT_ALIAS);
    }

    @Override
    public Optional<String> getMountedResourceFolder() {
        // Serves resources under src/main/resources/mounted/** at /res/<alias>/**
        return Optional.of("mounted");
    }

    // ---- Internal helpers (copied from 8.1 hook with no Wicket dependencies) ----

    private void startServices() throws Exception {
        logger.info("Starting Zerobus services (8.3)...");
        if (zerobusClientManager == null) {
            zerobusClientManager = new ZerobusClientManager(configModel);
        }

        // Always start buffering/ingest service first so "sink down" does not prevent ingestion.
        if (tagSubscriptionService == null) {
            ZerobusPipelineFactory.PipelineComponents comps = ZerobusPipelineFactory.create(configModel, zerobusClientManager);
            tagSubscriptionService = new TagSubscriptionService(gatewayContext, configModel, comps.mapper, comps.buffer, comps.sink);
        }
        tagSubscriptionService.start();

        // Best-effort: try to connect the sink. Failures should not stop ingestion; events will buffer.
        try {
            zerobusClientManager.initialize();
        } catch (Exception e) {
            logger.error("Zerobus sink is unavailable during startup (8.3). Ingestion will continue and buffer until the sink recovers.", e);
        }
    }

    private void loadConfiguration() {
        try {
            var persistence = gatewayContext.getPersistenceInterface();
            var query = new simpleorm.dataset.SQuery<>(ZerobusSettings83.META);
            var records = persistence.query(query);
            if (!records.isEmpty()) {
                this.configModel = records.get(0).toConfigModel();
                // Auto-correct common Docker path mismatches on load so services can start immediately.
                this.configModel.autoCorrectPaths();
                logger.info("Configuration loaded from database (8.3)");
            } else {
                logger.info("No saved configuration found, using defaults (8.3)");
                ZerobusSettings83 settings = persistence.createNew(ZerobusSettings83.META);
                settings.fromConfigModel(this.configModel);
                persistence.save(settings);
                logger.info("Created default configuration in database (8.3)");
            }
        } catch (Throwable t) {
            logger.warn("Failed to load configuration from database (8.3); using defaults", t);
        }
    }

    // ---- ZerobusRuntime implementation (used by servlet handler) ----

    @Override
    public ConfigModel getConfigModel() {
        return configModel;
    }

    @Override
    public String getDiagnosticsInfo() {
        StringBuilder sb = new StringBuilder();
        sb.append("=== Zerobus Module Diagnostics ===\n");
        sb.append("Module Enabled: ").append(configModel != null && configModel.isEnabled()).append("\n\n");

        sb.append("=== Zerobus Client Diagnostics ===\n");
        if (zerobusClientManager == null) {
            sb.append("Initialized: false\nConnected: false\n");
        } else {
            sb.append(zerobusClientManager.getDiagnostics());
        }

        sb.append("\n=== Event Processing Service Diagnostics ===\n");
        if (tagSubscriptionService == null) {
            sb.append("Running: false\n");
        } else {
            sb.append(tagSubscriptionService.getDiagnostics());
        }
        return sb.toString();
    }

    @Override
    public void saveConfiguration(ConfigModel newConfig) {
        logger.info("Saving configuration to persistent storage (8.3)...");
        try {
            boolean needsRestart = configModel.requiresRestart(newConfig);
            persistConfigOffThread(newConfig);
            logger.info("Configuration saved to database (8.3)");

            // Update runtime
            this.configModel.updateFrom(newConfig);

            if (needsRestart && configModel.isEnabled()) {
                try {
                    if (tagSubscriptionService != null) tagSubscriptionService.shutdown();
                    if (zerobusClientManager != null) zerobusClientManager.shutdown();
                    tagSubscriptionService = null;
                    zerobusClientManager = null;
                    startServices();
                } catch (IllegalArgumentException iae) {
                    logger.error("New configuration is invalid; services will remain stopped until fixed: {}", iae.getMessage());
                } catch (Exception e) {
                    logger.error("Failed to restart services with new configuration; services will remain stopped.", e);
                }
            } else if (!needsRestart) {
                // Even when a restart isn't required, if the module is enabled and services are down,
                // start them to avoid requiring the operator to manually restart the gateway.
                if (configModel.isEnabled() && (tagSubscriptionService == null || !tagSubscriptionService.isRunning())) {
                    try {
                        startServices();
                        logger.info("Configuration updated; services started (8.3)");
                    } catch (Exception e) {
                        logger.error("Configuration updated but services could not be started (8.3)", e);
                    }
                } else {
                    logger.info("Configuration updated, no service restart required (8.3)");
                }
            } else {
                logger.info("Configuration saved, services not started (module disabled) (8.3)");
            }
        } catch (Exception e) {
            logger.error("Failed to save configuration to database (8.3)", e);
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
                var persistence = gatewayContext.getPersistenceInterface();
                var query = new simpleorm.dataset.SQuery<>(ZerobusSettings83.META);
                List<ZerobusSettings83> records = persistence.query(query);
                ZerobusSettings83 settings = records.isEmpty()
                    ? persistence.createNew(ZerobusSettings83.META)
                    : records.get(0);
                settings.fromConfigModel(newConfig);
                persistence.save(settings);
            } catch (Exception e) {
                holder[0] = e;
            }
        }, "Zerobus-PersistConfig");
        t.setDaemon(true);
        t.start();
        t.join(5_000L);
        if (t.isAlive()) {
            t.interrupt();
            throw new RuntimeException("Configuration save failed: timed out persisting settings");
        }
        if (holder[0] != null) {
            throw holder[0];
        }
    }

    @Override
    public boolean testConnection() {
        try {
            ZerobusClientManager testClient = new ZerobusClientManager(configModel);
            testClient.initialize();
            boolean success = testClient.testConnection();
            testClient.shutdown();
            return success;
        } catch (Exception e) {
            logger.error("Connection test failed (8.3)", e);
            return false;
        }
    }

    @Override
    public boolean restartServices() {
        if (configModel == null || !configModel.isEnabled()) {
            logger.warn("Cannot restart services: module is disabled or config not initialized (8.3)");
            return false;
        }
        // IMPORTANT: Do not block the servlet thread.
        // Restarting can involve network calls / timeouts (e.g. stream creation), so we run it async and return
        // immediately to avoid wedging the gateway webserver under poor network conditions.
        if (!restartInProgress.compareAndSet(false, true)) {
            logger.warn("Restart requested while a restart is already in progress (8.3)");
            return true; // accepted; already running
        }

        Thread t = new Thread(() -> {
            try {
                synchronized (ZerobusGatewayHook83.this) {
                    logger.info("Restarting Zerobus services on request (8.3)...");
                    if (tagSubscriptionService != null) tagSubscriptionService.shutdown();
                    if (zerobusClientManager != null) zerobusClientManager.shutdown();
                    tagSubscriptionService = null;
                    zerobusClientManager = null;
                    startServices();
                    logger.info("Zerobus services restarted successfully (8.3)");
                }
            } catch (Exception e) {
                logger.error("Failed to restart Zerobus services (8.3)", e);
            } finally {
                restartInProgress.set(false);
            }
        }, "Zerobus-RestartServices");
        t.setDaemon(true);
        t.start();

        return true;
    }

    @Override
    public boolean ingestTagEvent(TagEventPayload payload) {
        if (configModel == null || !configModel.isEnabled()) {
            logger.warn("Cannot ingest: module is disabled");
            return false;
        }
        if (tagSubscriptionService == null) {
            logger.warn("Cannot ingest: services not running");
            return false;
        }
        return tagSubscriptionService.ingestEvent(payload);
    }

    @Override
    public int ingestTagEventBatch(TagEventPayload[] payloads) {
        if (configModel == null || !configModel.isEnabled()) {
            logger.warn("Cannot ingest batch: module is disabled");
            return 0;
        }
        if (tagSubscriptionService == null) {
            logger.warn("Cannot ingest batch: services not running");
            return 0;
        }
        return tagSubscriptionService.ingestEventBatch(payloads);
    }
}


