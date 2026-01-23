package com.example.ignition.zerobus.saf;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.EOFException;
import java.io.File;
import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.util.ArrayList;
import java.util.List;

/**
 * Minimal disk-backed append-only spool for store-and-forward.
 *
 * Format: [int32 length][bytes...], repeated.
 *
 * This provides at-least-once delivery when paired with "commit after successful send".
 * If the gateway crashes after sending but before commit, records may be replayed (duplicates),
 * so downstream should ideally deduplicate using event_id if needed.
 */
public final class DiskSpool {
    private static final Logger logger = LoggerFactory.getLogger(DiskSpool.class);

    private final Path dir;
    private final Path dataFile;
    private final Path metaFile;

    private long readOffset = 0L;

    public DiskSpool(Path dir) throws IOException {
        this.dir = dir;
        Files.createDirectories(dir);
        this.dataFile = dir.resolve("spool.dat");
        this.metaFile = dir.resolve("spool.meta");
        loadMeta();
    }

    public synchronized void append(byte[] payload) throws IOException {
        if (payload == null) {
            return;
        }
        try (FileChannel ch = FileChannel.open(dataFile, StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.APPEND)) {
            ByteBuffer len = ByteBuffer.allocate(4);
            len.putInt(payload.length);
            len.flip();
            ch.write(len);
            ch.write(ByteBuffer.wrap(payload));
            ch.force(false);
        }
    }

    public synchronized long backlogBytes() throws IOException {
        long size = Files.exists(dataFile) ? Files.size(dataFile) : 0L;
        return Math.max(0L, size - readOffset);
    }

    /**
     * Read up to maxRecords records from the current read offset without committing them.
     * Returns a batch with a "nextOffset" that the caller can commit after a successful send.
     */
    public synchronized ReadBatch readBatch(int maxRecords, long maxBytes) throws IOException {
        maxRecords = Math.max(1, maxRecords);
        maxBytes = Math.max(1024L, maxBytes);

        if (!Files.exists(dataFile)) {
            return new ReadBatch(List.of(), readOffset);
        }

        long fileSize = Files.size(dataFile);
        if (readOffset >= fileSize) {
            return new ReadBatch(List.of(), readOffset);
        }

        List<byte[]> out = new ArrayList<>(Math.min(maxRecords, 1024));
        long off = readOffset;
        long bytesRead = 0L;

        try (RandomAccessFile raf = new RandomAccessFile(dataFile.toFile(), "r");
             FileChannel ch = raf.getChannel()) {
            ch.position(off);
            for (int i = 0; i < maxRecords; i++) {
                if (bytesRead >= maxBytes) {
                    break;
                }
                // Track the start of this record so we can safely truncate corrupted tails.
                long recordStart = ch.position();
                try {
                    ByteBuffer lenBuf = ByteBuffer.allocate(4);
                    int n = ch.read(lenBuf);
                    if (n < 0) {
                        break;
                    }
                    if (n < 4) {
                        // Partial length at end-of-file: treat as a corrupted tail and truncate.
                        truncateCorruptTail(recordStart, "Truncated record length at offset " + recordStart);
                        break;
                    }
                    lenBuf.flip();
                    int len = lenBuf.getInt();
                    if (len < 0 || len > (32 * 1024 * 1024)) {
                        // Garbage length typically indicates a partial write or corruption.
                        truncateCorruptTail(recordStart, "Invalid record length " + len + " at offset " + recordStart);
                        break;
                    }
                    ByteBuffer payload = ByteBuffer.allocate(len);
                    int m = ch.read(payload);
                    if (m < len) {
                        // Partial payload at end-of-file: truncate and stop.
                        truncateCorruptTail(recordStart, "Truncated record payload at offset " + (recordStart + 4));
                        break;
                    }
                    payload.flip();
                    byte[] b = new byte[len];
                    payload.get(b);
                    out.add(b);

                    off = ch.position();
                    bytesRead += (4L + len);
                } catch (EOFException eof) {
                    truncateCorruptTail(recordStart, eof.getMessage() == null ? "Truncated record at offset " + recordStart : eof.getMessage());
                    break;
                } catch (IOException ioe) {
                    truncateCorruptTail(recordStart, ioe.getMessage() == null ? "Corrupt record at offset " + recordStart : ioe.getMessage());
                    break;
                }
            }
        }

        return new ReadBatch(out, off);
    }

    public synchronized void commit(long newReadOffset) throws IOException {
        if (newReadOffset < readOffset) {
            return;
        }
        this.readOffset = newReadOffset;
        persistMeta();
        maybeCompact();
    }

    private void maybeCompact() {
        try {
            if (!Files.exists(dataFile)) {
                return;
            }
            long size = Files.size(dataFile);
            // compact if we've consumed >64MB and >50% of file
            if (readOffset < (64L * 1024 * 1024)) {
                return;
            }
            if (readOffset < (size / 2)) {
                return;
            }

            Path tmp = dir.resolve("spool.compacting");
            try (RandomAccessFile raf = new RandomAccessFile(dataFile.toFile(), "r");
                 FileChannel in = raf.getChannel();
                 FileChannel out = FileChannel.open(tmp, StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.TRUNCATE_EXISTING)) {
                in.position(readOffset);
                long toCopy = size - readOffset;
                long copied = 0L;
                while (copied < toCopy) {
                    long n = in.transferTo(in.position(), toCopy - copied, out);
                    if (n <= 0) break;
                    in.position(in.position() + n);
                    copied += n;
                }
                out.force(false);
            }

            Files.move(tmp, dataFile, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
            readOffset = 0L;
            persistMeta();
            logger.info("Compacted spool: previousSize={} bytes", size);
        } catch (Throwable t) {
            logger.warn("Spool compaction failed (ignored)", t);
        }
    }

    private void loadMeta() throws IOException {
        if (!Files.exists(metaFile)) {
            this.readOffset = 0L;
            return;
        }
        try {
            String s = Files.readString(metaFile).trim();
            // format: single number (readOffset)
            this.readOffset = Long.parseLong(s);
        } catch (Exception e) {
            this.readOffset = 0L;
        }
    }

    private void persistMeta() throws IOException {
        Files.writeString(metaFile, Long.toString(readOffset), StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.TRUNCATE_EXISTING);
    }

    /**
     * Best-effort self-healing for corrupted spools:
     * If we encounter an invalid/truncated record, we assume corruption is in the tail and truncate the
     * spool file back to the start of the problematic record so we can continue appending and draining.
     *
     * This sacrifices the corrupt tail record(s) but keeps the spool usable without manual intervention.
     */
    private void truncateCorruptTail(long truncateToOffset, String reason) {
        try {
            // Never truncate below the current committed offset.
            long safeOffset = Math.max(0L, Math.max(readOffset, truncateToOffset));
            long size = Files.exists(dataFile) ? Files.size(dataFile) : 0L;
            if (safeOffset >= size) {
                return;
            }
            try (FileChannel out = FileChannel.open(dataFile, StandardOpenOption.WRITE)) {
                out.truncate(safeOffset);
                out.force(false);
            }
            logger.warn("Detected corrupted spool tail; truncated spool.dat from {} bytes to {} bytes. Reason: {}", size, safeOffset, reason);
        } catch (Throwable t) {
            logger.warn("Failed truncating corrupted spool tail (ignored). Reason was: {}", reason, t);
        }
    }

    public static Path resolveDir(String configuredPath) {
        if (configuredPath == null || configuredPath.isBlank()) {
            configuredPath = "data/zerobus-spool";
        }
        Path p = Path.of(configuredPath);
        if (p.isAbsolute()) {
            return p;
        }
        // Interpret relative paths from current working directory (Ignition install dir).
        return new File(configuredPath).toPath().toAbsolutePath().normalize();
    }

    /**
     * Simple value object representing a read batch and the next read offset to commit on success.
     *
     * Note: we intentionally avoid Java "record" here because Ignition module builds commonly target
     * Java 11 bytecode/source compatibility.
     */
    public static final class ReadBatch {
        private final List<byte[]> records;
        private final long nextOffset;

        public ReadBatch(List<byte[]> records, long nextOffset) {
            this.records = records;
            this.nextOffset = nextOffset;
        }

        public List<byte[]> records() {
            return records;
        }

        public long nextOffset() {
            return nextOffset;
        }
    }
}


