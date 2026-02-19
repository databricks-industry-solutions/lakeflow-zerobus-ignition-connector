package com.example.ignition.zerobus.compression;

import com.example.ignition.zerobus.ConfigModel;
import org.junit.jupiter.api.Test;

import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

public class SdtOverrideTest {

    @Test
    void matchesFullTagPath() {
        SdtOverride ov = new SdtOverride(".*WindSpeed.*", 0.5, 10);
        assertTrue(ov.matches("[renewables]Site01/MetMast01/WindSpeed_mps"));
        assertFalse(ov.matches("[renewables]Site01/MetMast01/Temperature_C"));
    }

    @Test
    void matchesExactPattern() {
        SdtOverride ov = new SdtOverride("\\[default\\]Turbine/Power_kW", 2.0, 15);
        assertTrue(ov.matches("[default]Turbine/Power_kW"));
        assertFalse(ov.matches("[default]Turbine/Power_kW_extra"));
    }

    @Test
    void nullTagPathReturnsFalse() {
        SdtOverride ov = new SdtOverride(".*", 1.0, 60);
        assertFalse(ov.matches(null));
    }

    @Test
    void nullPatternReturnsFalse() {
        SdtOverride ov = new SdtOverride(null, 1.0, 60);
        assertFalse(ov.matches("anything"));
    }

    @Test
    void emptyPatternReturnsFalse() {
        SdtOverride ov = new SdtOverride("", 1.0, 60);
        assertFalse(ov.matches("anything"));
    }

    @Test
    void invalidRegexReturnsFalse() {
        SdtOverride ov = new SdtOverride("[unclosed", 1.0, 60);
        assertFalse(ov.matches("anything"));
    }

    @Test
    void compiledPatternIsCached() {
        SdtOverride ov = new SdtOverride(".*Test.*", 1.0, 60);
        assertNotNull(ov.getCompiledPattern());
        assertSame(ov.getCompiledPattern(), ov.getCompiledPattern());
    }

    @Test
    void setPatternInvalidatesCache() {
        SdtOverride ov = new SdtOverride(".*Test.*", 1.0, 60);
        ov.getCompiledPattern(); // force compilation
        ov.setPattern(".*Other.*");
        assertTrue(ov.matches("SomeOtherTag"));
        assertFalse(ov.matches("SomeTestTag"));
    }

    @Test
    void zeroDeviationAllowed() {
        SdtOverride ov = new SdtOverride(".*Status.*", 0.0, 600);
        assertEquals(0.0, ov.getDeviation());
        assertTrue(ov.matches("[default]PLC/Status_code"));
    }

    @Test
    void equalsAndHashCode() {
        SdtOverride a = new SdtOverride(".*Wind.*", 0.5, 10);
        SdtOverride b = new SdtOverride(".*Wind.*", 0.5, 10);
        SdtOverride c = new SdtOverride(".*Temp.*", 0.5, 10);

        assertEquals(a, b);
        assertEquals(a.hashCode(), b.hashCode());
        assertNotEquals(a, c);
    }

    // --- Integration with ConfigModel.findMatchingOverride ---

    @Test
    void firstMatchWins() {
        ConfigModel config = new ConfigModel();
        config.setSdtOverrides(Arrays.asList(
            new SdtOverride(".*WindSpeed.*", 0.5, 10),
            new SdtOverride(".*Wind.*", 1.0, 30)
        ));

        SdtOverride match = config.findMatchingOverride("[site]WindSpeed_mps");
        assertNotNull(match);
        assertEquals(0.5, match.getDeviation());
        assertEquals(10, match.getMaxIntervalSeconds());
    }

    @Test
    void fallbackToNullWhenNoMatch() {
        ConfigModel config = new ConfigModel();
        config.setSdtOverrides(List.of(
            new SdtOverride(".*WindSpeed.*", 0.5, 10)
        ));

        assertNull(config.findMatchingOverride("[site]Temperature_C"));
    }

    @Test
    void emptyOverridesListReturnsNull() {
        ConfigModel config = new ConfigModel();
        assertNull(config.findMatchingOverride("[site]AnyTag"));
    }

    @Test
    void nullTagPathReturnsNull() {
        ConfigModel config = new ConfigModel();
        config.setSdtOverrides(List.of(
            new SdtOverride(".*", 1.0, 60)
        ));
        assertNull(config.findMatchingOverride(null));
    }

    @Test
    void multipleOverridesSelectCorrectRule() {
        ConfigModel config = new ConfigModel();
        config.setSdtOverrides(Arrays.asList(
            new SdtOverride(".*WindSpeed.*", 0.5, 10),
            new SdtOverride(".*Power_kW.*", 2.0, 15),
            new SdtOverride(".*Temp.*", 0.2, 300),
            new SdtOverride(".*Status.*", 0.0, 600)
        ));

        SdtOverride wind = config.findMatchingOverride("[site]MetMast/WindSpeed_mps");
        assertNotNull(wind);
        assertEquals(0.5, wind.getDeviation());

        SdtOverride power = config.findMatchingOverride("[site]Turbine/Power_kW");
        assertNotNull(power);
        assertEquals(2.0, power.getDeviation());

        SdtOverride temp = config.findMatchingOverride("[site]BearingTemp_C");
        assertNotNull(temp);
        assertEquals(0.2, temp.getDeviation());

        SdtOverride status = config.findMatchingOverride("[site]PLC/Status_code");
        assertNotNull(status);
        assertEquals(0.0, status.getDeviation());
        assertEquals(600, status.getMaxIntervalSeconds());
    }
}
