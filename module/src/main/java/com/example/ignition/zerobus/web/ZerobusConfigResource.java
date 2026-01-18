package com.example.ignition.zerobus.web;

import com.example.ignition.zerobus.ZerobusRuntime;
import com.inductiveautomation.ignition.gateway.model.GatewayContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Configuration & diagnostics helper for Zerobus Connector.
 *
 * IMPORTANT (Ignition 8.1/8.2): Do not use JAX-RS annotations here.
 * Many 8.1/8.2 Gateways do not ship a JAX-RS API/runtime on the module classpath, which can cause the module to fail
 * during class loading and appear as "not registering".
 *
 * HTTP endpoints are served via servlet implementations selected at runtime:
 * - Ignition 8.1/8.2: `web.servlet81.ZerobusConfigServletJavax`
 * - Ignition 8.3+:    `web.servlet83.ZerobusConfigServletJakarta`
 */
public class ZerobusConfigResource {
    
    private static final Logger logger = LoggerFactory.getLogger(ZerobusConfigResource.class);
    
    private final GatewayContext context;
    private final ZerobusRuntime runtime;
    
    /**
     * Constructor.
     * 
     * @param context Gateway context
     * @param gatewayHook Module hook instance
     */
    public ZerobusConfigResource(GatewayContext context, ZerobusRuntime runtime) {
        this.context = context;
        this.runtime = runtime;
    }
    
    /**
     * Get the gateway hook instance.
     * 
     * @return Gateway hook
     */
    public ZerobusRuntime getRuntime() {
        return runtime;
    }

    // Keeping the class for wiring only; behavior lives in the runtime hook and servlet handler.
}

