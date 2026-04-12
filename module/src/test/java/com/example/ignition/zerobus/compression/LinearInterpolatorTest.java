package com.example.ignition.zerobus.compression;

import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

public class LinearInterpolatorTest {

    private static SdtValidationBuffer.DataPoint pivot(long ts, double val) {
        return new SdtValidationBuffer.DataPoint(ts, val, true);
    }

    @Test
    void nullOrEmptyPivotsReturnsNull() {
        assertNull(LinearInterpolator.interpolate(null, 1000));
        assertNull(LinearInterpolator.interpolate(Collections.emptyList(), 1000));
    }

    @Test
    void beforeFirstPivotReturnsNull() {
        List<SdtValidationBuffer.DataPoint> pivots = Arrays.asList(
                pivot(1000, 10.0),
                pivot(2000, 20.0)
        );
        assertNull(LinearInterpolator.interpolate(pivots, 500));
    }

    @Test
    void exactMatchOnFirstPivot() {
        List<SdtValidationBuffer.DataPoint> pivots = Arrays.asList(
                pivot(1000, 10.0),
                pivot(2000, 20.0)
        );
        assertEquals(10.0, LinearInterpolator.interpolate(pivots, 1000), 0.001);
    }

    @Test
    void exactMatchOnLastPivot() {
        List<SdtValidationBuffer.DataPoint> pivots = Arrays.asList(
                pivot(1000, 10.0),
                pivot(2000, 20.0)
        );
        assertEquals(20.0, LinearInterpolator.interpolate(pivots, 2000), 0.001);
    }

    @Test
    void betweenTwoPivotsLinearInterpolation() {
        List<SdtValidationBuffer.DataPoint> pivots = Arrays.asList(
                pivot(1000, 10.0),
                pivot(2000, 20.0)
        );
        // Midpoint: 15.0
        assertEquals(15.0, LinearInterpolator.interpolate(pivots, 1500), 0.001);
        // Quarter: 12.5
        assertEquals(12.5, LinearInterpolator.interpolate(pivots, 1250), 0.001);
    }

    @Test
    void afterLastPivotHoldsLastValue() {
        List<SdtValidationBuffer.DataPoint> pivots = Arrays.asList(
                pivot(1000, 10.0),
                pivot(2000, 20.0)
        );
        assertEquals(20.0, LinearInterpolator.interpolate(pivots, 3000), 0.001);
        assertEquals(20.0, LinearInterpolator.interpolate(pivots, 5000), 0.001);
    }

    @Test
    void singlePivotExactMatch() {
        List<SdtValidationBuffer.DataPoint> pivots = Collections.singletonList(
                pivot(1000, 42.0)
        );
        assertEquals(42.0, LinearInterpolator.interpolate(pivots, 1000), 0.001);
    }

    @Test
    void singlePivotAfterHoldsValue() {
        List<SdtValidationBuffer.DataPoint> pivots = Collections.singletonList(
                pivot(1000, 42.0)
        );
        assertEquals(42.0, LinearInterpolator.interpolate(pivots, 2000), 0.001);
    }

    @Test
    void singlePivotBeforeReturnsNull() {
        List<SdtValidationBuffer.DataPoint> pivots = Collections.singletonList(
                pivot(1000, 42.0)
        );
        assertNull(LinearInterpolator.interpolate(pivots, 500));
    }

    @Test
    void multiplePivotsInterpolation() {
        List<SdtValidationBuffer.DataPoint> pivots = Arrays.asList(
                pivot(0, 0.0),
                pivot(100, 10.0),
                pivot(200, 30.0)
        );
        // Between first and second: linear 0->10
        assertEquals(5.0, LinearInterpolator.interpolate(pivots, 50), 0.001);
        // Between second and third: linear 10->30
        assertEquals(20.0, LinearInterpolator.interpolate(pivots, 150), 0.001);
        // After last: hold 30
        assertEquals(30.0, LinearInterpolator.interpolate(pivots, 300), 0.001);
    }

    @Test
    void exactMatchOnMiddlePivot() {
        List<SdtValidationBuffer.DataPoint> pivots = Arrays.asList(
                pivot(0, 0.0),
                pivot(100, 10.0),
                pivot(200, 30.0)
        );
        assertEquals(10.0, LinearInterpolator.interpolate(pivots, 100), 0.001);
    }
}
