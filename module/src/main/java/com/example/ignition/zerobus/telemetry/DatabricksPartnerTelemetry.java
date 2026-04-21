package com.example.ignition.zerobus.telemetry;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Registers Databricks partner / product identifiers for SDK HTTP User-Agent attribution.
 * Uses reflection so the module builds without {@code databricks-sdk-java} on the classpath; when that SDK
 * is present (optional Gradle dependency or future classpath), registration runs at runtime.
 *
 * @see <a href="https://databrickslabs.github.io/partner-architecture/isv-partners/telemetry-attribution/sdks">Partner Well Architected — SDKs</a>
 */
public final class DatabricksPartnerTelemetry {

    private static final Logger log = LoggerFactory.getLogger(DatabricksPartnerTelemetry.class);

    /** Short ISV identifier (Inductive Automation). */
    public static final String PARTNER_NAME = "InductiveAuto";

    /** Product surfaced in User-Agent (Ignition Gateway module). */
    public static final String PRODUCT_NAME = "Ignition";

    /** SemVer string required by the Java SDK ({@code UserAgent#withProduct}). */
    public static final String PRODUCT_VERSION = "1.0.0";

    private static final String USER_AGENT_CLASS = "com.databricks.sdk.core.UserAgent";

    private static volatile boolean registered;
    private static volatile boolean finishedRegistrationAttempt;

    private DatabricksPartnerTelemetry() {}

    /**
     * Applies {@code UserAgent.withProduct} then {@code UserAgent.withPartner} once per JVM when the
     * Databricks SDK for Java is on the classpath.
     */
    public static void ensureRegistered() {
        if (registered || finishedRegistrationAttempt) {
            return;
        }
        synchronized (DatabricksPartnerTelemetry.class) {
            if (registered || finishedRegistrationAttempt) {
                return;
            }
            try {
                Class<?> ua = Class.forName(USER_AGENT_CLASS);
                ua.getMethod("withProduct", String.class, String.class).invoke(null, PRODUCT_NAME, PRODUCT_VERSION);
                ua.getMethod("withPartner", String.class).invoke(null, PARTNER_NAME);
                registered = true;
                log.info("Databricks partner telemetry registered: partner={} product={}/{}",
                        PARTNER_NAME, PRODUCT_NAME, PRODUCT_VERSION);
            } catch (ClassNotFoundException e) {
                log.debug("Databricks SDK {} not on classpath; partner User-Agent not registered.", USER_AGENT_CLASS);
            } catch (Throwable t) {
                log.warn("Databricks partner User-Agent registration failed: {}", t.toString());
            } finally {
                finishedRegistrationAttempt = true;
            }
        }
    }
}
