package com.example.ignition.zerobus;

import java.util.Date;

/**
 * TagEvent - Represents a tag value change event from Ignition.
 * 
 * This is a simple POJO that captures the essential information from
 * an Ignition tag update that will be sent to Databricks via Zerobus.
 */
public class TagEvent {
    
    private final String tagPath;
    private final Object value;
    private final String quality;
    private final Date timestamp;
    private final String assetId;
    private final String assetPath;
    
    /**
     * Constructor for basic tag event.
     * 
     * @param tagPath The full path of the tag in Ignition
     * @param value The tag value (can be numeric, string, boolean, etc.)
     * @param quality The quality code/name (e.g., "Good", "Bad", "Uncertain")
     * @param timestamp The timestamp when the value changed
     */
    public TagEvent(String tagPath, Object value, String quality, Date timestamp) {
        this(tagPath, value, quality, timestamp, null, null);
    }
    
    /**
     * Constructor with asset information.
     * 
     * @param tagPath The full path of the tag in Ignition
     * @param value The tag value
     * @param quality The quality code/name
     * @param timestamp The timestamp when the value changed
     * @param assetId Optional asset identifier
     * @param assetPath Optional asset hierarchy path
     */
    public TagEvent(String tagPath, Object value, String quality, Date timestamp, 
                    String assetId, String assetPath) {
        this.tagPath = tagPath;
        this.value = value;
        this.quality = quality;
        this.timestamp = timestamp;
        this.assetId = assetId;
        this.assetPath = assetPath;
    }
    
    // Getters
    
    public String getTagPath() {
        return tagPath;
    }
    
    public Object getValue() {
        return value;
    }
    
    public String getQuality() {
        return quality;
    }
    
    public Date getTimestamp() {
        return timestamp;
    }
    
    public String getAssetId() {
        return assetId;
    }
    
    public String getAssetPath() {
        return assetPath;
    }
    
    /**
     * Get the value as a string (for serialization).
     */
    public String getValueAsString() {
        return value != null ? value.toString() : null;
    }
    
    /**
     * Get the value as a double (if numeric).
     */
    public Double getValueAsDouble() {
        if (value instanceof Number) {
            return ((Number) value).doubleValue();
        }
        return null;
    }
    
    /**
     * Get the value as a boolean.
     */
    public Boolean getValueAsBoolean() {
        if (value instanceof Boolean) {
            return (Boolean) value;
        }
        return null;
    }
    
    /**
     * Get the value as a long integer.
     */
    public Long getValueAsLong() {
        if (value instanceof Number) {
            return ((Number) value).longValue();
        }
        return null;
    }
    
    /**
     * Check if this is a numeric value.
     */
    public boolean isNumeric() {
        return value instanceof Number;
    }
    
    /**
     * Check if this is a string value.
     */
    public boolean isString() {
        return value instanceof String;
    }
    
    /**
     * Check if this is a boolean value.
     */
    public boolean isBoolean() {
        return value instanceof Boolean;
    }
    
    /**
     * Check if the quality indicates a good reading.
     */
    public boolean isGoodQuality() {
        return quality != null && quality.toLowerCase().contains("good");
    }
    
    @Override
    public String toString() {
        return "TagEvent{" +
                "tagPath='" + tagPath + '\'' +
                ", value=" + value +
                ", quality='" + quality + '\'' +
                ", timestamp=" + timestamp +
                ", assetId='" + assetId + '\'' +
                '}';
    }
}

