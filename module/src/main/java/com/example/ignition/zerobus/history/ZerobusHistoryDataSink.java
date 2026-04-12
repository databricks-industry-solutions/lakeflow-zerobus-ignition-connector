package com.example.ignition.zerobus.history;

/**
 * Placeholder — in Ignition 8.3.4+, the DataSink registration is handled automatically
 * by LegacyTagHistoryProviderAdapter via TagHistoryStorageEngineBridge.
 *
 * The actual write path flows through the existing Zerobus pipeline
 * (TagSubscriptionService -> OtEventMapper -> StoreAndForwardBuffer -> ZerobusEventSink),
 * not through the historian DataSink.
 */
public class ZerobusHistoryDataSink {
    // Intentionally empty — see class javadoc.
}
