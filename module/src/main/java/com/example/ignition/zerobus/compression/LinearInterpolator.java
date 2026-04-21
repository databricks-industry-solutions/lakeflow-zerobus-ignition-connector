package com.example.ignition.zerobus.compression;

import java.util.List;

/**
 * Stateless utility for linear interpolation between pivot points.
 *
 * Given a sorted list of pivot points and a query timestamp, returns
 * the linearly interpolated value.
 */
public final class LinearInterpolator {
    private LinearInterpolator() {}

    public static Double interpolate(List<SdtValidationBuffer.DataPoint> pivots, long queryTimestampMs) {
        if (pivots == null || pivots.isEmpty()) {
            return null;
        }

        // Before first pivot: no data to interpolate from
        if (queryTimestampMs < pivots.get(0).timestampMs) {
            return null;
        }

        // Walk through pivots to find the surrounding pair
        for (int i = 0; i < pivots.size() - 1; i++) {
            SdtValidationBuffer.DataPoint p1 = pivots.get(i);
            SdtValidationBuffer.DataPoint p2 = pivots.get(i + 1);

            // Exact match on this pivot
            if (queryTimestampMs == p1.timestampMs) {
                return p1.value;
            }

            // Between p1 and p2: linear interpolation
            if (queryTimestampMs > p1.timestampMs && queryTimestampMs <= p2.timestampMs) {
                if (queryTimestampMs == p2.timestampMs) {
                    return p2.value;
                }
                long dt = p2.timestampMs - p1.timestampMs;
                if (dt == 0) {
                    return p1.value;
                }
                double fraction = (double) (queryTimestampMs - p1.timestampMs) / dt;
                return p1.value + (p2.value - p1.value) * fraction;
            }
        }

        // Exact match on last pivot, or after last pivot: hold last value
        return pivots.get(pivots.size() - 1).value;
    }
}

