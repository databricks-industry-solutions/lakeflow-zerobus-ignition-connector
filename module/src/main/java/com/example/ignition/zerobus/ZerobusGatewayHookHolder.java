package com.example.ignition.zerobus;

/**
 * Holds a reference to the active {@link ZerobusGatewayHook} so Wicket pages (Gateway UI)
 * can notify the running module when PersistentRecord config is saved.
 *
 * Ignition instantiates one gateway hook per module, so this is safe.
 */
public final class ZerobusGatewayHookHolder {
    private static volatile ZerobusGatewayHook instance;

    private ZerobusGatewayHookHolder() {}

    public static ZerobusGatewayHook get() {
        return instance;
    }

    public static void set(ZerobusGatewayHook hook) {
        instance = hook;
    }
}


