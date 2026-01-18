def handleTimerEvent():
    """
    Ignition Gateway Timer Script (Jython)
    Source: Weather + production forecast (next hour)

    Provider: [forecast]
    Base:     [forecast]Renewables/Site01/Forecast/H01/...

    Responsibilities:
    - Produce a next-hour forecast for wind/solar/net power.
    - Confidence decreases during grid events / high cloudiness.
    - Expected curtailment derived from current constraint state.

    Paste into: Designer -> Scripting -> Gateway Events -> Timer
    Recommended: Fixed Delay 5000ms (5s) is enough, Enabled=true
    """
    import math, random

    FORE = "[forecast]Renewables/Site01/Forecast/H01"
    TILT = "[renewables]Renewables/Site01"
    GRID = "[grid]Renewables/Site01"

    log = system.util.getLogger("renewables_site01.forecast")

    # Optional self-debug tags (create these in Tag Browser or re-import updated JSON).
    DIAG = "[forecast]Renewables/Site01/Diagnostics"

    def _try_write_diag(status, err_msg):
        try:
            ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
            system.tag.writeBlocking(
                [DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"],
                [ts, status, err_msg or ""]
            )
            try:
                cur = system.tag.readBlocking([DIAG + "/TickCount"])[0].value
                cur = int(cur or 0)
                system.tag.writeBlocking([DIAG + "/TickCount"], [cur + 1])
            except Exception:
                pass
        except Exception:
            pass

    def clamp(x, lo, hi):
        return lo if x < lo else hi if x > hi else x

    try:
        now = system.date.now()

        # Read current conditions / plant totals (as a baseline)
        paths = [
            TILT + "/MetMast01/WindSpeed_mps",
            TILT + "/MetMast01/Irradiance_Wm2",
            TILT + "/Windfarm01/Site/Power_Total_kW",
            TILT + "/SolarFarm01/Plant/Power_Total_kW",
            TILT + "/BESS01/Power/NetPower_kW",
            GRID + "/Dispatch/ConstraintActive",
            GRID + "/Dispatch/Curtailment_pct",
        ]
        v = system.tag.readBlocking(paths)
        wind = float(v[0].value or 0.0)
        irr = float(v[1].value or 0.0)
        wind_kw = float(v[2].value or 0.0)
        solar_kw = float(v[3].value or 0.0)
        bess_kw = float(v[4].value or 0.0)
        constraint = bool(v[5].value or False)
        curtail_pct = float(v[6].value or 0.0)

        # Next-hour met forecast: mean reversion + uncertainty
        wind_f = clamp(wind + random.gauss(0, 0.6) - 0.15, 0.0, 30.0)
        irr_f = clamp(irr + random.gauss(0, 80.0) - 20.0, 0.0, 1200.0)

        # Convert to next-hour power forecast: simple persistence + regression-to-mean
        wind_power_f = clamp(wind_kw * 0.85 + (wind_f / max(0.1, wind)) * wind_kw * 0.15 + random.gauss(0, 180.0), 0.0, 18000.0)
        solar_power_f = clamp(solar_kw * 0.80 + (irr_f / max(1.0, irr)) * solar_kw * 0.20 + random.gauss(0, 120.0), 0.0, 22000.0)

        # BESS power forecast: assume near 0 unless constraint/curtailment suggests charging
        bess_power_f = 0.0
        if constraint and curtail_pct > 5.0:
            bess_power_f = -clamp(1500.0 + curtail_pct * 80.0 + random.gauss(0, 150.0), 0.0, 8000.0)
        else:
            bess_power_f = clamp(bess_kw * 0.5 + random.gauss(0, 200.0), -5000.0, 5000.0)

        expected_curtail = clamp(curtail_pct + (10.0 if constraint else -2.0) + random.gauss(0, 2.0), 0.0, 80.0)

        # Confidence: lower during constraints and high variability
        variability = clamp(abs(random.gauss(0, 1.0)) * 10.0 + (15.0 if constraint else 0.0), 0.0, 40.0)
        conf = clamp(80.0 - variability - (abs(expected_curtail - curtail_pct) * 0.6), 35.0, 95.0)

        net_f = wind_power_f + solar_power_f + bess_power_f

        asof = system.date.format(now, "yyyy-MM-dd HH:mm:ss")
        writes = [
            (FORE + "/AsOfTime", asof),
            (FORE + "/WindPower_kW", wind_power_f),
            (FORE + "/SolarPower_kW", solar_power_f),
            (FORE + "/BESSPower_kW", bess_power_f),
            (FORE + "/NetPower_kW", net_f),
            (FORE + "/ExpectedCurtailment_pct", expected_curtail),
            (FORE + "/Confidence_pct", conf),
        ]
        system.tag.writeBlocking([p for (p, _) in writes], [x for (_, x) in writes])
        log.info("Forecast updated: net=%.1f kW, conf=%.0f%%, expCurt=%.1f%%" % (net_f, conf, expected_curtail))
        _try_write_diag("OK", "")

    except Exception as e:
        log.error("Forecast timer failed", e)
        _try_write_diag("ERROR", str(e))


# Ignition Gateway Timer Scripts execute top-level code each tick.
# Many projects do NOT automatically invoke handleTimerEvent(), so we call it explicitly.
handleTimerEvent()


