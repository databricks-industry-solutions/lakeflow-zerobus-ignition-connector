package com.example.ignition.zerobus.compression;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

/**
 * Per-tag circular buffer storing the last N data points for SDT validation.
 *
 * Each point records its raw value, timestamp, and whether it was emitted as
 * a pivot by the SDT compressor.
 */
public class SdtValidationBuffer {
    private final int capacity;
    private final DataPoint[] ring;
    private int head = 0;  // next write position
    private int size = 0;

    public SdtValidationBuffer(int capacity) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity must be > 0");
        }
        this.capacity = capacity;
        this.ring = new DataPoint[capacity];
    }

    /**
     * Append a raw data point before the SDT decision.
     */
    public synchronized void addRawPoint(long timestampMs, double value) {
        ring[head] = new DataPoint(timestampMs, value, false);
        head = (head + 1) % capacity;
        if (size < capacity) {
            size++;
        }
    }

    /**
     * Flag the most recently added point as a pivot (called when SDT emits the current point).
     */
    public synchronized void markLastAsPivot() {
        if (size == 0) {
            return;
        }
        int lastIndex = (head - 1 + capacity) % capacity;
        DataPoint last = ring[lastIndex];
        if (last != null) {
            ring[lastIndex] = new DataPoint(last.timestampMs, last.value, true);
        }
    }

    /**
     * Flag a previously added point as a pivot by matching its timestamp.
     * Scans backward from the most recent entry. Used when the emitted point
     * is not the most recently added one.
     */
    public synchronized void markPointAsPivot(long timestampMs) {
        if (size == 0) {
            return;
        }

        for (int i = size - 1; i >= 0; i--) {
            int idx = (size < capacity)
                    ? i
                    : (head + i) % capacity;
            DataPoint pt = ring[idx];
            if (pt != null && pt.timestampMs == timestampMs) {
                ring[idx] = new DataPoint(pt.timestampMs, pt.value, true);
                return;
            }
        }
    }

    /**
     * Return a snapshot of all buffered points in chronological order.
     */
    public synchronized List<DataPoint> getPoints() {
        List<DataPoint> result = new ArrayList<>(size);
        if (size == 0) {
            return result;
        }
        int start = (size < capacity) ? 0 : head;
        for (int i = 0; i < size; i++) {
            result.add(ring[(start + i) % capacity]);
        }
        return result;
    }

    /**
     * Return only pivot points in chronological order.
     */
    public synchronized List<DataPoint> getPivots() {
        return getPoints().stream()
                .filter(p -> p.isPivot)
                .collect(Collectors.toList());
    }

    /**
     * Clear all buffered points.
     */
    public synchronized void clear() {
        for (int i = 0; i < capacity; i++) {
            ring[i] = null;
        }
        head = 0;
        size = 0;
    }

    /**
     * Return the number of buffered points.
     */
    public synchronized int size() {
        return size;
    }

    /**
     * Immutable data point stored in the validation buffer.
     */
    public static final class DataPoint {
        public final long timestampMs;
        public final double value;
        public final boolean isPivot;

        public DataPoint(long timestampMs, double value, boolean isPivot) {
            this.timestampMs = timestampMs;
            this.value = value;
            this.isPivot = isPivot;
        }
    }
}

