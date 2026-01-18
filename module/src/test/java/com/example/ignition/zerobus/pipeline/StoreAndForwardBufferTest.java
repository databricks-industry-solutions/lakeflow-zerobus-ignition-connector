package com.example.ignition.zerobus.pipeline;

import com.example.ignition.zerobus.ConfigModel;
import com.example.ignition.zerobus.TagEvent;
import com.example.ignition.zerobus.proto.OTEvent;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.nio.file.Path;
import java.util.Date;

import static org.junit.jupiter.api.Assertions.*;

public class StoreAndForwardBufferTest {

    @TempDir
    Path tempDir;

    private static OTEvent makeEvent(ConfigModel cfg, String tagPath, Object value) {
        TagEvent te = new TagEvent(tagPath, value, "Good", new Date());
        return new OtEventMapper(cfg).map(te);
    }

    @Test
    public void memoryMode_drainDoesNotRemoveUntilCommit() {
        ConfigModel cfg = new ConfigModel();
        cfg.setEnableStoreAndForward(false);
        cfg.setMaxQueueSize(100);
        StoreAndForwardBuffer buf = new StoreAndForwardBuffer(cfg);
        assertFalse(buf.isDiskBacked());

        OTEvent e1 = makeEvent(cfg, "[default]t1", 1);
        OTEvent e2 = makeEvent(cfg, "[default]t2", 2);
        assertTrue(buf.offer(e1));
        assertTrue(buf.offer(e2));

        StoreAndForwardBuffer.DrainResult d1 = buf.drain(2);
        assertEquals(2, d1.events.size());

        // Not committed: should return same events again
        StoreAndForwardBuffer.DrainResult d1Replay = buf.drain(2);
        assertEquals(2, d1Replay.events.size());

        // Commit removes from memory queue
        buf.commit(d1);
        StoreAndForwardBuffer.DrainResult d2 = buf.drain(2);
        assertTrue(d2.events.isEmpty());
    }

    @Test
    public void diskMode_drainDoesNotAdvanceUntilCommit() {
        ConfigModel cfg = new ConfigModel();
        cfg.setEnableStoreAndForward(true);
        cfg.setSpoolDirectory(tempDir.toString());
        cfg.setSpoolMaxBytes(50L * 1024 * 1024);
        cfg.setSpoolHighWatermarkPct(0.9);
        cfg.setSpoolLowWatermarkPct(0.5);
        cfg.setSpoolReadMaxBytes(5L * 1024 * 1024);

        StoreAndForwardBuffer buf = new StoreAndForwardBuffer(cfg);
        assertTrue(buf.isDiskBacked());

        OTEvent e1 = makeEvent(cfg, "[default]t1", 1);
        OTEvent e2 = makeEvent(cfg, "[default]t2", 2);
        assertTrue(buf.offer(e1));
        assertTrue(buf.offer(e2));

        StoreAndForwardBuffer.DrainResult d1 = buf.drain(1);
        assertEquals(1, d1.events.size());

        // Not committed: should re-read same first record again
        StoreAndForwardBuffer.DrainResult d1Replay = buf.drain(1);
        assertEquals(1, d1Replay.events.size());
        assertEquals(d1.events.get(0).getTagPath(), d1Replay.events.get(0).getTagPath());

        buf.commit(d1);
        StoreAndForwardBuffer.DrainResult d2 = buf.drain(10);
        assertEquals(1, d2.events.size());
        assertNotEquals(d1.events.get(0).getTagPath(), d2.events.get(0).getTagPath());
    }

    @Test
    public void diskMode_backpressurePauseAndResume() {
        ConfigModel cfg = new ConfigModel();
        cfg.setEnableStoreAndForward(true);
        cfg.setSpoolDirectory(tempDir.toString());
        cfg.setSpoolMaxBytes(1024 * 1024); // 1 MiB
        cfg.setSpoolHighWatermarkPct(0.50);
        cfg.setSpoolLowWatermarkPct(0.25);
        cfg.setSpoolReadMaxBytes(1024 * 1024);

        StoreAndForwardBuffer buf = new StoreAndForwardBuffer(cfg);
        assertTrue(buf.isDiskBacked());

        // Fill with ~600KB of events so we cross high watermark (~512KB)
        byte[] payload = new byte[50 * 1024]; // 50KB
        for (int i = 0; i < 13; i++) { // ~650KB
            OTEvent e = OTEvent.newBuilder()
                    .setEventId("e" + i)
                    .setEventTime(1)
                    .setTagPath("t" + i)
                    .setTagProvider("default")
                    .setQuality("Good")
                    .setQualityCode(192)
                    .setSourceSystem("s")
                    .setIngestionTimestamp(1)
                    .setDataType("STRING")
                    .setNumericValue(0.0)
                    .setStringValue(new String(payload))
                    .setBooleanValue(false)
                    .setAlarmState("")
                    .setAlarmPriority(0)
                    .build();
            assertTrue(buf.offer(e));
        }

        buf.refreshBackpressure();
        assertTrue(buf.isPaused(), "Should pause when above high watermark");

        // Drain+commit enough to drop below low watermark (commit all)
        StoreAndForwardBuffer.DrainResult d;
        do {
            d = buf.drain(50);
            if (!d.events.isEmpty()) {
                buf.commit(d);
            }
        } while (!d.events.isEmpty());

        buf.refreshBackpressure();
        assertFalse(buf.isPaused(), "Should resume when below low watermark");
    }
}


