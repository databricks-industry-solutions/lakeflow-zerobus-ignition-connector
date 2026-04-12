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
        private long receivedCount;
        private long emittedCount;
        private long suppressedCount;

        private Outcome recordOutcome(TagEvent emit, boolean forcedByMaxInterval, boolean resetDueToOutOfOrder) {
            if (emit != null) {
                emittedCount++;
            } else {
                suppressedCount++;
            }
            return new Outcome(emit, forcedByMaxInterval, resetDueToOutOfOrder);
        }

        synchronized Outcome offer(TagEvent current, double deviation, long maxIntervalMs, long minIntervalMs) {
            if (current == null || !(current.getValue() instanceof Number)) {
                return new Outcome(null, false, false);
            }
            receivedCount++;

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
                return recordOutcome(current, false, false);
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
                return recordOutcome(current, false, true);
            }

            // Min-interval suppression (CompMin): don't emit anything too soon after the last emit.
            // Still track the latest value/time so the next evaluation uses a recent "previous" point.
            if (minIntervalMs > 0 && (t - lastEmitTimeMs) < minIntervalMs) {
                prevTimeMs = t;
                prevValue = v;
                prevQuality = q;
                return recordOutcome(null, false, false);
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
                return recordOutcome(current, true, false);
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
                return recordOutcome(current, false, true);
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

                return recordOutcome(closing, false, false);
            }

            prevTimeMs = t;
            prevValue = v;
            prevQuality = q;
            return recordOutcome(null, false, false);
        }

        synchronized long getReceivedCount() {
            return receivedCount;
        }

        synchronized long getEmittedCount() {
            return emittedCount;
        }

        synchronized long getSuppressedCount() {
            return suppressedCount;
        }

        synchronized double getCompressionRatioPct() {
            if (receivedCount <= 0L) {
                return 0.0;
            }
            return (double) suppressedCount * 100.0 / (double) receivedCount;
        }
    }
}

