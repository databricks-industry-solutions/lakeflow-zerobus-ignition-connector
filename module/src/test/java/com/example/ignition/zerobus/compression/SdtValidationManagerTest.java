package com.example.ignition.zerobus.compression;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

public class SdtValidationManagerTest {

    private SdtValidationManager manager;

    @BeforeEach
    void setUp() {
        manager = new SdtValidationManager(100);
    }

    @Test
    void emptyManagerGeneratesEmptyReport() {
        SdtValidationReport report = manager.generateReport(1.0, 300, 20, 10);
        assertTrue(report.enabled);
        assertEquals(0, report.trackedTags);
        assertEquals("PASS", report.overallVerdict);
        assertTrue(report.tags.isEmpty());
    }

    @Test
    void recordAndMarkPivots() {
        manager.recordRawPoint("tag1", 1000, 10.0);
        manager.markPivot("tag1");
        manager.recordRawPoint("tag1", 2000, 15.0);
        manager.recordRawPoint("tag1", 3000, 20.0);
        manager.markPivot("tag1");

        assertEquals(1, manager.getTrackedTagCount());

        SdtValidationReport report = manager.generateReport(5.0, 300, 20, 100);
        assertEquals(1, report.tags.size());

        SdtValidationReport.TagValidation tv = report.tags.get(0);
        assertEquals("tag1", tv.tagPath);
        assertEquals(3, tv.rawPointCount);
        assertEquals(2, tv.pivotCount);
    }

    @Test
    void linearInterpolationWithinDeviation() {
        // Simulate a linear ramp: pivots at start and end, intermediate points should be exact
        double deviation = 1.0;

        // Record raw points: linear ramp 0 -> 100
        for (int i = 0; i <= 10; i++) {
            manager.recordRawPoint("ramp", i * 1000, i * 10.0);
            // Mark first and last as pivots
            if (i == 0 || i == 10) {
                manager.markPivot("ramp");
            }
        }

        SdtValidationReport report = manager.generateReport(deviation, 300, 20, 100);
        SdtValidationReport.TagValidation tv = report.tags.get(0);

        // Interpolation of a perfect linear ramp from two endpoints should produce zero error
        assertEquals(0.0, tv.maxAbsError, 0.001);
        assertTrue(tv.withinDeviation);
        assertEquals("PASS", report.overallVerdict);
    }

    @Test
    void errorExceedsDeviationProducesFail() {
        double deviation = 0.5;

        // Two pivots: (0, 0) and (1000, 10)
        manager.recordRawPoint("noisy", 0, 0.0);
        manager.markPivot("noisy");

        // Intermediate point deviates from the interpolated line by 5.0
        // Interpolated at t=500 would be 5.0, but raw is 10.0
        manager.recordRawPoint("noisy", 500, 10.0);

        manager.recordRawPoint("noisy", 1000, 10.0);
        manager.markPivot("noisy");

        SdtValidationReport report = manager.generateReport(deviation, 300, 20, 100);
        SdtValidationReport.TagValidation tv = report.tags.get(0);

        assertTrue(tv.maxAbsError > deviation);
        assertFalse(tv.withinDeviation);
        assertEquals("FAIL", report.overallVerdict);
    }

    @Test
    void compressionRatioCalculation() {
        // 5 raw points, 2 pivots = (1 - 2/5) * 100 = 60%
        manager.recordRawPoint("tag1", 1000, 1.0);
        manager.markPivot("tag1");
        manager.recordRawPoint("tag1", 2000, 2.0);
        manager.recordRawPoint("tag1", 3000, 3.0);
        manager.recordRawPoint("tag1", 4000, 4.0);
        manager.recordRawPoint("tag1", 5000, 5.0);
        manager.markPivot("tag1");

        SdtValidationReport report = manager.generateReport(10.0, 300, 20, 100);
        assertEquals(60.0, report.tags.get(0).compressionRatioPct, 0.01);
    }

    @Test
    void maxTagsLimitsOutput() {
        for (int i = 0; i < 10; i++) {
            String tag = "tag" + i;
            for (int j = 0; j < (10 - i); j++) {
                manager.recordRawPoint(tag, j * 1000, j * 1.0);
            }
            manager.markPivot(tag);
        }

        SdtValidationReport report = manager.generateReport(10.0, 300, 3, 100);
        assertEquals(3, report.tags.size());
        // Top 3 by rawPointCount should be tag0 (10), tag1 (9), tag2 (8)
        assertEquals("tag0", report.tags.get(0).tagPath);
        assertEquals("tag1", report.tags.get(1).tagPath);
        assertEquals("tag2", report.tags.get(2).tagPath);
    }

    @Test
    void samplePointsLimitsPointDetails() {
        for (int i = 0; i < 50; i++) {
            manager.recordRawPoint("tag1", i * 1000, i * 1.0);
        }
        manager.markPivot("tag1");

        SdtValidationReport report = manager.generateReport(10.0, 300, 20, 5);
        assertTrue(report.tags.get(0).points.size() <= 5);
    }

    @Test
    void clearRemovesAllState() {
        manager.recordRawPoint("tag1", 1000, 10.0);
        manager.recordRawPoint("tag2", 2000, 20.0);
        assertEquals(2, manager.getTrackedTagCount());

        manager.clear();
        assertEquals(0, manager.getTrackedTagCount());

        SdtValidationReport report = manager.generateReport(1.0, 300, 20, 10);
        assertEquals(0, report.trackedTags);
        assertTrue(report.tags.isEmpty());
    }

    @Test
    void multipleTagsVerdict() {
        double deviation = 1.0;

        // Tag1: perfect linear ramp - should pass
        manager.recordRawPoint("tag1", 0, 0.0);
        manager.markPivot("tag1");
        manager.recordRawPoint("tag1", 500, 5.0);
        manager.recordRawPoint("tag1", 1000, 10.0);
        manager.markPivot("tag1");

        // Tag2: has a point way off - should fail
        manager.recordRawPoint("tag2", 0, 0.0);
        manager.markPivot("tag2");
        manager.recordRawPoint("tag2", 500, 50.0);  // way off from interpolated 5.0
        manager.recordRawPoint("tag2", 1000, 10.0);
        manager.markPivot("tag2");

        SdtValidationReport report = manager.generateReport(deviation, 300, 20, 100);
        assertEquals("FAIL", report.overallVerdict);

        // Find individual tag verdicts
        boolean tag1Pass = false, tag2Fail = false;
        for (SdtValidationReport.TagValidation tv : report.tags) {
            if ("tag1".equals(tv.tagPath)) tag1Pass = tv.withinDeviation;
            if ("tag2".equals(tv.tagPath)) tag2Fail = !tv.withinDeviation;
        }
        assertTrue(tag1Pass, "tag1 should pass");
        assertTrue(tag2Fail, "tag2 should fail");
    }

    @Test
    void markPivotOnUnknownTagIsSafe() {
        // Should not throw
        manager.markPivot("nonexistent");
    }

    @Test
    void pointDetailsIncludeInterpolatedValues() {
        manager.recordRawPoint("tag1", 0, 0.0);
        manager.markPivot("tag1");
        manager.recordRawPoint("tag1", 500, 5.0);
        manager.recordRawPoint("tag1", 1000, 10.0);
        manager.markPivot("tag1");

        SdtValidationReport report = manager.generateReport(1.0, 300, 20, 100);
        SdtValidationReport.TagValidation tv = report.tags.get(0);

        // First point is a pivot: interpolated should equal raw
        SdtValidationReport.PointDetail firstPoint = tv.points.get(0);
        assertTrue(firstPoint.isPivot);
        assertNotNull(firstPoint.interpolatedValue);
        assertEquals(0.0, firstPoint.absError, 0.001);

        // Middle point: not a pivot
        SdtValidationReport.PointDetail midPoint = tv.points.get(1);
        assertFalse(midPoint.isPivot);
        assertNotNull(midPoint.interpolatedValue);
        assertEquals(5.0, midPoint.interpolatedValue, 0.001);
        assertEquals(0.0, midPoint.absError, 0.001);
    }
}
