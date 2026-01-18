def handleTimerEvent():
    """
    Ignition Gateway Timer Script (Jython)
    Source: Maintenance / CMMS events

    Provider: [cmms]
    Base:     [cmms]Renewables/Site01/...

    Responsibilities:
    - Create/close work orders
    - Force outages for certain assets (maintenance impacts production)
    - Update health scores gradually, influenced by recent outages

    Paste into: Designer -> Scripting -> Gateway Events -> Timer
    Recommended: Fixed Delay 2000ms (less frequent is fine), Enabled=true
    """
    import random

    CMMS = "[cmms]Renewables/Site01"
    GRID = "[grid]Renewables/Site01"

    ASSETS = [
        ("Windfarm01/T01", CMMS + "/Assets/Windfarm01/T01"),
        ("Windfarm01/T02", CMMS + "/Assets/Windfarm01/T02"),
        ("Windfarm01/T03", CMMS + "/Assets/Windfarm01/T03"),
        ("SolarFarm01/I01", CMMS + "/Assets/SolarFarm01/I01"),
        ("SolarFarm01/I02", CMMS + "/Assets/SolarFarm01/I02"),
        ("BESS01", CMMS + "/Assets/BESS01"),
    ]

    WO = CMMS + "/WorkOrders"
    OPS = CMMS + "/Operations"

    log = system.util.getLogger("renewables_site01.cmms")

    # Optional self-debug tags (create these in Tag Browser or re-import updated JSON).
    DIAG = CMMS + "/Diagnostics"

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

    try:
        g = system.util.getGlobals()
        now = system.date.now()
        state = g.get("renewables_site01_cmms_state")
        if state is None:
            state = {
                "outageUntilByAsset": {},
                "nextWoSeq": 1001
            }
            g["renewables_site01_cmms_state"] = state

        # Weather hold sometimes during grid events
        grid_ev = system.tag.readBlocking([GRID + "/Events/VoltageSagActive", GRID + "/Events/FrequencyEventActive"])
        weather_hold = bool((grid_ev[0].value or False) or (grid_ev[1].value or False)) and (random.random() < 0.25)

        # technician staffing
        techs = 0 if weather_hold else random.choice([0, 1, 2, 3])

        # active WO counters (stored tags)
        wo_vals = system.tag.readBlocking([WO + "/ActiveCount", WO + "/HighPriorityCount"])
        active_count = int(wo_vals[0].value or 0)
        high_count = int(wo_vals[1].value or 0)

        # Occasionally create a work order
        created = False
        if random.random() < 0.03:
            created = True
            wo_id = "WO-%d" % int(state.get("nextWoSeq", 1001))
            state["nextWoSeq"] = int(state.get("nextWoSeq", 1001)) + 1
            summary = random.choice([
                "Inspect turbine yaw drive (abnormal vibration)",
                "Solar inverter derate investigation (thermal)",
                "BESS PCS alarm reset and diagnostics",
                "POI meter comms check",
                "Blade pitch calibration",
                "Transformer oil temp check"
            ])
            priority_high = (random.random() < 0.25)
            active_count += 1
            if priority_high:
                high_count += 1
            system.tag.writeBlocking(
                [WO + "/LastWorkOrderId", WO + "/LastWorkOrderSummary"],
                [wo_id, summary]
            )

        # Occasionally close a work order
        if active_count > 0 and random.random() < 0.04 and techs > 0 and not weather_hold:
            active_count -= 1
            if high_count > 0 and random.random() < 0.50:
                high_count -= 1

        # Forced outages: rare, but long enough to show in dashboards
        outage_started = False
        outage_ended = False
        outage_asset = None
        outage_reason = None

        for (asset_key, asset_path) in ASSETS:
            until = state["outageUntilByAsset"].get(asset_key)
            in_outage = (until is not None) and system.date.isAfter(until, now)

            if in_outage:
                # occasionally end early if techs on site
                if techs > 0 and random.random() < 0.03 and not weather_hold:
                    state["outageUntilByAsset"][asset_key] = None
                    in_outage = False
                    outage_ended = True
                    outage_asset = asset_key
            else:
                # possibly start a new outage
                if random.random() < 0.006:
                    dur_min = random.randint(20, 120)
                    state["outageUntilByAsset"][asset_key] = system.date.addMinutes(now, dur_min)
                    in_outage = True
                    outage_started = True
                    outage_asset = asset_key
                    outage_reason = random.choice([
                        "Preventive maintenance",
                        "Unplanned corrective maintenance",
                        "Component replacement",
                        "Electrical fault investigation",
                        "Comms / sensor replacement"
                    ])

            # write forced outage flag + reason
            forced = bool(in_outage)
            reason = "" if not forced else (outage_reason if outage_reason is not None else "Maintenance")
            system.tag.writeBlocking([asset_path + "/ForcedOutage", asset_path + "/OutageReason"], [forced, reason])

            # health score drifts down slightly during outages and recovers slowly otherwise
            hs = system.tag.readBlocking([asset_path + "/HealthScore"])[0].value
            hs = float(hs or 92.0)
            if forced:
                hs = max(60.0, hs - random.uniform(0.05, 0.25))
            else:
                hs = min(99.0, hs + random.uniform(0.02, 0.10))
            system.tag.writeBlocking([asset_path + "/HealthScore"], [hs])

        # summarize into operations tags
        last_event = ""
        if outage_started:
            last_event = "OUTAGE_START:%s" % outage_asset
        elif outage_ended:
            last_event = "OUTAGE_END:%s" % outage_asset
        elif created:
            last_event = "WORK_ORDER_CREATED"

        system.tag.writeBlocking(
            [WO + "/ActiveCount", WO + "/HighPriorityCount", OPS + "/TechniciansOnSite", OPS + "/WeatherHold"],
            [active_count, high_count, techs, weather_hold]
        )

        if last_event:
            log.info("CMMS tick: %s, activeWO=%d, high=%d, techs=%d, weatherHold=%r" % (last_event, active_count, high_count, techs, weather_hold))
        else:
            log.info("CMMS tick ok: activeWO=%d, high=%d, techs=%d, weatherHold=%r" % (active_count, high_count, techs, weather_hold))
        _try_write_diag("OK", "")

    except Exception as e:
        log.error("CMMS timer failed", e)
        _try_write_diag("ERROR", str(e))


# Ignition Gateway Timer Scripts execute top-level code each tick.
# Many projects do NOT automatically invoke handleTimerEvent(), so we call it explicitly.
handleTimerEvent()


