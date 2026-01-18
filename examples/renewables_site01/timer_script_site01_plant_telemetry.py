def handleTimerEvent():
    """
    Ignition Gateway Timer Script (Jython)
    Source: Plant telemetry (SCADA-like): Wind + Solar + BESS + Met

    Provider: [renewables]
    Base:     [renewables]Renewables/Site01/...

    Business story wiring:
    - Reads [grid] curtailment/target/price to influence plant output and BESS behavior.
    - Reads [cmms] ForcedOutage flags to force assets offline (maintenance impacts production).

    Paste into: Designer -> Scripting -> Gateway Events -> Timer
    Recommended: Fixed Delay 1000ms (or 2000ms), Enabled=true
    """
    import math, random

    # --- Providers / paths ---
    TILT = "[renewables]Renewables/Site01"
    GRID = "[grid]Renewables/Site01"
    CMMS = "[cmms]Renewables/Site01"

    CFG = TILT + "/Config"
    MET = TILT + "/MetMast01"
    WIND = TILT + "/Windfarm01"
    SOLAR = TILT + "/SolarFarm01"
    BESS = TILT + "/BESS01"

    TURBINES = [WIND + "/Turbines/T01", WIND + "/Turbines/T02", WIND + "/Turbines/T03"]
    INVERTERS = [SOLAR + "/Inverters/I01", SOLAR + "/Inverters/I02"]

    log = system.util.getLogger("renewables_site01.plant")

    # Optional self-debug tags (create these in Tag Browser or re-import updated JSON).
    DIAG = TILT + "/Diagnostics"

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

    def wrap_deg(d):
        d = d % 360.0
        return d + 360.0 if d < 0 else d

    def ang_diff_deg(a, b):
        return (a - b + 180.0) % 360.0 - 180.0

    def power_curve_kw(v_mps, rated_kw, cut_in, rated, cut_out):
        if v_mps < cut_in or v_mps >= cut_out:
            return 0.0
        if v_mps >= rated:
            return rated_kw
        x = (v_mps - cut_in) / max(0.1, (rated - cut_in))
        return rated_kw * (x ** 3)

    try:
        g = system.util.getGlobals()
        now = system.date.now()

        state = g.get("renewables_site01_state")
        if state is None:
            state = {
                "lastTs": now,
                "accumMs": 0,
                "wind": 8.0,
                "windDir": 180.0,
                "irr": 500.0,
                "soc": 55.0,          # %
                "throughputMWh": 0.0,
                "cycles": 0.0,
                "cfg": None,
                "cfgLastReadTs": now,
                "lastSocForCycles": 55.0
            }
            g["renewables_site01_state"] = state

        # --- config read (cached) ---
        cfg = state.get("cfg")
        cfg_last = state.get("cfgLastReadTs", now)
        if cfg is None or system.date.millisBetween(cfg_last, now) >= 5000:
            paths = [
                CFG + "/SimEnabled",
                CFG + "/UpdateEveryMs",
                CFG + "/MeanWind_mps",
                CFG + "/MeanReversion_k",
                CFG + "/TurbulenceSigma",
                CFG + "/WindDirNoiseSigma_deg",
                CFG + "/MeanIrradiance_Wm2",
                CFG + "/Cloudiness_sigma",
                CFG + "/CutIn_mps",
                CFG + "/RatedWind_mps",
                CFG + "/CutOut_mps",
                CFG + "/RatedPower_T01_kW",
                CFG + "/RatedPower_T02_kW",
                CFG + "/RatedPower_T03_kW",
                CFG + "/SolarACCapacity_kW",
                CFG + "/BESS_EnergyCapacity_kWh",
                CFG + "/BESS_MaxCharge_kW",
                CFG + "/BESS_MaxDischarge_kW",
                CFG + "/InverterCount"
            ]
            vals = system.tag.readBlocking(paths)

            def _v(i, default):
                try:
                    x = vals[i].value
                    return default if x is None else x
                except Exception:
                    return default

            cfg = {
                "simEnabled": bool(_v(0, True)),
                "updateEveryMs": int(_v(1, 1000)),
                "muWind": float(_v(2, 9.0)),
                "kWind": float(_v(3, 0.06)),
                "sigmaWind": float(_v(4, 0.7)),
                "windDirSigma": float(_v(5, 4.0)),
                "muIrr": float(_v(6, 650.0)),
                "sigmaIrr": float(_v(7, 120.0)),
                "cutIn": float(_v(8, 3.0)),
                "ratedWind": float(_v(9, 12.0)),
                "cutOut": float(_v(10, 25.0)),
                "ratedKw": [float(_v(11, 3500.0)), float(_v(12, 3600.0)), float(_v(13, 3400.0))],
                "solarCapKw": float(_v(14, 18000.0)),
                "bessKWh": float(_v(15, 40000.0)),
                "bessMaxChKw": float(_v(16, 10000.0)),
                "bessMaxDisKw": float(_v(17, 10000.0)),
                "invCount": int(_v(18, 2))
            }
            state["cfg"] = cfg
            state["cfgLastReadTs"] = now

        if not cfg.get("simEnabled", True):
            return

        dt_ms = system.date.millisBetween(state["lastTs"], now)
        dt_s = max(0.2, min(5.0, dt_ms / 1000.0))
        state["lastTs"] = now

        state["accumMs"] = int(state.get("accumMs", 0)) + int(max(0, dt_ms))
        update_every = max(200, int(cfg.get("updateEveryMs", 1000)))
        if state["accumMs"] < update_every:
            return
        state["accumMs"] = 0

        # --- external drivers from other sources ---
        # IMPORTANT: This script should still run even if [grid] and/or [cmms] providers are not set up yet.
        # If reads fail (missing provider/tags), fall back to safe defaults and keep producing telemetry.

        # Defaults (no curtailment, modest price, no FCAS)
        curtail_pct = 0.0
        target_export_kw = 0.0
        rrp = 80.0
        fcas_enabled = False

        try:
            grid_paths = [
                GRID + "/Dispatch/Curtailment_pct",
                GRID + "/Dispatch/TargetExport_kW",
                GRID + "/Market/RRP_AUD_per_MWh",
                GRID + "/Dispatch/FCAS_Enabled"
            ]
            grid_vals = system.tag.readBlocking(grid_paths)
            curtail_pct = float(grid_vals[0].value or 0.0)
            target_export_kw = float(grid_vals[1].value or 0.0)
            rrp = float(grid_vals[2].value or 80.0)
            fcas_enabled = bool(grid_vals[3].value or False)
        except Exception:
            # Keep defaults; don't spam logs every tick.
            pass

        curtail_frac = clamp(curtail_pct / 100.0, 0.0, 1.0)

        # Maintenance forced outages (simulate operator-driven downtime)
        forced_t = [False, False, False]
        forced_i = [False, False]
        forced_bess = False
        try:
            cmms_paths = [
                CMMS + "/Assets/Windfarm01/T01/ForcedOutage",
                CMMS + "/Assets/Windfarm01/T02/ForcedOutage",
                CMMS + "/Assets/Windfarm01/T03/ForcedOutage",
                CMMS + "/Assets/SolarFarm01/I01/ForcedOutage",
                CMMS + "/Assets/SolarFarm01/I02/ForcedOutage",
                CMMS + "/Assets/BESS01/ForcedOutage",
            ]
            cmms_vals = system.tag.readBlocking(cmms_paths)
            forced_t = [bool(cmms_vals[i].value or False) for i in range(3)]
            forced_i = [bool(cmms_vals[3].value or False), bool(cmms_vals[4].value or False)]
            forced_bess = bool(cmms_vals[5].value or False)
        except Exception:
            # Keep defaults
            pass

        # --- met mast: wind + irradiance ---
        hour = system.date.getHour24(now)
        day_shape = max(0.0, math.sin((hour / 24.0) * 2.0 * math.pi))  # 0..1..0

        # Wind: mean-reverting + turbulence
        state["wind"] = clamp(
            state["wind"] + (cfg["muWind"] - state["wind"]) * cfg["kWind"] * dt_s + random.gauss(0, cfg["sigmaWind"]) * math.sqrt(dt_s),
            0.0, 30.0
        )
        state["windDir"] = wrap_deg(state["windDir"] + random.gauss(0, cfg["windDirSigma"]) * math.sqrt(dt_s))

        # Solar irradiance: diurnal + cloudiness noise + clamp
        irr_target = cfg["muIrr"] * (0.15 + 0.85 * max(0.0, math.sin(((hour - 6) / 12.0) * math.pi)))  # crude sunrise->sunset
        state["irr"] = clamp(
            0.92 * state["irr"] + 0.08 * irr_target + random.gauss(0, cfg["sigmaIrr"]) * 0.10,
            0.0, 1200.0
        )
        amb_temp = 16.0 + 8.0 * max(0.0, math.sin(((hour - 6) / 12.0) * math.pi)) + random.gauss(0, 0.4)

        site_wind = state["wind"]
        site_dir = state["windDir"]
        irr = state["irr"]

        writes = []

        # Met writes
        writes.extend([
            (MET + "/WindSpeed_mps", site_wind),
            (MET + "/WindDir_deg", site_dir),
            (MET + "/Irradiance_Wm2", irr),
            (MET + "/AmbientTemp_C", amb_temp),
            (MET + "/Humidity_pct", clamp(45.0 + random.gauss(0, 2.0), 15.0, 90.0)),
            (MET + "/Pressure_hPa", clamp(1010.0 + random.gauss(0, 1.5), 980.0, 1035.0)),
        ])

        # --- wind turbines ---
        wind_total = 0.0
        avail_count = 0
        for idx, tpath in enumerate(TURBINES):
            rated_kw = cfg["ratedKw"][idx]
            v_local = clamp(site_wind + random.gauss(0, 0.35) + (-0.3 if idx == 2 else 0.0), 0.0, 30.0)

            # yaw (lag)
            try:
                yaw_pos = float(system.tag.readBlocking([tpath + "/YawPitch/YawPosition_deg"])[0].value)
            except Exception:
                yaw_pos = site_dir
            yaw_pos = wrap_deg(yaw_pos + ang_diff_deg(site_dir, yaw_pos) * 0.35 + random.gauss(0, 0.6))
            yaw_err = ang_diff_deg(site_dir, yaw_pos)

            # base power
            p_kw_raw = power_curve_kw(v_local, rated_kw, cfg["cutIn"], cfg["ratedWind"], cfg["cutOut"])

            # yaw derate
            yaw_derate = max(0.0, math.cos(math.radians(yaw_err))) ** 1.7
            p_kw = p_kw_raw * yaw_derate

            # forced outage
            availability = not forced_t[idx]
            if not availability:
                p_kw = 0.0

            # curtailment
            p_kw *= (1.0 - curtail_frac)

            # simple electrical
            pf = clamp(0.97 + random.gauss(0, 0.01), 0.90, 1.0)
            v_ll = 690.0
            current_a = 0.0 if p_kw <= 0 else (p_kw * 1000.0) / (math.sqrt(3.0) * v_ll * max(0.1, pf))
            try:
                kvar = p_kw * math.tan(math.acos(pf))
            except Exception:
                kvar = 0.0

            # energy integrate
            try:
                e_today = float(system.tag.readBlocking([tpath + "/Electrical/EnergyToday_kWh"])[0].value or 0.0)
                e_total = float(system.tag.readBlocking([tpath + "/Electrical/EnergyTotal_MWh"])[0].value or 0.0)
            except Exception:
                e_today, e_total = 0.0, 0.0
            e_today += p_kw * (dt_s / 3600.0)
            e_total += (p_kw * (dt_s / 3600.0)) / 1000.0

            writes.extend([
                (tpath + "/Electrical/Power_kW", p_kw),
                (tpath + "/Electrical/ReactivePower_kVAr", kvar),
                (tpath + "/Electrical/PowerFactor", pf),
                (tpath + "/Electrical/Voltage_V", v_ll),
                (tpath + "/Electrical/Current_A", current_a),
                (tpath + "/Electrical/EnergyToday_kWh", e_today),
                (tpath + "/Electrical/EnergyTotal_MWh", e_total),
                (tpath + "/WindRotor/WindSpeed_mps", v_local),
                (tpath + "/WindRotor/RotorSpeed_RPM", clamp((v_local / max(0.1, cfg["ratedWind"])) * 16.0, 0.0, 16.0)),
                (tpath + "/WindRotor/GenSpeed_RPM", clamp((v_local / max(0.1, cfg["ratedWind"])) * 16.0 * 80.0, 0.0, 16.0 * 80.0)),
                (tpath + "/WindRotor/NacelleTemp_C", 24.0 + 0.01 * p_kw + random.gauss(0, 0.2)),
                (tpath + "/YawPitch/YawPosition_deg", yaw_pos),
                (tpath + "/YawPitch/YawError_deg", yaw_err),
                (tpath + "/YawPitch/PitchBlade1_deg", clamp(2.0 + (0.0 if p_kw < 0.95 * rated_kw else 8.0) + random.gauss(0, 0.1), 0.0, 22.0)),
                (tpath + "/YawPitch/PitchBlade2_deg", clamp(2.0 + (0.0 if p_kw < 0.95 * rated_kw else 8.0) + random.gauss(0, 0.1), 0.0, 22.0)),
                (tpath + "/YawPitch/PitchBlade3_deg", clamp(2.0 + (0.0 if p_kw < 0.95 * rated_kw else 8.0) + random.gauss(0, 0.1), 0.0, 22.0)),
                (tpath + "/Status/OperatingState", 2 if (availability and p_kw > 0.0) else 3 if (not availability) else 0),
                (tpath + "/Status/Availability", availability),
                (tpath + "/Status/AlarmActive", (not availability)),
                (tpath + "/Status/FaultCode", 0 if availability else random.choice([101, 203, 315])),
                (tpath + "/Status/LastFault", "" if availability else "MAINT_OUTAGE"),
            ])

            wind_total += p_kw
            avail_count += 1 if availability else 0

        wind_avail_pct = 100.0 * (float(avail_count) / float(len(TURBINES)))
        writes.extend([
            (WIND + "/Site/Power_Total_kW", wind_total),
            (WIND + "/Site/Availability_pct", wind_avail_pct),
            (WIND + "/Site/Curtailment_pct", curtail_pct),
        ])

        # --- solar farm ---
        # Approx: AC power proportional to irradiance, clipped by nameplate; reduced by curtailment and outages.
        solar_cap = cfg["solarCapKw"]
        inv_count = max(1, int(cfg.get("invCount", 2)))
        inv_share = solar_cap / float(inv_count)

        # Temperature derate (very rough)
        temp_derate = clamp(1.0 - max(0.0, (amb_temp - 25.0)) * 0.004, 0.80, 1.05)
        solar_potential = solar_cap * clamp(irr / 1000.0, 0.0, 1.15) * temp_derate

        # Curtailment applies at plant level
        solar_potential *= (1.0 - curtail_frac)

        solar_total = 0.0
        for i, inv in enumerate(INVERTERS):
            if i >= inv_count:
                continue
            inv_forced = forced_i[i] if i < len(forced_i) else False
            inv_avail = not inv_forced
            inv_p = min(inv_share, max(0.0, solar_potential / float(inv_count)))
            if not inv_avail:
                inv_p = 0.0
            # add small noise
            inv_p = max(0.0, inv_p + random.gauss(0, 30.0))

            # DC approx
            dc_v = 900.0 + random.gauss(0, 5.0)
            dc_p = inv_p * 1.03
            dc_i = 0.0 if dc_v <= 1.0 else (dc_p * 1000.0) / dc_v

            # AC approx
            ac_v = 690.0 + random.gauss(0, 2.0)
            pf = clamp(0.99 + random.gauss(0, 0.005), 0.92, 1.0)
            ac_i = 0.0 if inv_p <= 0 else (inv_p * 1000.0) / (math.sqrt(3.0) * ac_v * max(0.1, pf))

            writes.extend([
                (inv + "/Status", "RUN" if inv_avail else "STOP"),
                (inv + "/Availability", inv_avail),
                (inv + "/DC/Voltage_V", dc_v),
                (inv + "/DC/Current_A", dc_i),
                (inv + "/DC/Power_kW", dc_p),
                (inv + "/AC/Voltage_V", ac_v),
                (inv + "/AC/Current_A", ac_i),
                (inv + "/AC/Frequency_Hz", 50.0 + random.gauss(0, 0.02)),
                (inv + "/AC/Power_kW", inv_p),
            ])

            solar_total += inv_p

        solar_avail_pct = 100.0 * (float(inv_count) - float(sum([1 for x in forced_i[:inv_count] if x]))) / float(inv_count)
        writes.extend([
            (SOLAR + "/Plant/Power_Total_kW", solar_total),
            (SOLAR + "/Plant/Availability_pct", clamp(solar_avail_pct, 0.0, 100.0)),
        ])

        # --- BESS ---
        # Goal: demonstrate shifting + dispatch support.
        # - If price high or FCAS enabled: discharge (support export)
        # - If curtailment high or price low: charge (absorb excess)
        bess_kwh = max(1.0, cfg["bessKWh"])
        max_ch = max(0.0, cfg["bessMaxChKw"])
        max_dis = max(0.0, cfg["bessMaxDisKw"])
        soc = clamp(float(state.get("soc", 55.0)), 5.0, 95.0)

        bess_avail = (not forced_bess)
        mode = "AUTO"

        # simple policy
        desired_kw = 0.0
        if not bess_avail:
            desired_kw = 0.0
            mode = "OUTAGE"
        else:
            if (rrp >= 150.0) or fcas_enabled:
                # discharge when valuable / needed
                desired_kw = +min(max_dis, 3500.0 + (rrp - 150.0) * 15.0)
            elif curtail_frac >= 0.05 or rrp <= 60.0:
                desired_kw = -min(max_ch, 3000.0 + curtail_frac * 8000.0)
            else:
                desired_kw = 0.0

            # SOC constraints
            if soc <= 8.0 and desired_kw > 0:
                desired_kw = 0.0
            if soc >= 92.0 and desired_kw < 0:
                desired_kw = 0.0

        # apply
        net_kw = desired_kw
        ch_kw = max(0.0, -net_kw)
        dis_kw = max(0.0, net_kw)

        # update SOC (kW -> kWh)
        delta_kwh = (dis_kw - ch_kw) * (dt_s / 3600.0)  # dis reduces energy, ch increases energy => sign inverted
        # Our sign convention: net_kw>0 discharge => SOC decreases
        soc = clamp(soc - (delta_kwh / bess_kwh) * 100.0, 5.0, 95.0)

        # throughput + cycles (very rough)
        throughput_mwh = float(state.get("throughputMWh", 0.0))
        throughput_mwh += (abs(net_kw) * (dt_s / 3600.0)) / 1000.0
        cycles = float(state.get("cycles", 0.0))
        # approximate: 1 full cycle per 2 * energy capacity throughput
        cycles = throughput_mwh / max(0.001, (bess_kwh / 1000.0) * 2.0)

        state["soc"] = soc
        state["throughputMWh"] = throughput_mwh
        state["cycles"] = cycles

        writes.extend([
            (BESS + "/Status/Available", bess_avail),
            (BESS + "/Status/Mode", mode),
            (BESS + "/Status/AlarmActive", (not bess_avail)),
            (BESS + "/Status/LastAlarm", "" if bess_avail else "MAINT_OUTAGE"),
            (BESS + "/SoC/StateOfCharge_pct", soc),
            (BESS + "/SoC/StateOfHealth_pct", 98.0 - min(8.0, cycles * 0.05)),
            (BESS + "/Power/NetPower_kW", net_kw),
            (BESS + "/Power/ChargePower_kW", ch_kw),
            (BESS + "/Power/DischargePower_kW", dis_kw),
            (BESS + "/Energy/Throughput_MWh", throughput_mwh),
            (BESS + "/Energy/Cycles", cycles),
        ])

        # --- site narrative metrics: net plant (not POI) ---
        plant_net_kw = (wind_total + solar_total + net_kw)
        # lightly enforce export target by additional curtailment in plant (grid will meter at POI)
        if target_export_kw > 0:
            plant_net_kw = min(plant_net_kw, target_export_kw * 1.10)  # allow slight overshoot

        # write
        paths = [p for (p, _) in writes]
        vals = [v for (_, v) in writes]
        results = system.tag.writeBlocking(paths, vals)
        bad = [(paths[i], str(results[i])) for i in range(len(results)) if str(results[i]) != "Good"]
        if bad:
            log.warn("Plant telemetry write failures (first 10): %r" % bad[:10])
            _try_write_diag("WARN", "Write failures: %s" % str(bad[:1]))
        else:
            log.info("Plant telemetry tick ok (wrote %d tags). NetPlant_kW≈%.1f, curtail=%.1f%%, price=%.1f" % (len(paths), plant_net_kw, curtail_pct, rrp))
            _try_write_diag("OK", "")

    except Exception as e:
        log.error("Plant telemetry timer failed", e)
        _try_write_diag("ERROR", str(e))


# Ignition Gateway Timer Scripts execute top-level code each tick.
# Many projects do NOT automatically invoke handleTimerEvent(), so we call it explicitly.
handleTimerEvent()


