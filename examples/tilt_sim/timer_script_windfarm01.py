def handleTimerEvent():
    """
    Ignition Gateway Timer Script (Jython)
    Updates [tilt_sim]Tilt/Windfarm01/... once per second with a realistic wind->power simulation.

    Paste into: Designer -> Scripting -> Gateway Events -> Timer
    Set: Delay Type = Fixed Delay, Delay (ms) = 1000, Enabled = true
    """

    import math, random

    BASE = "[tilt_sim]Tilt/Windfarm01"
    SITE = BASE + "/Site"
    TURBINES = [BASE + "/Turbines/T01", BASE + "/Turbines/T02", BASE + "/Turbines/T03"]

    log = system.util.getLogger("tilt_sim")

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
        state = g.get("tilt_sim_state")
        now = system.date.now()

        if state is None:
            state = {
                "lastTs": now,
                "wind": 8.0,
                "windDir": 180.0,
                "faultUntil": dict((t, None) for t in TURBINES),
            }
            g["tilt_sim_state"] = state

        dt_ms = system.date.millisBetween(state["lastTs"], now)
        dt_s = max(0.2, min(5.0, dt_ms / 1000.0))
        state["lastTs"] = now

        # Site weather (mean reversion + turbulence)
        mu = 9.0
        k = 0.06
        sigma = 0.7
        state["wind"] = clamp(
            state["wind"] + (mu - state["wind"]) * k * dt_s + random.gauss(0, sigma) * math.sqrt(dt_s),
            0.0, 30.0
        )
        state["windDir"] = wrap_deg(state["windDir"] + random.gauss(0, 4.0) * math.sqrt(dt_s))

        site_wind = state["wind"]
        site_dir = state["windDir"]
        air_temp = 16.0 + 6.0 * math.sin((system.date.getHour24(now) / 24.0) * 2.0 * math.pi) + random.gauss(0, 0.3)

        # Curtailment input (0..100)
        try:
            curtail_pct = float(system.tag.readBlocking([SITE + "/Curtailment_pct"])[0].value or 0.0)
        except Exception:
            curtail_pct = 0.0
        curtail_frac = clamp(curtail_pct / 100.0, 0.0, 1.0)

        rated_kw_by_turb = {TURBINES[0]: 3500.0, TURBINES[1]: 3600.0, TURBINES[2]: 3400.0}
        gear_ratio = 80.0
        v_rated = 12.0
        rotor_rated_rpm = 16.0

        writes = []
        total_power_kw = 0.0
        avail_count = 0

        for tpath in TURBINES:
            rated_kw = rated_kw_by_turb[tpath]

            # Local wind (turbulence + small wake bias)
            wake_bias = -0.3 if tpath.endswith("T03") else 0.0
            v = clamp(site_wind + wake_bias + random.gauss(0, 0.4), 0.0, 30.0)

            # Yaw control (lags wind direction)
            try:
                yaw_pos = float(system.tag.readBlocking([tpath + "/YawPitch/YawPosition_deg"])[0].value)
            except Exception:
                yaw_pos = site_dir

            yaw_pos = wrap_deg(yaw_pos + ang_diff_deg(site_dir, yaw_pos) * 0.35 + random.gauss(0, 0.6))
            yaw_err = ang_diff_deg(site_dir, yaw_pos)

            # Random faults (rare, short)
            fault_until = state["faultUntil"].get(tpath)
            in_fault = (fault_until is not None) and system.date.isAfter(fault_until, now)

            if (not in_fault) and (random.random() < (0.0008 * dt_s)):
                fault_seconds = random.randint(20, 90)
                fault_until = system.date.addSeconds(now, fault_seconds)
                state["faultUntil"][tpath] = fault_until
                in_fault = True

            availability = (not in_fault)
            alarm_active = in_fault
            fault_code = 0 if not in_fault else random.choice([101, 203, 315])
            last_fault = "" if not in_fault else ("FAULT_%d" % fault_code)

            # Wind -> power curve
            p_kw_raw = power_curve_kw(v, rated_kw, cut_in=3.0, rated=v_rated, cut_out=25.0)

            # Yaw misalignment derate
            yaw_derate = max(0.0, math.cos(math.radians(yaw_err))) ** 1.88
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
            pf = clamp(0.97 + random.gauss(0, 0.01), 0.90, 1.0)
            v_ll = 690.0
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
            log.info("tilt_sim tick ok (wrote %d tags)" % len(paths))

    except Exception as e:
        log.error("Timer script failed", e)


