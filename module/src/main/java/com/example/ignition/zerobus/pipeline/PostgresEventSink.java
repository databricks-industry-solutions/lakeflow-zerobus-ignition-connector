package com.example.ignition.zerobus.pipeline;

import com.example.ignition.zerobus.PostgresClientManager;
import com.example.ignition.zerobus.proto.OTEvent;

import java.util.List;

/**
 * Event sink implementation for PostgreSQL/Lakebase.
 */
public final class PostgresEventSink implements EventSink {
    private final PostgresClientManager client;

    public PostgresEventSink(PostgresClientManager client) {
        this.client = client;
    }

    @Override
    public boolean isReady() {
        return client.isReadyToSend();
    }

    @Override
    public boolean tryEnsureReady() {
        return client.tryEnsureConnected();
    }

    @Override
    public boolean send(List<OTEvent> events) {
        return client.sendOtEvents(events);
    }
}
