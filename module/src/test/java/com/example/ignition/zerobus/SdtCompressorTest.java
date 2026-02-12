package com.example.ignition.zerobus;

import org.junit.jupiter.api.Test;

import java.util.Date;

import static org.junit.jupiter.api.Assertions.*;

public class SdtCompressorTest {

    private static TagEvent te(String path, double v, long tMs) {
        return new TagEvent(path, v, "Good", new Date(tMs));
    }

    @Test
    void firstSampleEmits() {
        SdtCompressor.State s = new SdtCompressor.State();
        SdtCompressor.Outcome o = s.offer(te("t", 1.0, 1000L), 0.1, 0, 0);
        assertNotNull(o);
        assertNotNull(o.emit);
        assertEquals(1.0, ((Number) o.emit.getValue()).doubleValue(), 1e-9);
        assertFalse(o.forcedByMaxInterval);
        assertFalse(o.resetDueToOutOfOrder);
    }

    @Test
    void linearWithinDeviationDoesNotEmit() {
        SdtCompressor.State s = new SdtCompressor.State();
        String path = "t";
        double dev = 1.0;

        assertNotNull(s.offer(te(path, 0.0, 0L), dev, 0, 0).emit);
        assertNull(s.offer(te(path, 0.2, 1000L), dev, 0, 0).emit);
        assertNull(s.offer(te(path, 0.4, 2000L), dev, 0, 0).emit);
        assertNull(s.offer(te(path, 0.6, 3000L), dev, 0, 0).emit);
    }

    @Test
    void doorClosureEmitsPreviousPoint() {
        SdtCompressor.State s = new SdtCompressor.State();
        String path = "t";
        double dev = 0.1;

        // Anchor
        assertNotNull(s.offer(te(path, 0.0, 0L), dev, 0, 0).emit);

        // A stable point (should not emit)
        assertNull(s.offer(te(path, 0.0, 1000L), dev, 0, 0).emit);

        // Large jump should close the door and emit the previous point (t=1000)
        SdtCompressor.Outcome o = s.offer(te(path, 10.0, 2000L), dev, 0, 0);
        assertNotNull(o.emit);
        assertEquals(0.0, ((Number) o.emit.getValue()).doubleValue(), 1e-9);
        assertEquals(1000L, o.emit.getTimestamp().getTime());
    }

    @Test
    void maxIntervalForcesEmit() {
        SdtCompressor.State s = new SdtCompressor.State();
        String path = "t";
        double dev = 1.0;

        assertNotNull(s.offer(te(path, 5.0, 0L), dev, 1000, 0).emit);
        // No change within interval -> no emit
        assertNull(s.offer(te(path, 5.0, 500L), dev, 1000, 0).emit);

        // At interval boundary -> forced emit
        SdtCompressor.Outcome forced = s.offer(te(path, 5.0, 1000L), dev, 1000, 0);
        assertNotNull(forced.emit);
        assertTrue(forced.forcedByMaxInterval);
    }

    @Test
    void outOfOrderResetsAndEmitsCurrent() {
        SdtCompressor.State s = new SdtCompressor.State();
        String path = "t";

        assertNotNull(s.offer(te(path, 1.0, 1000L), 0.1, 0, 0).emit);

        SdtCompressor.Outcome o = s.offer(te(path, 2.0, 900L), 0.1, 0, 0);
        assertNotNull(o.emit);
        assertTrue(o.resetDueToOutOfOrder);
        assertEquals(900L, o.emit.getTimestamp().getTime());
    }

    @Test
    void minIntervalSuppressesEmits() {
        SdtCompressor.State s = new SdtCompressor.State();
        String path = "t";
        double dev = 0.1;
        long maxInterval = 0L;
        long minInterval = 1000L;

        assertNotNull(s.offer(te(path, 1.0, 0L), dev, maxInterval, minInterval).emit);
        // Within min interval: suppress even if value changes a lot
        assertNull(s.offer(te(path, 10.0, 500L), dev, maxInterval, minInterval).emit);
        // After min interval window: normal SDT evaluation resumes (this may emit due to door closure)
        SdtCompressor.Outcome o = s.offer(te(path, 10.0, 1500L), dev, maxInterval, minInterval);
        assertNotNull(o);
    }
}

