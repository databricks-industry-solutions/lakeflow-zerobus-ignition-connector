package com.example.ignition.zerobus;

/**
 * Minimal interface shared by the HTTP servlet layer for both Ignition 8.1 and 8.3.
 *
 * Ignition 8.1 used Wicket-based config tabs, while 8.3 uses a different web UI system.
 * The servlet endpoints (/system/zerobus/*) should work for both, so we avoid hard-coding a specific
 * gateway hook class type in the servlet handler.
 */
public interface ZerobusRuntime {
    ConfigModel getConfigModel();

    String getDiagnosticsInfo();

    void saveConfiguration(ConfigModel newConfig);

    boolean testConnection();

    boolean ingestTagEvent(com.example.ignition.zerobus.web.TagEventPayload payload);

    int ingestTagEventBatch(com.example.ignition.zerobus.web.TagEventPayload[] payloads);
}


