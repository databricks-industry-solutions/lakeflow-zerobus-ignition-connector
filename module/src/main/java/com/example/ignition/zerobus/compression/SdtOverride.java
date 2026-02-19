package com.example.ignition.zerobus.compression;

import java.util.Objects;
import java.util.regex.Pattern;
import java.util.regex.PatternSyntaxException;

/**
 * Pattern-based SDT override rule.
 *
 * Allows different tag classes to use different SDT compression parameters.
 * The {@code pattern} is a Java regex matched against the full tag path.
 * Rules are evaluated in list order; first match wins.
 *
 * <p>A {@code deviation} of 0 means "archive every change" (no compression),
 * useful for status/boolean-like numeric tags.</p>
 *
 * <p>Gson serializes/deserializes this automatically as part of the
 * {@code ConfigModel.sdtOverrides} list.</p>
 */
public class SdtOverride {

    private String pattern;
    private double deviation;
    private int maxIntervalSeconds;

    /** Compiled regex - transient so Gson ignores it. */
    private transient volatile Pattern compiledPattern;

    public SdtOverride() {
        // Default constructor for Gson
    }

    public SdtOverride(String pattern, double deviation, int maxIntervalSeconds) {
        this.pattern = pattern;
        this.deviation = deviation;
        this.maxIntervalSeconds = maxIntervalSeconds;
    }

    public String getPattern() {
        return pattern;
    }

    public void setPattern(String pattern) {
        this.pattern = pattern;
        this.compiledPattern = null; // invalidate cache
    }

    public double getDeviation() {
        return deviation;
    }

    public void setDeviation(double deviation) {
        this.deviation = deviation;
    }

    public int getMaxIntervalSeconds() {
        return maxIntervalSeconds;
    }

    public void setMaxIntervalSeconds(int maxIntervalSeconds) {
        this.maxIntervalSeconds = maxIntervalSeconds;
    }

    /**
     * Test whether the given tag path matches this override's pattern.
     *
     * @param tagPath full tag path string
     * @return true if the pattern matches (full match, not partial)
     */
    public boolean matches(String tagPath) {
        if (tagPath == null || pattern == null || pattern.isEmpty()) {
            return false;
        }
        Pattern p = getCompiledPattern();
        return p != null && p.matcher(tagPath).matches();
    }

    /**
     * Compile the pattern lazily and cache it.
     *
     * @return compiled Pattern, or null if the regex is invalid
     */
    Pattern getCompiledPattern() {
        Pattern p = compiledPattern;
        if (p == null && pattern != null && !pattern.isEmpty()) {
            try {
                p = Pattern.compile(pattern);
                compiledPattern = p;
            } catch (PatternSyntaxException e) {
                // Invalid regex - will be caught during validation
                return null;
            }
        }
        return p;
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;
        SdtOverride that = (SdtOverride) o;
        return Double.compare(deviation, that.deviation) == 0
                && maxIntervalSeconds == that.maxIntervalSeconds
                && Objects.equals(pattern, that.pattern);
    }

    @Override
    public int hashCode() {
        return Objects.hash(pattern, deviation, maxIntervalSeconds);
    }

    @Override
    public String toString() {
        return "SdtOverride{pattern='" + pattern + "', deviation=" + deviation
                + ", maxIntervalSeconds=" + maxIntervalSeconds + "}";
    }
}
