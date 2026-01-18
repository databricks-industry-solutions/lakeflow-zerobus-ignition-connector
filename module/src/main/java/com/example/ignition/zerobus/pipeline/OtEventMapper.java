package com.example.ignition.zerobus.pipeline;

import com.example.ignition.zerobus.ConfigModel;
import com.example.ignition.zerobus.TagEvent;
import com.example.ignition.zerobus.proto.OTEvent;

import java.util.UUID;

/**
 * Pure mapping: TagEvent -> OTEvent.
 *
 * Keeping this out of the Zerobus sink makes the architecture extensible:
 * new adapters (MQTT/Sparkplug, Modbus, OPC-UA) can all map into the same OTEvent contract.
 */
public final class OtEventMapper {
    private final ConfigModel config;

    public OtEventMapper(ConfigModel config) {
        this.config = config;
    }

    public OTEvent map(TagEvent event) {
        String eventId = UUID.randomUUID().toString();

        long ingestionTimeMicros = System.currentTimeMillis() * 1000L;
        long eventTimeMicros = (event.getTimestamp() != null ? event.getTimestamp().getTime() : System.currentTimeMillis()) * 1000L;

        String tagPath = event.getTagPath();
        String tagProvider = "default";
        if (tagPath != null && tagPath.startsWith("[") && tagPath.contains("]")) {
            int endBracket = tagPath.indexOf("]");
            if (endBracket > 1) {
                tagProvider = tagPath.substring(1, endBracket);
            }
        }

        String dataType = "UNKNOWN";
        if (event.isNumeric()) {
            dataType = "DOUBLE";
        } else if (event.isString()) {
            dataType = "STRING";
        } else if (event.isBoolean()) {
            dataType = "BOOLEAN";
        }

        String quality = (config.isIncludeQuality() && event.getQuality() != null) ? event.getQuality() : "";
        int qualityCode = (config.isIncludeQuality() && event.isGoodQuality()) ? 192 : 0;

        OTEvent.Builder builder = OTEvent.newBuilder()
            .setEventId(eventId)
            .setEventTime(eventTimeMicros)
            .setTagPath(tagPath != null ? tagPath : "")
            .setTagProvider(tagProvider)
            .setQuality(quality)
            .setQualityCode(qualityCode)
            .setSourceSystem(config.getSourceSystemId())
            .setIngestionTimestamp(ingestionTimeMicros)
            .setDataType(dataType)
            .setAlarmState("")
            .setAlarmPriority(0);

        if (event.isNumeric()) {
            builder.setNumericValue(event.getValueAsDouble());
        } else {
            builder.setNumericValue(0.0);
        }

        if (event.isString()) {
            builder.setStringValue(event.getValueAsString());
        } else {
            builder.setStringValue("");
        }

        if (event.isBoolean()) {
            builder.setBooleanValue(event.getValueAsBoolean());
        } else {
            builder.setBooleanValue(false);
        }

        return builder.build();
    }
}


