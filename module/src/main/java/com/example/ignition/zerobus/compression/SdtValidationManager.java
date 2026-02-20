package com.example.ignition.zerobus.compression;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Function;

/**
 * Manages per-tag validation buffers and generates SDT validation reports.
 *
 * Records raw data points and pivot markers from the SDT compression pipeline,
 * then reconstructs intermediate values via linear interpolation to validate
 * compression quality is within the configured deviation band.
 */
public class SdtValidationManager {
    private final ConcurrentHashMap<String, SdtValidationBuffer> buffers = new ConcurrentHashMap<>();
    private final int bufferCapacity;

    public SdtValidationManager() {
        this(200);
    }

    public SdtValidationManager(int bufferCapacity) {
        if (bufferCapacity <= 0) {
            throw new IllegalArgumentException("bufferCapacity must be > 0");
        }
        this.bufferCapacity = bufferCapacity;
    }

    public void recordRawPoint(String tagPath, long timestampMs, double value) {
        SdtValidationBuffer buf = buffers.computeIfAbsent(tagPath, k -> new SdtValidationBuffer(bufferCapacity));
        buf.addRawPoint(timestampMs, value);
    }

    public void markPivot(String tagPath) {
        SdtValidationBuffer buf = buffers.get(tagPath);
        if (buf != null) {
            buf.markLastAsPivot();
        }
    }

    public void markPivotByTimestamp(String tagPath, long timestampMs) {
        SdtValidationBuffer buf = buffers.get(tagPath);
        if (buf != null) {
            buf.markPointAsPivot(timestampMs);
        }
    }

    public SdtValidationReport generateReport(
            double deviation,
            long sdtMaxIntervalMs,
            long sdtMinIntervalMs,
            int maxTags,
            int samplePoints,
            Function<String, Double> deviationResolver
    ) {
        SdtValidationReport report = new SdtValidationReport();
        report.enabled = true;
        report.deviationConfigured = deviation;
        report.sdtMaxIntervalMs = sdtMaxIntervalMs;
        report.sdtMinIntervalMs = sdtMinIntervalMs;
        report.trackedTags = buffers.size();

        List<SdtValidationReport.TagValidation> tagValidations = new ArrayList<>();
        boolean allPass = true;

        for (var entry : buffers.entrySet()) {
            String tagPath = entry.getKey();
            SdtValidationBuffer buf = entry.getValue();

            List<SdtValidationBuffer.DataPoint> allPoints = buf.getPoints();
            List<SdtValidationBuffer.DataPoint> pivots = buf.getPivots();

            SdtValidationReport.TagValidation tv = new SdtValidationReport.TagValidation();
            tv.tagPath = tagPath;
            double deviationUsed = deviation;
            if (deviationResolver != null) {
                try {
                    Double resolved = deviationResolver.apply(tagPath);
                    if (resolved != null && resolved > 0.0) {
                        deviationUsed = resolved;
                    }
                } catch (Exception ignored) {
                    // Keep diagnostics robust even if resolver fails for a tag.
                }
            }
            tv.deviationUsed = deviationUsed;
            tv.rawPointCount = allPoints.size();
            tv.pivotCount = pivots.size();
            tv.compressionRatioPct = allPoints.isEmpty()
                    ? 0.0
                    : (1.0 - (double) pivots.size() / allPoints.size()) * 100.0;

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
                    maxErr = Math.max(maxErr, err);
                    sumErr += err;
                    errorCount++;
                    if (err > deviationUsed) {
                        tagWithinDeviation = false;
                    }
                }

                pointDetails.add(pd);
            }

            tv.maxAbsError = maxErr;
            tv.meanAbsError = (errorCount > 0) ? (sumErr / errorCount) : 0.0;
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

    public void clear() {
        buffers.clear();
    }

    public int getTrackedTagCount() {
        return buffers.size();
    }
}

