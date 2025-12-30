package com.example.ignition.zerobus.pipeline;

import com.example.ignition.zerobus.ZerobusClientManager;
import com.example.ignition.zerobus.proto.OTEvent;

import java.util.List;

/**
 * EventSink implementation backed by the Databricks Zerobus SDK.
 */
public final class ZerobusEventSink implements EventSink {
    private final ZerobusClientManager client;

    public ZerobusEventSink(ZerobusClientManager client) {
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


