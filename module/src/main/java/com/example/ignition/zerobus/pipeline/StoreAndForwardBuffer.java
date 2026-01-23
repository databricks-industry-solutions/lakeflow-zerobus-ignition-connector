package com.example.ignition.zerobus.pipeline;

import com.example.ignition.zerobus.ConfigModel;
import com.example.ignition.zerobus.saf.DiskSpool;
import com.example.ignition.zerobus.proto.OTEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.List;
import java.util.concurrent.locks.ReentrantLock;

/**
 * Buffer abstraction that can be backed by memory or disk (store-and-forward).
 */
public final class StoreAndForwardBuffer {
    private static final Logger logger = LoggerFactory.getLogger(StoreAndForwardBuffer.class);

    private final ConfigModel config;
    private final DiskSpool spool; // nullable when disabled
    // In-memory mode must be commit-able (don't drop drained records on send failure)
    private final Deque<OTEvent> memQueue; // used when spool disabled
    private final ReentrantLock memLock = new ReentrantLock();

    private volatile boolean paused = false;

    public StoreAndForwardBuffer(ConfigModel config) {
        this.config = config;
        DiskSpool ds = null;
        if (config.isEnableStoreAndForward()) {
            try {
                ds = new DiskSpool(DiskSpool.resolveDir(config.getSpoolDirectory()));
                logger.info("Store-and-forward enabled. Spool dir={}", DiskSpool.resolveDir(config.getSpoolDirectory()));
            } catch (IOException e) {
                // No fallback: if SAF is enabled, disk spool must be available.
                throw new RuntimeException("Store-and-forward is enabled but disk spool could not be initialized: " + e.getMessage(), e);
            }
        }
        this.spool = ds;
        this.memQueue = (ds == null) ? new ArrayDeque<>() : null;
    }

    public boolean isDiskBacked() {
        return spool != null;
    }

    public boolean isPaused() {
        return paused;
    }

    public void refreshBackpressure() {
        if (spool == null) {
            paused = false;
            return;
        }
        try {
            long backlog = spool.backlogBytes();
            long max = Math.max(1024L, config.getSpoolMaxBytes());
            // Respect configured thresholds. Validation enforces (0,1) and low < high.
            double hiPct = config.getSpoolHighWatermarkPct();
            double loPct = config.getSpoolLowWatermarkPct();
            long hi = (long) (max * hiPct);
            long lo = (long) (max * loPct);
            if (!paused && backlog >= hi) {
                paused = true;
                logger.warn("Backpressure ON (spool backlog {} bytes >= high watermark {} bytes).", backlog, hi);
            } else if (paused && backlog <= lo) {
                paused = false;
                logger.info("Backpressure OFF (spool backlog {} bytes <= low watermark {} bytes).", backlog, lo);
            }
        } catch (Exception e) {
            // If we can't read spool metrics, do not pause; we still want to attempt draining.
            paused = false;
        }
    }

    public long backlogBytes() {
        try {
            if (spool != null) return spool.backlogBytes();
        } catch (Exception ignored) { }
        if (memQueue != null) return memQueueSize();
        return 0L;
    }

    /**
     * Enqueue an OTEvent. Returns false if rejected due to backpressure/capacity.
     */
    public boolean offer(OTEvent event) {
        if (event == null) return true;

        refreshBackpressure();

        // When disk spool is enabled, do not accept if hard max exceeded.
        if (spool != null) {
            try {
                long max = Math.max(1024L, config.getSpoolMaxBytes());
                long backlog = spool.backlogBytes();
                if (backlog >= max) {
                    return false;
                }
                spool.append(event.toByteArray());
                return true;
            } catch (Exception e) {
                logger.warn("Failed appending to spool; event dropped", e);
                return false;
            }
        }

        // In-memory mode
        memLock.lock();
        try {
            int cap = Math.max(1, config.getMaxQueueSize());
            if (memQueue.size() >= cap) {
                return false;
            }
            memQueue.addLast(event);
            return true;
        } finally {
            memLock.unlock();
        }
    }

    /**
     * Drain up to batchSize events. If disk-backed, returns a cursor allowing commit on success.
     */
    public DrainResult drain(int batchSize) {
        batchSize = Math.max(1, batchSize);

        if (spool != null) {
            try {
                // Cap batch bytes to avoid huge reads
                long maxBytes = Math.max(1L, config.getSpoolReadMaxBytes());
                DiskSpool.ReadBatch rb = spool.readBatch(batchSize, maxBytes);
                List<byte[]> raw = rb.records();
                List<OTEvent> events = new ArrayList<>(raw.size());
                int corrupt = 0;
                for (byte[] b : raw) {
                    try {
                        events.add(OTEvent.parseFrom(b));
                    } catch (Exception parseErr) {
                        corrupt++;
                        // NOTE: We intentionally do not fail the whole drain on a single corrupt record.
                        // We will advance the read offset past the corrupt bytes on the next successful commit.
                        logger.warn("Corrupt record found in spool; dropping record (parse failed): {}", parseErr.toString());
                    }
                }
                return new DrainResult(events, rb.nextOffset(), raw.size(), corrupt);
            } catch (Exception e) {
                logger.warn("Failed reading from spool", e);
                return new DrainResult(List.of(), -1L, 0, 0);
            }
        }

        // In-memory: return a preview batch; commit will remove.
        memLock.lock();
        try {
            if (memQueue.isEmpty()) {
                return new DrainResult(List.of(), 0L, 0, 0);
            }
            List<OTEvent> out = new ArrayList<>(Math.min(batchSize, memQueue.size()));
            int n = 0;
            for (OTEvent e : memQueue) {
                out.add(e);
                n++;
                if (n >= batchSize) break;
            }
            return new DrainResult(out, n, n, 0);
        } finally {
            memLock.unlock();
        }
    }

    public void commit(DrainResult drained) {
        if (drained == null) return;
        if (spool != null && drained.nextOffset >= 0) {
            try {
                spool.commit(drained.nextOffset);
            } catch (Exception e) {
                logger.warn("Failed committing spool offset (ignored)", e);
            }
            return;
        }
        // In-memory: nextOffset is count to remove from head.
        if (memQueue != null && drained.nextOffset > 0) {
            memLock.lock();
            try {
                long n = drained.nextOffset;
                while (n > 0 && !memQueue.isEmpty()) {
                    memQueue.removeFirst();
                    n--;
                }
            } finally {
                memLock.unlock();
            }
        }
    }

    private int memQueueSize() {
        memLock.lock();
        try {
            return memQueue.size();
        } finally {
            memLock.unlock();
        }
    }

    public static final class DrainResult {
        public final List<OTEvent> events;
        public final long nextOffset; // disk: commit cursor (byte offset), memory: count to remove
        /** Number of raw records read from the buffer (disk) or previewed from memory. */
        public final int recordsRead;
        /** Number of records that were dropped due to corruption (parse failures). */
        public final int corruptRecords;

        public DrainResult(List<OTEvent> events, long nextOffset, int recordsRead, int corruptRecords) {
            this.events = events;
            this.nextOffset = nextOffset;
            this.recordsRead = recordsRead;
            this.corruptRecords = corruptRecords;
        }
    }
}


