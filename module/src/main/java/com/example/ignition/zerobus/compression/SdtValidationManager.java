package com.example.ignition.zerobus.compression;

import com.example.ignition.zerobus.ConfigModel;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Manages per-tag validation buffers and generates SDT validation reports.
 *
 * Records raw data points and pivot markers from the SDT compression pipeline,
 * then reconstructs intermediate values via linear interpolation to prove
 * compression quality is within the configured deviation band.
 */
public class SdtValidationManager {

    private final ConcurrentHashMap<String, SdtValidationBuffer> buffers = new ConcurrentHashMap<>();
    private final int bufferCapacity;

    public SdtValidationManager() {
        this(100);
    }

    public SdtValidationManager(int bufferCapacity) {
        if (bufferCapacity <= 0) {
            throw new IllegalArgumentException("bufferCapacity must be > 0");
        }
        this.bufferCapacity = bufferCapacity;
    }

    /**
     * Record a raw data point before the SDT decision.
     */
    public void recordRawPoint(String tagPath, long timestampMs, double value) {
        SdtValidationBuffer buf = buffers.computeIfAbsent(tagPath, k -> new SdtValidationBuffer(bufferCapacity));
        buf.addRawPoint(timestampMs, value);
    }

    /**
     * Mark the last raw point for a tag as a pivot (called when SDT emits the current point).
     */
    public void markPivot(String tagPath) {
        SdtValidationBuffer buf = buffers.get(tagPath);
        if (buf != null) {
            buf.markLastAsPivot();
        }
    }

    /**
     * Mark a previously recorded point as a pivot by timestamp.
     * Used for EMIT_HELD where the emitted point is not the most recent.
     */
    public void markPivotByTimestamp(String tagPath, long timestampMs) {
        SdtValidationBuffer buf = buffers.get(tagPath);
        if (buf != null) {
            buf.markPointAsPivot(timestampMs);
        }
    }

    /**
     * Generate a validation report across all tracked tags.
     *
     * @param config       the current ConfigModel (used to resolve per-tag deviation via overrides)
     * @param maxTags      max number of tags to include (sorted by rawPointCount desc)
     * @param samplePoints max number of PointDetail entries per tag
     * @return the validation report
     */
    public SdtValidationReport generateReport(ConfigModel config, int maxTags, int samplePoints) {
        double globalDeviation = config.getSdtDeviation();
        int globalMaxInterval = config.getSdtMaxIntervalSeconds();

        SdtValidationReport report = new SdtValidationReport();
        report.enabled = true;
        report.deviationConfigured = globalDeviation;
        report.sdtMaxIntervalSeconds = globalMaxInterval;
        report.trackedTags = buffers.size();

        List<SdtValidationReport.TagValidation> tagValidations = new ArrayList<>();
        boolean allPass = true;

        for (var entry : buffers.entrySet()) {
            String tagPath = entry.getKey();
            SdtValidationBuffer buf = entry.getValue();

            // Resolve effective deviation for this tag
            SdtOverride override = config.findMatchingOverride(tagPath);
            double effectiveDeviation = override != null ? override.getDeviation() : globalDeviation;
            int effectiveMaxInterval = override != null ? override.getMaxIntervalSeconds() : globalMaxInterval;

            List<SdtValidationBuffer.DataPoint> allPoints = buf.getPoints();
            List<SdtValidationBuffer.DataPoint> pivots = buf.getPivots();

            SdtValidationReport.TagValidation tv = new SdtValidationReport.TagValidation();
            tv.tagPath = tagPath;
            tv.matchedOverridePattern = override != null ? override.getPattern() : null;
            tv.effectiveDeviation = effectiveDeviation;
            tv.effectiveMaxIntervalSeconds = effectiveMaxInterval;
            tv.rawPointCount = allPoints.size();
            tv.pivotCount = pivots.size();
            tv.compressionRatioPct = allPoints.isEmpty() ? 0.0
                    : (1.0 - (double) pivots.size() / allPoints.size()) * 100.0;

            // Compute interpolation errors
            double maxErr = 0.0;
            double sumErr = 0.0;
            int errorCount = 0;
            boolean tagWithinDeviation = true;

            List<SdtValidationReport.PointDetail> pointDetails = new ArrayList<>();

            for (SdtValidationBuffer.DataPoint pt : allPoints) {
                SdtValidationReport.PointDetail pd = new SdtValidationReport.PointDetail();
                pd.timestampMs = pt.timestampMs;
                pd.rawValue = pt.value;
                pd.isPivot = pt.isPivot;

                Double interpolated = LinearInterpolator.interpolate(pivots, pt.timestampMs);
                pd.interpolatedValue = interpolated;

                if (interpolated != null) {
                    double err = Math.abs(pt.value - interpolated);
                    pd.absError = err;
                    if (err > maxErr) {
                        maxErr = err;
                    }
                    sumErr += err;
                    errorCount++;
                    if (err > effectiveDeviation) {
                        tagWithinDeviation = false;
                    }
                }

                pointDetails.add(pd);
            }

            tv.maxAbsError = maxErr;
            tv.meanAbsError = errorCount > 0 ? sumErr / errorCount : 0.0;
            tv.withinDeviation = tagWithinDeviation;

            // Subsample points for the response
            if (pointDetails.size() > samplePoints && samplePoints > 0) {
                List<SdtValidationReport.PointDetail> sampled = new ArrayList<>(samplePoints);
                int step = Math.max(1, pointDetails.size() / samplePoints);
                for (int i = 0; i < pointDetails.size() && sampled.size() < samplePoints; i += step) {
                    sampled.add(pointDetails.get(i));
                }
                tv.points = sampled;
            } else {
                tv.points = pointDetails;
            }

            if (!tagWithinDeviation) {
                allPass = false;
            }

            tagValidations.add(tv);
        }

        // Sort by rawPointCount descending, take top N
        tagValidations.sort(Comparator.comparingInt((SdtValidationReport.TagValidation t) -> t.rawPointCount).reversed());
        if (tagValidations.size() > maxTags) {
            tagValidations = tagValidations.subList(0, maxTags);
        }

        report.tags = tagValidations;
        report.overallVerdict = allPass ? "PASS" : "FAIL";

        return report;
    }

    /**
     * Clear all tracked buffers.
     */
    public void clear() {
        buffers.clear();
    }

    /**
     * Return the number of tracked tags.
     */
    public int getTrackedTagCount() {
        return buffers.size();
    }
}
