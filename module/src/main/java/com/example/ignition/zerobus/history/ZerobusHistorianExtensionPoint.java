package com.example.ignition.zerobus.history;

import com.example.ignition.zerobus.ConfigModel;
import com.inductiveautomation.ignition.gateway.config.DecodedResource;
import com.inductiveautomation.ignition.gateway.config.ExtensionPointConfig;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import com.inductiveautomation.historian.gateway.api.Historian;
import com.inductiveautomation.historian.gateway.api.HistorianExtensionPoint;
import com.inductiveautomation.historian.gateway.api.HistorianProvider;
import com.inductiveautomation.historian.gateway.api.config.HistorianSettings;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Historian extension point that creates ZerobusTagHistoryProvider instances.
 *
 * In Ignition 8.3.3+, historian providers register through the extension point system
 * (returned from GatewayModuleHook.getExtensionPoints()) rather than the old
 * TagManager.registerTagHistoryProvider() API.
 */
public class ZerobusHistorianExtensionPoint extends HistorianExtensionPoint<HistorianSettings> {

    private static final Logger logger = LoggerFactory.getLogger(ZerobusHistorianExtensionPoint.class);

    public static final String TYPE_ID = "zerobus-historian";

    private final ConfigModel configModel;

    public ZerobusHistorianExtensionPoint(ConfigModel configModel) {
        super(TYPE_ID, "Zerobus", "Streams tag history to/from Databricks Delta via Zerobus");
        this.configModel = configModel;
    }

    @Override
    public Historian<HistorianSettings> createHistorianProvider(
            GatewayContext context,
            DecodedResource<ExtensionPointConfig<HistorianProvider, HistorianSettings>> resource) throws Exception {
        String name = resource.name();
        logger.info("Creating ZerobusTagHistoryProvider: {}", name);
        return new ZerobusTagHistoryProvider(context, name, configModel);
    }
}
