package com.example.ignition.zerobus.pipeline;

import com.example.ignition.zerobus.ConfigModel;
import com.example.ignition.zerobus.ZerobusClientManager;

import java.util.Objects;

/**
 * Central wiring for the adapter -> buffer -> sink pipeline.
 *
 * Keeps construction decisions (disk spool vs memory, which sink, etc.) outside of services
 * like TagSubscriptionService so those services remain easy to test and reason about.
 */
public final class ZerobusPipelineFactory {
    private ZerobusPipelineFactory() {}

    public static PipelineComponents create(ConfigModel config, ZerobusClientManager clientManager) {
        Objects.requireNonNull(config, "config");
        Objects.requireNonNull(clientManager, "clientManager");
        OtEventMapper mapper = new OtEventMapper(config);
        StoreAndForwardBuffer buffer = new StoreAndForwardBuffer(config);
        EventSink sink = new ZerobusEventSink(clientManager);
        return new PipelineComponents(mapper, buffer, sink);
    }

    public static final class PipelineComponents {
        public final OtEventMapper mapper;
        public final StoreAndForwardBuffer buffer;
        public final EventSink sink;

        public PipelineComponents(OtEventMapper mapper, StoreAndForwardBuffer buffer, EventSink sink) {
            this.mapper = Objects.requireNonNull(mapper, "mapper");
            this.buffer = Objects.requireNonNull(buffer, "buffer");
            this.sink = Objects.requireNonNull(sink, "sink");
        }
    }
}


