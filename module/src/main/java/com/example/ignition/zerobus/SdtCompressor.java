package com.example.ignition.zerobus;

import java.util.Date;

/**
 * PI-like Swinging Door Trending (SDT) compressor for a single tag stream.
 *
 * Semantics:
 * - Maintains a door (line segment) anchored at the last emitted point with an error band ±deviation.
 * - When a new point would cause the door to close (slope bounds cross), emit the previous point
 *   as the closing point, reset the door at that point, then continue.
 * - If maxIntervalMs > 0, force an emit at least every maxIntervalMs.
 */
final class SdtCompressor {

    private SdtCompressor() {}

    static final class Outcome {
        final TagEvent emit; // null means "do not emit"
        final boolean forcedByMaxInterval;
        final boolean resetDueToOutOfOrder;

        Outcome(TagEvent emit, boolean forcedByMaxInterval, boolean resetDueToOutOfOrder) {
            this.emit = emit;
            this.forcedByMaxInterval = forcedByMaxInterval;
            this.resetDueToOutOfOrder = resetDueToOutOfOrder;
        }
    }

    static final class State {
        private boolean initialized = false;

        private long anchorTimeMs;
        private double anchorValue;

        private long prevTimeMs;
        private double prevValue;
        private String prevQuality;

        private double lowerSlope;
        private double upperSlope;

        private long lastEmitTimeMs;

        synchronized Outcome offer(TagEvent current, double deviation, long maxIntervalMs) {
            if (current == null || !(current.getValue() instanceof Number)) {
                return new Outcome(null, false, false);
            }

            long t = (current.getTimestamp() != null) ? current.getTimestamp().getTime() : System.currentTimeMillis();
            double v = ((Number) current.getValue()).doubleValue();
            String q = current.getQuality();

            if (!initialized) {
                initialized = true;
                anchorTimeMs = t;
                anchorValue = v;
                prevTimeMs = t;
                prevValue = v;
                prevQuality = q;
                lowerSlope = Double.NEGATIVE_INFINITY;
                upperSlope = Double.POSITIVE_INFINITY;
                lastEmitTimeMs = t;
                return new Outcome(current, false, false);
            }

            // Out-of-order timestamps: reset and emit current to keep monotonic archive semantics.
            if (t <= prevTimeMs) {
                anchorTimeMs = t;
                anchorValue = v;
                prevTimeMs = t;
                prevValue = v;
                prevQuality = q;
                lowerSlope = Double.NEGATIVE_INFINITY;
                upperSlope = Double.POSITIVE_INFINITY;
                lastEmitTimeMs = t;
                return new Outcome(current, false, true);
            }

            // Max-interval forcing: emit current and reset door.
            if (maxIntervalMs > 0 && (t - lastEmitTimeMs) >= maxIntervalMs) {
                anchorTimeMs = t;
                anchorValue = v;
                prevTimeMs = t;
                prevValue = v;
                prevQuality = q;
                lowerSlope = Double.NEGATIVE_INFINITY;
                upperSlope = Double.POSITIVE_INFINITY;
                lastEmitTimeMs = t;
                return new Outcome(current, true, false);
            }

            long dt = t - anchorTimeMs;
            if (dt <= 0) {
                anchorTimeMs = t;
                anchorValue = v;
                prevTimeMs = t;
                prevValue = v;
                prevQuality = q;
                lowerSlope = Double.NEGATIVE_INFINITY;
                upperSlope = Double.POSITIVE_INFINITY;
                lastEmitTimeMs = t;
                return new Outcome(current, false, true);
            }

            double sLow = (v - anchorValue - deviation) / (double) dt;
            double sHigh = (v - anchorValue + deviation) / (double) dt;
            lowerSlope = Math.max(lowerSlope, sLow);
            upperSlope = Math.min(upperSlope, sHigh);

            if (lowerSlope > upperSlope) {
                TagEvent closing = new TagEvent(
                        current.getTagPath(),
                        prevValue,
                        prevQuality,
                        new Date(prevTimeMs),
                        current.getAssetId(),
                        current.getAssetPath()
                );

                // Reset door at closing point.
                anchorTimeMs = prevTimeMs;
                anchorValue = prevValue;
                lowerSlope = Double.NEGATIVE_INFINITY;
                upperSlope = Double.POSITIVE_INFINITY;
                lastEmitTimeMs = prevTimeMs;

                // Incorporate current into new door (no emit here).
                prevTimeMs = t;
                prevValue = v;
                prevQuality = q;

                long dt2 = t - anchorTimeMs;
                if (dt2 > 0) {
                    double sLow2 = (v - anchorValue - deviation) / (double) dt2;
                    double sHigh2 = (v - anchorValue + deviation) / (double) dt2;
                    lowerSlope = Math.max(lowerSlope, sLow2);
                    upperSlope = Math.min(upperSlope, sHigh2);
                }

                return new Outcome(closing, false, false);
            }

            prevTimeMs = t;
            prevValue = v;
            prevQuality = q;
            return new Outcome(null, false, false);
        }
    }
}

