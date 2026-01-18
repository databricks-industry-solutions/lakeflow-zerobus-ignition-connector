package com.example.ignition.zerobus.saf;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

public class DiskSpoolTest {

    @TempDir
    Path tempDir;

    @Test
    public void appendReadCommit_replaysUntilCommitted() throws Exception {
        DiskSpool spool = new DiskSpool(tempDir);

        spool.append("a".getBytes());
        spool.append("bb".getBytes());
        spool.append("ccc".getBytes());

        long backlog1 = spool.backlogBytes();
        assertTrue(backlog1 > 0, "Backlog should be > 0 after appends");

        DiskSpool.ReadBatch b1 = spool.readBatch(2, 1024);
        assertEquals(2, b1.records().size());
        assertArrayEquals("a".getBytes(), b1.records().get(0));
        assertArrayEquals("bb".getBytes(), b1.records().get(1));

        // Not committed: should return same first records again
        DiskSpool.ReadBatch b1Replay = spool.readBatch(2, 1024);
        assertEquals(2, b1Replay.records().size());
        assertArrayEquals("a".getBytes(), b1Replay.records().get(0));
        assertArrayEquals("bb".getBytes(), b1Replay.records().get(1));

        // Commit advances cursor
        spool.commit(b1.nextOffset());
        DiskSpool.ReadBatch b2 = spool.readBatch(10, 1024);
        assertEquals(1, b2.records().size());
        assertArrayEquals("ccc".getBytes(), b2.records().get(0));

        // Commit remaining; subsequent reads empty
        spool.commit(b2.nextOffset());
        DiskSpool.ReadBatch empty = spool.readBatch(10, 1024);
        assertTrue(empty.records().isEmpty());
        assertEquals(empty.nextOffset(), b2.nextOffset());
    }

    @Test
    public void loadMeta_persistsReadOffsetAcrossInstances() throws Exception {
        DiskSpool spool1 = new DiskSpool(tempDir);
        spool1.append("one".getBytes());
        spool1.append("two".getBytes());

        DiskSpool.ReadBatch b = spool1.readBatch(1, 1024);
        assertEquals(1, b.records().size());
        spool1.commit(b.nextOffset());

        // New instance should load readOffset from meta file
        DiskSpool spool2 = new DiskSpool(tempDir);
        DiskSpool.ReadBatch b2 = spool2.readBatch(10, 1024);
        assertEquals(1, b2.records().size());
        assertArrayEquals("two".getBytes(), b2.records().get(0));
    }

    @Test
    public void resolveDir_relativePathBecomesAbsolute() throws IOException {
        Path p = DiskSpool.resolveDir("data/zerobus-spool-test");
        assertTrue(p.isAbsolute());
        // Ensure normalize doesn't produce empty
        assertFalse(p.toString().isEmpty());
    }

    @Test
    public void readBatch_emptyWhenNoData() throws Exception {
        DiskSpool spool = new DiskSpool(tempDir);
        DiskSpool.ReadBatch empty = spool.readBatch(10, 1024);
        assertEquals(List.of(), empty.records());
        // offset remains 0
        assertEquals(0L, empty.nextOffset());
    }

    @Test
    public void commit_isMonotonic() throws Exception {
        DiskSpool spool = new DiskSpool(tempDir);
        spool.append("x".getBytes());
        DiskSpool.ReadBatch b = spool.readBatch(1, 1024);
        long off = b.nextOffset();
        spool.commit(off);

        // committing a smaller offset should be ignored
        spool.commit(off - 1);
        // Still empty
        DiskSpool.ReadBatch empty = spool.readBatch(1, 1024);
        assertTrue(empty.records().isEmpty());
    }

    @Test
    public void compaction_doesNotCorruptData() throws Exception {
        DiskSpool spool = new DiskSpool(tempDir);

        // Create > 64MB so compaction threshold can trigger when readOffset >= 64MB and >= 50% of file.
        byte[] payload = new byte[1024 * 1024]; // 1 MiB record
        for (int i = 0; i < 80; i++) { // ~80 MiB + headers
            payload[0] = (byte) i;
            spool.append(payload);
        }

        // Read and commit ~70 records => readOffset > 64MB and > 50% file
        long committedOffset = 0L;
        for (int i = 0; i < 70; i++) {
            DiskSpool.ReadBatch b = spool.readBatch(1, 2L * 1024 * 1024);
            assertEquals(1, b.records().size());
            committedOffset = b.nextOffset();
            spool.commit(committedOffset);
        }

        // After compaction, spool.dat should still exist and backlog should be non-negative.
        assertTrue(Files.exists(tempDir.resolve("spool.dat")));
        assertTrue(spool.backlogBytes() >= 0);

        // Remaining records should still be readable.
        DiskSpool.ReadBatch remaining = spool.readBatch(20, 25L * 1024 * 1024);
        assertFalse(remaining.records().isEmpty(), "Should still have remaining records after commits/compaction");
    }
}


