package com.example.ignition.zerobus.pipeline;

import com.example.ignition.zerobus.proto.OTEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

/**
 * CompositeSink - Wrapper that sends events to multiple sinks in parallel.
 *
 * Sends events to all enabled sinks, logging failures per sink.
 * Returns true only if ALL sinks successfully received the events.
 */
public final class CompositeSink implements EventSink {

    private static final Logger logger = LoggerFactory.getLogger(CompositeSink.class);

    private final List<NamedSink> sinks;

    /**
     * A sink with a name for logging purposes.
     * Static class instead of record for Java 11 compatibility.
     */
    private static final class NamedSink {
        private final String name;
        private final EventSink sink;

        NamedSink(String name, EventSink sink) {
            this.name = name;
            this.sink = sink;
        }

        String getName() { return name; }

        EventSink getSink() { return sink; }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (!(o instanceof NamedSink)) return false;
            NamedSink that = (NamedSink) o;
            return Objects.equals(name, that.name) && Objects.equals(sink, that.sink);
        }

        @Override
        public int hashCode() {
            return Objects.hash(name, sink);
        }

        @Override
        public String toString() {
            return "NamedSink{name='" + name + "', sink=" + sink + "}";
        }
    }

    private CompositeSink(List<NamedSink> sinks) {
        this.sinks = new ArrayList<>(sinks);
    }

    /**
     * Builder for creating a CompositeSink with named sinks.
     */
    public static class Builder {
        private final List<NamedSink> sinks = new ArrayList<>();

        public Builder addSink(String name, EventSink sink) {
            if (sink != null) {
                sinks.add(new NamedSink(name, sink));
            }
            return this;
        }

        public CompositeSink build() {
            if (sinks.isEmpty()) {
                throw new IllegalStateException("CompositeSink requires at least one sink");
            }
            return new CompositeSink(sinks);
        }
    }

    public static Builder builder() {
        return new Builder();
    }

    @Override
    public boolean isReady() {
        // Ready if ANY sink is ready
        for (NamedSink ns : sinks) {
            if (ns.getSink().isReady()) {
                return true;
            }
        }
        return false;
    }

    @Override
    public boolean tryEnsureReady() {
        boolean anyReady = false;
        for (NamedSink ns : sinks) {
            try {
                if (ns.getSink().tryEnsureReady()) {
                    anyReady = true;
                }
            } catch (Exception e) {
                logger.warn("Failed to ensure {} sink is ready: {}", ns.getName(), e.getMessage());
            }
        }
        return anyReady;
    }

    @Override
    public boolean send(List<OTEvent> events) {
        if (events == null || events.isEmpty()) {
            return true;
        }

        boolean allSuccess = true;
        List<String> failures = new ArrayList<>();

        for (NamedSink ns : sinks) {
            try {
                boolean success = ns.getSink().send(events);
                if (success) {
                    logger.debug("Successfully sent {} events to {} sink", events.size(), ns.getName());
                } else {
                    allSuccess = false;
                    failures.add(ns.getName());
                    logger.warn("Failed to send {} events to {} sink (returned false)", events.size(), ns.getName());
                }
            } catch (Exception e) {
                allSuccess = false;
                failures.add(ns.getName());
                logger.error("Exception sending {} events to {} sink: {}", events.size(), ns.getName(), e.getMessage(), e);
            }
        }

        if (!failures.isEmpty()) {
            logger.warn("Sink failures: {}", failures);
        }

        // Return true only if ALL sinks succeeded (prevents buffer from committing partial deliveries)
        return allSuccess;
    }

    /**
     * Get the number of configured sinks.
     */
    public int getSinkCount() {
        return sinks.size();
    }

    /**
     * Get the names of configured sinks.
     */
    public List<String> getSinkNames() {
        List<String> names = new ArrayList<>();
        for (NamedSink ns : sinks) {
            names.add(ns.getName());
        }
        return names;
    }
}
