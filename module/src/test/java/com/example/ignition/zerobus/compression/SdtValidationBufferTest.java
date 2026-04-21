package com.example.ignition.zerobus.compression;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

public class SdtValidationBufferTest {

    private SdtValidationBuffer buffer;

    @BeforeEach
    void setUp() {
        buffer = new SdtValidationBuffer(5);
    }

    @Test
    void constructorRejectsZeroCapacity() {
        assertThrows(IllegalArgumentException.class, () -> new SdtValidationBuffer(0));
        assertThrows(IllegalArgumentException.class, () -> new SdtValidationBuffer(-1));
    }

    @Test
    void emptyBufferReturnsEmptyList() {
        assertTrue(buffer.getPoints().isEmpty());
        assertTrue(buffer.getPivots().isEmpty());
        assertEquals(0, buffer.size());
    }

    @Test
    void addAndRetrievePoints() {
        buffer.addRawPoint(1000, 10.0);
        buffer.addRawPoint(2000, 20.0);
        buffer.addRawPoint(3000, 30.0);

        List<SdtValidationBuffer.DataPoint> points = buffer.getPoints();
        assertEquals(3, points.size());
        assertEquals(3, buffer.size());
        assertEquals(1000, points.get(0).timestampMs);
        assertEquals(10.0, points.get(0).value);
        assertFalse(points.get(0).isPivot);
    }

    @Test
    void markLastAsPivot() {
        buffer.addRawPoint(1000, 10.0);
        buffer.addRawPoint(2000, 20.0);
        buffer.markLastAsPivot();

        List<SdtValidationBuffer.DataPoint> points = buffer.getPoints();
        assertFalse(points.get(0).isPivot);
        assertTrue(points.get(1).isPivot);
    }

    @Test
    void markLastAsPivotOnEmptyBufferIsSafe() {
        // Should not throw
        buffer.markLastAsPivot();
        assertEquals(0, buffer.size());
    }

    @Test
    void getPivotsReturnsOnlyPivots() {
        buffer.addRawPoint(1000, 10.0);
        buffer.markLastAsPivot();
        buffer.addRawPoint(2000, 20.0);
        buffer.addRawPoint(3000, 30.0);
        buffer.markLastAsPivot();

        List<SdtValidationBuffer.DataPoint> pivots = buffer.getPivots();
        assertEquals(2, pivots.size());
        assertEquals(1000, pivots.get(0).timestampMs);
        assertEquals(3000, pivots.get(1).timestampMs);
    }

    @Test
    void capacityOverflowWrapsAround() {
        // Buffer capacity is 5
        for (int i = 1; i <= 7; i++) {
            buffer.addRawPoint(i * 1000, i * 10.0);
        }

        // Should have the last 5 points
        assertEquals(5, buffer.size());
        List<SdtValidationBuffer.DataPoint> points = buffer.getPoints();
        assertEquals(5, points.size());
        assertEquals(3000, points.get(0).timestampMs);  // oldest remaining
        assertEquals(7000, points.get(4).timestampMs);  // newest
    }

    @Test
    void capacityOverflowPreservesChronologicalOrder() {
        for (int i = 1; i <= 8; i++) {
            buffer.addRawPoint(i * 100, i * 1.0);
        }

        List<SdtValidationBuffer.DataPoint> points = buffer.getPoints();
        for (int i = 1; i < points.size(); i++) {
            assertTrue(points.get(i).timestampMs > points.get(i - 1).timestampMs,
                    "Points should be in chronological order");
        }
    }

    @Test
    void clearResetsBuffer() {
        buffer.addRawPoint(1000, 10.0);
        buffer.addRawPoint(2000, 20.0);
        buffer.markLastAsPivot();

        buffer.clear();
        assertEquals(0, buffer.size());
        assertTrue(buffer.getPoints().isEmpty());
        assertTrue(buffer.getPivots().isEmpty());
    }

    @Test
    void clearAllowsReuse() {
        buffer.addRawPoint(1000, 10.0);
        buffer.clear();

        buffer.addRawPoint(2000, 20.0);
        assertEquals(1, buffer.size());
        assertEquals(2000, buffer.getPoints().get(0).timestampMs);
    }

    @Test
    void markPointAsPivotByTimestamp() {
        buffer.addRawPoint(1000, 10.0);
        buffer.addRawPoint(2000, 20.0);
        buffer.addRawPoint(3000, 30.0);

        // Mark the middle point as pivot by its timestamp
        buffer.markPointAsPivot(2000);

        List<SdtValidationBuffer.DataPoint> points = buffer.getPoints();
        assertFalse(points.get(0).isPivot);
        assertTrue(points.get(1).isPivot);
        assertFalse(points.get(2).isPivot);
    }

    @Test
    void markPointAsPivotNonexistentTimestampIsSafe() {
        buffer.addRawPoint(1000, 10.0);
        // Should not throw
        buffer.markPointAsPivot(9999);
        assertFalse(buffer.getPoints().get(0).isPivot);
    }

    @Test
    void markPivotThenOverflow() {
        // Add 3 points, mark second as pivot
        buffer.addRawPoint(1000, 10.0);
        buffer.addRawPoint(2000, 20.0);
        buffer.markLastAsPivot();
        buffer.addRawPoint(3000, 30.0);

        // Overflow the pivot out by adding more points
        for (int i = 4; i <= 8; i++) {
            buffer.addRawPoint(i * 1000, i * 10.0);
        }

        // The pivot at ts=2000 should have been evicted
        List<SdtValidationBuffer.DataPoint> pivots = buffer.getPivots();
        assertTrue(pivots.isEmpty() || pivots.get(0).timestampMs > 2000);
    }
}
