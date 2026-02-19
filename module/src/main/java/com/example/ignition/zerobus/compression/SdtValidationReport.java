package com.example.ignition.zerobus.compression;

import java.util.List;

/**
 * Gson-serializable POJOs for the SDT validation diagnostic endpoint.
 *
 * Returned by {@code GET /system/zerobus/diagnostics/sdt} to prove that
 * SDT-compressed data can faithfully reconstruct the original signal
 * via linear interpolation within the configured deviation band.
 */
public class SdtValidationReport {

    public boolean enabled;
    public double deviationConfigured;
    public int sdtMaxIntervalSeconds;
    public int trackedTags;
    public String overallVerdict;  // "PASS" or "FAIL"
    public List<TagValidation> tags;

    public static class TagValidation {
        public String tagPath;
        public String matchedOverridePattern;  // null if using global defaults
        public double effectiveDeviation;       // actual deviation used for this tag
        public int effectiveMaxIntervalSeconds; // actual max interval used for this tag
        public int rawPointCount;
        public int pivotCount;
        public double compressionRatioPct;
        public double maxAbsError;
        public double meanAbsError;
        public boolean withinDeviation;
        public List<PointDetail> points;
    }

    public static class PointDetail {
        public long timestampMs;
        public double rawValue;
        public Double interpolatedValue;  // null if outside pivot range
        public Double absError;
        public boolean isPivot;
    }
}
