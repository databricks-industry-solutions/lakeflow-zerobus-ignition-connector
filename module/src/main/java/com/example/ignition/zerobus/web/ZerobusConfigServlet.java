package com.example.ignition.zerobus.web;

/**
 * Runtime servlet selector to support both Ignition 8.1/8.2 (javax.servlet) and Ignition 8.3+ (jakarta.servlet).
 *
 * Ignition's servlet API package changed during the 8.3 line, so we ship two servlet implementations and pick one
 * based on the classes available in the Gateway runtime.
 */
public final class ZerobusConfigServlet {
    private ZerobusConfigServlet() {
        // no-op
    }

    /**
     * Pick the correct servlet class for the running Ignition Gateway.
     */
    public static Class<?> pickServletClass() {
        // Use reflection by name to avoid hard-linking either servlet implementation at class-load time.
        // This is critical for "single .modl works on both 8.1 and 8.3" where only one servlet namespace exists.
        final String servletClassName;
        if (classExists("jakarta.servlet.http.HttpServlet")) {
            // Ignition 8.3+
            servletClassName = "com.example.ignition.zerobus.web.servlet83.ZerobusConfigServletJakarta";
        } else {
            // Ignition 8.1/8.2
            servletClassName = "com.example.ignition.zerobus.web.servlet81.ZerobusConfigServletJavax";
        }

        try {
            return Class.forName(servletClassName, false, ZerobusConfigServlet.class.getClassLoader());
        } catch (ClassNotFoundException e) {
            throw new IllegalStateException("Expected servlet class missing: " + servletClassName, e);
        }
    }

    private static boolean classExists(String className) {
        try {
            Class.forName(className, false, ZerobusConfigServlet.class.getClassLoader());
            return true;
        } catch (Throwable t) {
            return false;
        }
    }
}


