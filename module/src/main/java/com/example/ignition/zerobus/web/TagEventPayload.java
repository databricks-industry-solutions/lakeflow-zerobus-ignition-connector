package com.example.ignition.zerobus.web;

import com.google.gson.annotations.SerializedName;

/**
 * Payload class for tag events received from Ignition Event Streams.
 * 
 * This matches the structure of events sent from Event Stream Script handlers.
 */
public class TagEventPayload {
    
    @SerializedName("tagPath")
    private String tagPath;
    
    @SerializedName("tagProvider")
    private String tagProvider;
    
    @SerializedName("value")
    private Object value;
    
    @SerializedName("quality")
    private String quality;
    
    @SerializedName("qualityCode")
    private Integer qualityCode;
    
    @SerializedName("timestamp")
    private Long timestamp;
    
    @SerializedName("dataType")
    private String dataType;
    
    // Default constructor for Gson
    public TagEventPayload() {
    }
    
    // Getters and setters
    public String getTagPath() {
        return tagPath;
    }
    
    public void setTagPath(String tagPath) {
        this.tagPath = tagPath;
    }
    
    public String getTagProvider() {
        return tagProvider;
    }
    
    public void setTagProvider(String tagProvider) {
        this.tagProvider = tagProvider;
    }
    
    public Object getValue() {
        return value;
    }
    
    public void setValue(Object value) {
        this.value = value;
    }
    
    public String getQuality() {
        return quality;
    }
    
    public void setQuality(String quality) {
        this.quality = quality;
    }
    
    public Integer getQualityCode() {
        return qualityCode;
    }
    
    public void setQualityCode(Integer qualityCode) {
        this.qualityCode = qualityCode;
    }
    
    public Long getTimestamp() {
        return timestamp;
    }
    
    public void setTimestamp(Long timestamp) {
        this.timestamp = timestamp;
    }
    
    public String getDataType() {
        return dataType;
    }
    
    public void setDataType(String dataType) {
        this.dataType = dataType;
    }
    
    @Override
    public String toString() {
        return "TagEventPayload{" +
                "tagPath='" + tagPath + '\'' +
                ", tagProvider='" + tagProvider + '\'' +
                ", value=" + value +
                ", quality='" + quality + '\'' +
                ", timestamp=" + timestamp +
                '}';
    }
}

