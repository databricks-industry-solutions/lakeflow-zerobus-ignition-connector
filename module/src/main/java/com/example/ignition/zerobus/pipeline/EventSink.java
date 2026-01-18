package com.example.ignition.zerobus.pipeline;

import com.example.ignition.zerobus.proto.OTEvent;

import java.util.List;

/**
 * Sink abstraction for sending normalized OT events downstream.
 *
 * This is the "UC/Zerobus write" boundary: sources/adapters should not know about Zerobus SDK details.
 */
public interface EventSink {
    /**
     * @return true if the sink is currently ready to accept sends without forcing upstream to drain buffers
     * (e.g., a network connection is established).
     */
    default boolean isReady() {
        return true;
    }

    /**
     * Best-effort: try to make the sink ready (e.g., reconnect), subject to internal backoff.
     *
     * @return true if the sink is ready after the attempt, false otherwise.
     */
    default boolean tryEnsureReady() {
        return isReady();
    }

    /**
     * @return true if the batch was accepted and durably written by the downstream sink, false otherwise.
     */
    boolean send(List<OTEvent> events);
}


