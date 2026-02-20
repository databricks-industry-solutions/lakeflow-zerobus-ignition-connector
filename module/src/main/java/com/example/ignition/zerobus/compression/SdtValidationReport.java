package com.example.ignition.zerobus.compression;

import java.util.List;

/**
 * Gson-serializable POJOs for SDT validation diagnostics.
 *
 * The intent is to prove that SDT-compressed pivot points can reconstruct the original signal
 * via linear interpolation within the configured deviation band.
 */
public class SdtValidationReport {
    public boolean enabled;
    public double deviationConfigured;
    public long sdtMaxIntervalMs;
    public long sdtMinIntervalMs;
    public int trackedTags;
    public String overallVerdict; // "PASS" or "FAIL"
    public List<TagValidation> tags;

    public static class TagValidation {
        public String tagPath;
        public double deviationUsed;
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
        public Double interpolatedValue; // null if outside pivot range
        public Double absError;
        public boolean isPivot;
    }
}

