def handleTimerEvent():
    """
    Ignition Gateway Timer Script (Jython)
    Source: Grid + Market

    Provider: [grid]
    Base:     [grid]Renewables/Site01/...

    Responsibilities:
    - Market price shape + spikes
    - Dispatch target + curtailment / constraint windows
    - POI metering (reads plant telemetry from [renewables] and produces POI measurements)

    Paste into: Designer -> Scripting -> Gateway Events -> Timer
    Recommended: Fixed Delay 1000ms (or 2000ms), Enabled=true
    """
    import math, random

    GRID = "[grid]Renewables/Site01"
    TILT = "[renewables]Renewables/Site01"

    POI = GRID + "/Substation01/POI"
    DISPATCH = GRID + "/Dispatch"
    MARKET = GRID + "/Market"
    EVENTS = GRID + "/Events"

    log = system.util.getLogger("renewables_site01.grid")

    # Optional self-debug tags (create these in Tag Browser or re-import updated JSON).
    DIAG = GRID + "/Diagnostics"

    def _try_write_diag(status, err_msg):
        try:
            # Only writes if tags exist; ignore failures so simulation still runs.
            ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
            system.tag.writeBlocking(
                [DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"],
                [ts, status, err_msg or ""]
            )
            # TickCount increments best-effort
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
        # Heartbeat: if you don't see TickCount/LastRun moving, the timer isn't executing (or changes weren't applied).
        _try_write_diag("START", "")

        g = system.util.getGlobals()
        now = system.date.now()
        state = g.get("renewables_site01_grid_state")
        if state is None:
            state = {
                "lastTs": now,
                "priceBase": 85.0,
                "spikeUntil": None,
                "constraintUntil": None,
                "freqEventUntil": None,
                "voltSagUntil": None
            }
            g["renewables_site01_grid_state"] = state

        dt_ms = system.date.millisBetween(state["lastTs"], now)
        dt_s = max(0.2, min(5.0, dt_ms / 1000.0))
        state["lastTs"] = now

        hour = system.date.getHour24(now)

        # --- market price (diurnal + noise + occasional spikes) ---
        diurnal = 25.0 * math.sin(((hour - 7) / 24.0) * 2.0 * math.pi) + 20.0 * math.sin(((hour - 17) / 24.0) * 2.0 * math.pi)
        base = 80.0 + diurnal + random.gauss(0, 3.0)

        # spike logic
        spike_active = False
        if state["spikeUntil"] is not None and system.date.isAfter(state["spikeUntil"], now):
            spike_active = True
        else:
            # small chance to start a spike
            if random.random() < (0.0009 * dt_s):
                state["spikeUntil"] = system.date.addSeconds(now, random.randint(30, 120))
                spike_active = True

        if spike_active:
            rrp = clamp(base + random.uniform(120.0, 450.0), -100.0, 15000.0)
        else:
            rrp = clamp(base, -100.0, 300.0)

        # --- grid events + constraints ---
        freq_event = False
        volt_sag = False
        constraint_active = False

        if state["freqEventUntil"] is not None and system.date.isAfter(state["freqEventUntil"], now):
            freq_event = True
        elif random.random() < (0.0007 * dt_s):
            state["freqEventUntil"] = system.date.addSeconds(now, random.randint(10, 40))
            freq_event = True

        if state["voltSagUntil"] is not None and system.date.isAfter(state["voltSagUntil"], now):
            volt_sag = True
        elif random.random() < (0.0005 * dt_s):
            state["voltSagUntil"] = system.date.addSeconds(now, random.randint(10, 30))
            volt_sag = True

        if state["constraintUntil"] is not None and system.date.isAfter(state["constraintUntil"], now):
            constraint_active = True
        elif (freq_event or volt_sag) and random.random() < 0.3:
            state["constraintUntil"] = system.date.addSeconds(now, random.randint(60, 180))
            constraint_active = True
        elif random.random() < (0.0004 * dt_s):
            state["constraintUntil"] = system.date.addSeconds(now, random.randint(60, 180))
            constraint_active = True

        # --- dispatch target + curtailment ---
        # crude policy: target depends on time-of-day and grid conditions.
        # We let it be a stable business driver for "tracking error" dashboards.
        base_target = 12000.0 + 2000.0 * math.sin(((hour - 9) / 24.0) * 2.0 * math.pi)
        target_export_kw = clamp(base_target + random.gauss(0, 150.0), 2000.0, 22000.0)

        curtail_pct = 0.0
        if constraint_active:
            curtail_pct = clamp(5.0 + random.uniform(0.0, 25.0), 0.0, 60.0)
        if volt_sag:
            curtail_pct = max(curtail_pct, clamp(10.0 + random.uniform(0.0, 30.0), 0.0, 80.0))
        if freq_event:
            # could be FCAS enablement
            curtail_pct = max(curtail_pct, clamp(2.0 + random.uniform(0.0, 10.0), 0.0, 25.0))

        # FCAS enabled sometimes during frequency events
        fcas_enabled = bool(freq_event and (random.random() < 0.75))

        # --- POI meter reads plant ---
        plant_paths = [
            # wind + solar totals
            TILT + "/Windfarm01/Site/Power_Total_kW",
            TILT + "/SolarFarm01/Plant/Power_Total_kW",
            # BESS net (+ discharge, - charge)
            TILT + "/BESS01/Power/NetPower_kW",
            # breaker status influences export later
            POI + "/BreakerClosed"
        ]
        pv = system.tag.readBlocking(plant_paths)
        wind_kw = float(pv[0].value or 0.0)
        solar_kw = float(pv[1].value or 0.0)
        bess_kw = float(pv[2].value or 0.0)
        breaker_closed = bool(pv[3].value if pv[3].value is not None else True)

        net_kw = wind_kw + solar_kw + bess_kw

        # apply dispatch target and curtailment at grid boundary
        if (not breaker_closed):
            export_kw = 0.0
            import_kw = 0.0
        else:
            allowed_kw = target_export_kw * (1.0 - (curtail_pct / 100.0))
            export_kw = max(0.0, min(net_kw, allowed_kw))
            # import occurs when plant net is negative (charging BESS or low gen)
            import_kw = max(0.0, -net_kw)

        # POI quality-ish values
        freq = 50.0 + (random.gauss(0, 0.02) if not freq_event else random.gauss(-0.18, 0.05))
        v_kv = 66.0 + (random.gauss(0, 0.05) if not volt_sag else random.gauss(-0.9, 0.2))
        pf = clamp(0.98 + random.gauss(0, 0.01), 0.90, 1.0)
        kvar = export_kw * math.tan(math.acos(pf)) if export_kw > 0 else 0.0

        # --- writes ---
        last_event = ""
        if freq_event:
            last_event = "FREQ_EVENT"
        elif volt_sag:
            last_event = "VOLT_SAG"
        elif constraint_active:
            last_event = "CONSTRAINT"

        writes = [
            (MARKET + "/RRP_AUD_per_MWh", rrp),
            (MARKET + "/PriceSpikeActive", spike_active),
            (DISPATCH + "/TargetExport_kW", target_export_kw),
            (DISPATCH + "/Curtailment_pct", curtail_pct),
            (DISPATCH + "/ConstraintActive", constraint_active),
            (DISPATCH + "/FCAS_Enabled", fcas_enabled),
            (EVENTS + "/FrequencyEventActive", freq_event),
            (EVENTS + "/VoltageSagActive", volt_sag),
            (EVENTS + "/LastEvent", last_event),
            (POI + "/ExportPower_kW", export_kw),
            (POI + "/ImportPower_kW", import_kw),
            (POI + "/NetPower_kW", export_kw - import_kw),
            (POI + "/ReactivePower_kVAr", kvar),
            (POI + "/PowerFactor", pf),
            (POI + "/Voltage_kV", v_kv),
            (POI + "/Frequency_Hz", freq),
        ]

        paths = [p for (p, _) in writes]
        vals = [v for (_, v) in writes]
        results = system.tag.writeBlocking(paths, vals)
        bad = [(paths[i], str(results[i])) for i in range(len(results)) if str(results[i]) != "Good"]
        if bad:
            log.warn("Grid/market write failures (first 10): %r" % bad[:10])
            _try_write_diag("WARN", "Write failures: %s" % str(bad[:1]))
        else:
            log.info("Grid tick ok. POI export=%.1f kW (target=%.1f, curtail=%.1f%%), price=%.1f" % (export_kw, target_export_kw, curtail_pct, rrp))
            _try_write_diag("OK", "")

    except Exception as e:
        log.error("Grid/market timer failed", e)
        _try_write_diag("ERROR", str(e))


# Ignition Gateway Timer Scripts execute top-level code each tick.
# Many projects do NOT automatically invoke handleTimerEvent(), so we call it explicitly.
handleTimerEvent()


