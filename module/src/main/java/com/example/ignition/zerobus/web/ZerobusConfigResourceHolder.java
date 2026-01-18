package com.example.ignition.zerobus.web;

/**
 * Simple static holder for the module's REST/resource wiring.
 *
 * We keep this in a separate class so both servlet implementations (javax/jakarta)
 * can access the same resource without creating a hard dependency between them.
 */
public final class ZerobusConfigResourceHolder {
    private static volatile ZerobusConfigResource resource;

    private ZerobusConfigResourceHolder() {
        // no-op
    }

    public static void set(ZerobusConfigResource newResource) {
        resource = newResource;
    }

    public static ZerobusConfigResource get() {
        return resource;
    }

    public static void clear() {
        resource = null;
    }
}


