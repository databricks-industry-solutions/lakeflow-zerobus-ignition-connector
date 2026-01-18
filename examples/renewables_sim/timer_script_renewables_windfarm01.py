def handleTimerEvent():
    """
    Ignition Gateway Timer Script (Jython)
    Updates [renewables]Renewables/Windfarm01/... once per second with a realistic wind->power simulation.

    Paste into: Designer -> Scripting -> Gateway Events -> Timer
    Set: Delay Type = Fixed Delay, Delay (ms) = 1000, Enabled = true
    """

    import math, random

    BASE = "[renewables]Renewables/Windfarm01"
    CONFIG = BASE + "/Config"
    SITE = BASE + "/Site"
    TURBINES = [BASE + "/Turbines/T01", BASE + "/Turbines/T02", BASE + "/Turbines/T03"]

    log = system.util.getLogger("renewables")

    def clamp(x, lo, hi):
        return lo if x < lo else hi if x > hi else x

    def wrap_deg(d):
        d = d % 360.0
        return d + 360.0 if d < 0 else d

    def ang_diff_deg(a, b):
        # shortest signed difference a-b in [-180, 180]
        return (a - b + 180.0) % 360.0 - 180.0

    def power_curve_kw(v_mps, rated_kw, cut_in=3.0, rated=12.0, cut_out=25.0):
        # 0 below cut-in, cubic ramp to rated, flat to cut-out, then 0
        if v_mps < cut_in or v_mps >= cut_out:
            return 0.0
        if v_mps >= rated:
            return rated_kw
        x = (v_mps - cut_in) / (rated - cut_in)  # 0..1
        return rated_kw * (x ** 3)

    try:
        g = system.util.getGlobals()
        state = g.get("renewables_sim_state")
        now = system.date.now()

        if state is None:
            state = {
                "lastTs": now,
                "accumMs": 0,
                "wind": 8.0,
                "windDir": 180.0,
                "faultUntil": dict((t, None) for t in TURBINES),
                "cfg": None,
                "cfgLastReadTs": now,
            }
            g["renewables_sim_state"] = state

        # --- Config (Renewables AU defaults, but operator can tune via tags under [renewables].../Config/*) ---
        # Cache config reads to reduce tag reads; refresh every 5 seconds.
        cfg = state.get("cfg")
        cfg_last = state.get("cfgLastReadTs", now)
        if cfg is None or system.date.millisBetween(cfg_last, now) >= 5000:
            cfg_paths = [
                CONFIG + "/SimEnabled",
                CONFIG + "/UpdateEveryMs",
                CONFIG + "/MeanWind_mps",
                CONFIG + "/MeanReversion_k",
                CONFIG + "/TurbulenceSigma",
                CONFIG + "/WindDirNoiseSigma_deg",
                CONFIG + "/WakeBias_T03_mps",
                CONFIG + "/LocalWindNoiseSigma_mps",
                CONFIG + "/YawGain",
                CONFIG + "/YawNoiseSigma_deg",
                CONFIG + "/YawDerateExponent",
                CONFIG + "/CutIn_mps",
                CONFIG + "/RatedWind_mps",
                CONFIG + "/CutOut_mps",
                CONFIG + "/RatedPower_T01_kW",
                CONFIG + "/RatedPower_T02_kW",
                CONFIG + "/RatedPower_T03_kW",
                CONFIG + "/GearRatio",
                CONFIG + "/RotorRatedRPM",
                CONFIG + "/FaultRatePerSecond",
                CONFIG + "/FaultMinSeconds",
                CONFIG + "/FaultMaxSeconds",
                CONFIG + "/VoltageLL_V",
                CONFIG + "/PF_Mean",
                CONFIG + "/PF_Sigma",
            ]
            vals = system.tag.readBlocking(cfg_paths)
            def _v(i, default):
                try:
                    x = vals[i].value
                    return default if x is None else x
                except Exception:
                    return default
            cfg = {
                "simEnabled": bool(_v(0, True)),
                "updateEveryMs": int(_v(1, 1000)),
                "mu": float(_v(2, 9.0)),
                "k": float(_v(3, 0.06)),
                "sigma": float(_v(4, 0.7)),
                "windDirNoiseSigma": float(_v(5, 4.0)),
                "wakeBiasT03": float(_v(6, -0.3)),
                "localWindNoiseSigma": float(_v(7, 0.4)),
                "yawGain": float(_v(8, 0.35)),
                "yawNoiseSigma": float(_v(9, 0.6)),
                "yawDerateExp": float(_v(10, 1.88)),
                "cutIn": float(_v(11, 3.0)),
                "ratedWind": float(_v(12, 12.0)),
                "cutOut": float(_v(13, 25.0)),
                "ratedKw": [float(_v(14, 3500.0)), float(_v(15, 3600.0)), float(_v(16, 3400.0))],
                "gearRatio": float(_v(17, 80.0)),
                "rotorRatedRpm": float(_v(18, 16.0)),
                "faultRatePerSec": float(_v(19, 0.0008)),
                "faultMinSec": int(_v(20, 20)),
                "faultMaxSec": int(_v(21, 90)),
                "vLL": float(_v(22, 690.0)),
                "pfMean": float(_v(23, 0.97)),
                "pfSigma": float(_v(24, 0.01)),
            }
            state["cfg"] = cfg
            state["cfgLastReadTs"] = now

        if not cfg.get("simEnabled", True):
            return

        dt_ms = system.date.millisBetween(state["lastTs"], now)
        dt_s = max(0.2, min(5.0, dt_ms / 1000.0))
        state["lastTs"] = now
        state["accumMs"] = int(state.get("accumMs", 0)) + int(max(0, dt_ms))

        # Optional throttling: allow UpdateEveryMs > timer period.
        update_every = max(100, int(cfg.get("updateEveryMs", 1000)))
        if state["accumMs"] < update_every:
            return
        state["accumMs"] = 0

        # Site weather (mean reversion + turbulence)
        mu = float(cfg.get("mu", 9.0))
        k = float(cfg.get("k", 0.06))
        sigma = float(cfg.get("sigma", 0.7))
        state["wind"] = clamp(
            state["wind"] + (mu - state["wind"]) * k * dt_s + random.gauss(0, sigma) * math.sqrt(dt_s),
            0.0, 30.0
        )
        wind_dir_noise = float(cfg.get("windDirNoiseSigma", 4.0))
        state["windDir"] = wrap_deg(state["windDir"] + random.gauss(0, wind_dir_noise) * math.sqrt(dt_s))

        site_wind = state["wind"]
        site_dir = state["windDir"]
        air_temp = 16.0 + 6.0 * math.sin((system.date.getHour24(now) / 24.0) * 2.0 * math.pi) + random.gauss(0, 0.3)

        # Curtailment input (0..100)
        try:
            curtail_pct = float(system.tag.readBlocking([SITE + "/Curtailment_pct"])[0].value or 0.0)
        except Exception:
            curtail_pct = 0.0
        curtail_frac = clamp(curtail_pct / 100.0, 0.0, 1.0)

        rated_kw_by_turb = {TURBINES[0]: cfg["ratedKw"][0], TURBINES[1]: cfg["ratedKw"][1], TURBINES[2]: cfg["ratedKw"][2]}
        gear_ratio = float(cfg.get("gearRatio", 80.0))
        v_rated = float(cfg.get("ratedWind", 12.0))
        rotor_rated_rpm = float(cfg.get("rotorRatedRpm", 16.0))
        cut_in = float(cfg.get("cutIn", 3.0))
        cut_out = float(cfg.get("cutOut", 25.0))

        writes = []
        total_power_kw = 0.0
        avail_count = 0

        for tpath in TURBINES:
            rated_kw = rated_kw_by_turb[tpath]

            # Local wind (turbulence + small wake bias)
            wake_bias = float(cfg.get("wakeBiasT03", -0.3)) if tpath.endswith("T03") else 0.0
            local_sigma = float(cfg.get("localWindNoiseSigma", 0.4))
            v = clamp(site_wind + wake_bias + random.gauss(0, local_sigma), 0.0, 30.0)

            # Yaw control (lags wind direction)
            try:
                yaw_pos = float(system.tag.readBlocking([tpath + "/YawPitch/YawPosition_deg"])[0].value)
            except Exception:
                yaw_pos = site_dir

            yaw_gain = float(cfg.get("yawGain", 0.35))
            yaw_sigma = float(cfg.get("yawNoiseSigma", 0.6))
            yaw_pos = wrap_deg(yaw_pos + ang_diff_deg(site_dir, yaw_pos) * yaw_gain + random.gauss(0, yaw_sigma))
            yaw_err = ang_diff_deg(site_dir, yaw_pos)

            # Random faults (rare, short)
            fault_until = state["faultUntil"].get(tpath)
            in_fault = (fault_until is not None) and system.date.isAfter(fault_until, now)

            fault_rate = float(cfg.get("faultRatePerSec", 0.0008))
            if (not in_fault) and (random.random() < (fault_rate * dt_s)):
                fault_min = int(cfg.get("faultMinSec", 20))
                fault_max = int(cfg.get("faultMaxSec", 90))
                fault_seconds = random.randint(min(fault_min, fault_max), max(fault_min, fault_max))
                fault_until = system.date.addSeconds(now, fault_seconds)
                state["faultUntil"][tpath] = fault_until
                in_fault = True

            availability = (not in_fault)
            alarm_active = in_fault
            fault_code = 0 if not in_fault else random.choice([101, 203, 315])
            last_fault = "" if not in_fault else ("FAULT_%d" % fault_code)

            # Wind -> power curve
            p_kw_raw = power_curve_kw(v, rated_kw, cut_in=cut_in, rated=v_rated, cut_out=cut_out)

            # Yaw misalignment derate
            yaw_exp = float(cfg.get("yawDerateExp", 1.88))
            yaw_derate = max(0.0, math.cos(math.radians(yaw_err))) ** yaw_exp
            p_kw = p_kw_raw * yaw_derate

            # Curtailment / availability
            if not availability:
                p_kw = 0.0
            else:
                p_kw *= (1.0 - curtail_frac)

            # Pitch regulation near rated
            pitch_base = 2.0
            pitch = pitch_base + (0.0 if p_kw < 0.95 * rated_kw else min(18.0, (p_kw / max(1.0, rated_kw) - 0.95) * 200.0))
            pitch = clamp(pitch + random.gauss(0, 0.15), 0.0, 22.0)

            # Speeds
            rotor_rpm = clamp((v / v_rated) * rotor_rated_rpm, 0.0, rotor_rated_rpm)
            gen_rpm = rotor_rpm * gear_ratio

            # Electrical approximations
            pf_mean = float(cfg.get("pfMean", 0.97))
            pf_sigma = float(cfg.get("pfSigma", 0.01))
            pf = clamp(pf_mean + random.gauss(0, pf_sigma), 0.90, 1.0)
            v_ll = float(cfg.get("vLL", 690.0))
            current_a = 0.0 if p_kw <= 0 else (p_kw * 1000.0) / (math.sqrt(3.0) * v_ll * max(0.1, pf))
            try:
                kvar = p_kw * math.tan(math.acos(pf))
            except Exception:
                kvar = 0.0

            # Energy integration
            try:
                e_today_kwh = float(system.tag.readBlocking([tpath + "/Electrical/EnergyToday_kWh"])[0].value or 0.0)
                e_total_mwh = float(system.tag.readBlocking([tpath + "/Electrical/EnergyTotal_MWh"])[0].value or 0.0)
            except Exception:
                e_today_kwh, e_total_mwh = 0.0, 0.0

            e_today_kwh += p_kw * (dt_s / 3600.0)
            e_total_mwh += (p_kw * (dt_s / 3600.0)) / 1000.0

            writes.extend([
                (tpath + "/Electrical/Power_kW", p_kw),
                (tpath + "/Electrical/ReactivePower_kVAr", kvar),
                (tpath + "/Electrical/PowerFactor", pf),
                (tpath + "/Electrical/Voltage_V", v_ll),
                (tpath + "/Electrical/Current_A", current_a),
                (tpath + "/Electrical/EnergyToday_kWh", e_today_kwh),
                (tpath + "/Electrical/EnergyTotal_MWh", e_total_mwh),

                (tpath + "/WindRotor/WindSpeed_mps", v),
                (tpath + "/WindRotor/RotorSpeed_RPM", rotor_rpm),
                (tpath + "/WindRotor/GenSpeed_RPM", gen_rpm),
                (tpath + "/WindRotor/NacelleTemp_C", 25.0 + 0.01 * p_kw + random.gauss(0, 0.2)),

                (tpath + "/YawPitch/YawPosition_deg", yaw_pos),
                (tpath + "/YawPitch/YawError_deg", yaw_err),
                (tpath + "/YawPitch/PitchBlade1_deg", pitch + random.gauss(0, 0.05)),
                (tpath + "/YawPitch/PitchBlade2_deg", pitch + random.gauss(0, 0.05)),
                (tpath + "/YawPitch/PitchBlade3_deg", pitch + random.gauss(0, 0.05)),

                (tpath + "/Status/OperatingState", 2 if (availability and p_kw > 0) else (3 if in_fault else 0)),
                (tpath + "/Status/Availability", availability),
                (tpath + "/Status/AlarmActive", alarm_active),
                (tpath + "/Status/FaultCode", fault_code),
                (tpath + "/Status/LastFault", last_fault),
                (tpath + "/Status/Curtailment_pct", curtail_pct),
            ])

            total_power_kw += p_kw
            avail_count += 1 if availability else 0

        availability_pct = 100.0 * (float(avail_count) / float(len(TURBINES)))
        writes.extend([
            (SITE + "/WindSpeed_mps", site_wind),
            (SITE + "/WindDir_deg", site_dir),
            (SITE + "/AirTemp_C", air_temp),
            (SITE + "/Power_Total_kW", total_power_kw),
            (SITE + "/Availability_pct", availability_pct),
        ])

        paths = [p for (p, v) in writes]
        vals = [v for (p, v) in writes]

        results = system.tag.writeBlocking(paths, vals)
        bad = [(paths[i], str(results[i])) for i in range(len(results)) if str(results[i]) != "Good"]

        if bad:
            log.warn("Tag write failures (first 10): %r" % bad[:10])
        else:
            log.info("renewables tick ok (wrote %d tags)" % len(paths))

    except Exception as e:
        log.error("Timer script failed", e)


# Ignition Gateway Timer Scripts execute top-level code each tick.
# Many projects do NOT automatically invoke handleTimerEvent(), so we call it explicitly.
handleTimerEvent()


