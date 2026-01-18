# Ignition Gateway Timer Script (Jython) - Manufacturing Plant Telemetry (TOP-LEVEL)
# Provider: sg
# Writes:   [manufacturing]Manufacturing/Site02/...
# Reads:    optional [manufacturing_grid] dispatch/curtailment/prices and [manufacturing_cmms] forced outages

import math, random

Manufacturing = "[manufacturing]Manufacturing/Site02"
GRID = "[manufacturing_grid]Manufacturing/Site02"
CMMS = "[manufacturing_cmms]Manufacturing/Site02"

CFG = Manufacturing + "/Config"
FURNACE = Manufacturing + "/Furnace"
CONV = Manufacturing + "/Conveyor"
CUT = Manufacturing + "/CuttingStation"
KPI = Manufacturing + "/KPIs"
DIAG = Manufacturing + "/Diagnostics"

log = system.util.getLogger("manufacturing_site02.plant")

def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x

def safe_write_diag(status, msg):
    try:
        ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
        system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, status, msg or ""])
        try:
            cur = system.tag.readBlocking([DIAG + "/TickCount"])[0].value
            cur = int(cur or 0)
            system.tag.writeBlocking([DIAG + "/TickCount"], [cur + 1])
        except:
            pass
    except:
        pass

try:
    safe_write_diag("START", "")

    g = system.util.getGlobals()
    now = system.date.now()
    st = g.get("manufacturing_site02_state")
    if st is None:
        st = {
            "lastTs": now,
            "accMs": 0,
            "cuts": 0,
            "meltTemp": 1500.0,
            "formTemp": 1100.0,
            "pressure": 1.05,
            "gasFlow": 1200.0,
            "thickness": 4.0,
            "convSpeed": 18.0,
            "convLoad": 250.0,
            "vibration": 1.2,
            "bladeTemp": 60.0,
            "quality": 97.0,
            "throughput": 120.0,
            "scrap": 1.5
        }
        g["manufacturing_site02_state"] = st

    dt_ms = system.date.millisBetween(st["lastTs"], now)
    dt_s = max(0.2, min(5.0, float(dt_ms) / 1000.0))
    st["lastTs"] = now

    # Config (read every tick; small number of tags)
    cfgv = system.tag.readBlocking([CFG + "/SimEnabled", CFG + "/UpdateEveryMs"])
    sim_enabled = bool(cfgv[0].value if cfgv[0].value is not None else True)
    update_every = int(cfgv[1].value or 1000)

    do_run = sim_enabled
    st["accMs"] = int(st.get("accMs", 0)) + int(max(0, dt_ms))
    if st["accMs"] < max(200, update_every):
        do_run = False
    else:
        st["accMs"] = 0

    if not do_run:
        safe_write_diag("SKIP", "SimEnabled=false or throttled")
    else:
        # Drivers from manufacturing_grid (defaults)
        target_rate = 120.0
        curtail_pct = 0.0
        gas_price = 14.0
        elec_price = 120.0
        try:
            gv = system.tag.readBlocking([
                GRID + "/Dispatch/TargetRate_units_per_min",
                GRID + "/Dispatch/Curtailment_pct",
                GRID + "/Energy/GasPrice_EUR_per_GJ",
                GRID + "/Energy/ElectricityPrice_EUR_per_MWh"
            ])
            target_rate = float(gv[0].value or target_rate)
            curtail_pct = float(gv[1].value or curtail_pct)
            gas_price = float(gv[2].value or gas_price)
            elec_price = float(gv[3].value or elec_price)
        except:
            pass
        curtail_frac = clamp(curtail_pct / 100.0, 0.0, 1.0)

        # Forced outages (defaults)
        outage_furnace = False
        outage_conv = False
        outage_cut = False
        try:
            cv = system.tag.readBlocking([
                CMMS + "/Assets/Furnace/ForcedOutage",
                CMMS + "/Assets/Conveyor/ForcedOutage",
                CMMS + "/Assets/CuttingStation/ForcedOutage"
            ])
            outage_furnace = bool(cv[0].value or False)
            outage_conv = bool(cv[1].value or False)
            outage_cut = bool(cv[2].value or False)
        except:
            pass

        # Furnace dynamics (simple OU + coupling)
        # When furnace is out, temps drift down toward safe idle.
        melt_target = 1500.0 if not outage_furnace else 900.0
        form_target = 1100.0 if not outage_furnace else 750.0
        k = 0.04
        st["meltTemp"] = clamp(st["meltTemp"] + (melt_target - st["meltTemp"]) * k * dt_s + random.gauss(0, 2.5), 600.0, 1650.0)
        st["formTemp"] = clamp(st["formTemp"] + (form_target - st["formTemp"]) * k * dt_s + random.gauss(0, 2.0), 500.0, 1250.0)
        st["pressure"] = clamp(st["pressure"] + random.gauss(0, 0.005) + (0.01 if not outage_furnace else -0.01), 0.85, 1.25)
        # Gas flow correlates with melt temp and curtailment
        base_gas = 1100.0 + (st["meltTemp"] - 1450.0) * 1.5
        st["gasFlow"] = clamp(base_gas * (1.0 - 0.6 * curtail_frac) + random.gauss(0, 10.0), 200.0, 1800.0)

        # Thickness and quality (affected by stability)
        thickness_target = 4.0 + random.gauss(0, 0.01)
        st["thickness"] = clamp(0.97 * st["thickness"] + 0.03 * thickness_target + random.gauss(0, 0.01), 3.0, 6.0)

        # Conveyor (if out, speed=0)
        if outage_conv:
            st["convSpeed"] = 0.0
        else:
            st["convSpeed"] = clamp(0.9 * st["convSpeed"] + 0.1 * (18.0 + random.gauss(0, 0.3)), 10.0, 24.0)
        st["convLoad"] = clamp(240.0 + (st["convSpeed"] - 18.0) * 8.0 + random.gauss(0, 6.0), 50.0, 600.0)
        # Vibration increases with speed and maintenance issues
        st["vibration"] = clamp(1.0 + (st["convSpeed"] / 18.0) * 0.4 + random.gauss(0, 0.08) + (0.6 if outage_conv else 0.0), 0.2, 8.0)

        # Cutting station: cut count increments with throughput unless out
        if outage_cut or outage_conv or outage_furnace:
            inc = 0
        else:
            inc = int(max(0, (target_rate * (1.0 - curtail_frac)) * (dt_s / 60.0)))
        st["cuts"] = int(st.get("cuts", 0)) + inc
        st["bladeTemp"] = clamp(55.0 + st["convSpeed"] * 0.6 + random.gauss(0, 0.8) + (10.0 if inc > 0 else -5.0), 20.0, 140.0)

        # Quality score degrades with thickness drift, vibration, and furnace instability
        thickness_err = abs(st["thickness"] - 4.0)
        instability = abs(st["meltTemp"] - melt_target) / 200.0
        vib_pen = max(0.0, st["vibration"] - 1.5) * 2.0
        q = 99.0 - thickness_err * 25.0 - instability * 8.0 - vib_pen
        if outage_furnace or outage_cut:
            q -= 10.0
        st["quality"] = clamp(0.9 * st["quality"] + 0.1 * q + random.gauss(0, 0.3), 40.0, 99.5)

        # Throughput + scrap proxy
        throughput = target_rate * (1.0 - curtail_frac)
        if outage_furnace or outage_conv or outage_cut:
            throughput = 0.0
        st["throughput"] = clamp(0.85 * st["throughput"] + 0.15 * throughput + random.gauss(0, 1.0), 0.0, 220.0)
        st["scrap"] = clamp(0.85 * st["scrap"] + 0.15 * (max(0.5, (100.0 - st["quality"]) * 0.12)) + random.gauss(0, 0.05), 0.1, 25.0)

        writes = [
            (FURNACE + "/Temperature_Melting_C", st["meltTemp"]),
            (FURNACE + "/Temperature_Forming_C", st["formTemp"]),
            (FURNACE + "/Pressure_Chamber_bar", st["pressure"]),
            (FURNACE + "/Gas_Flow_m3h", st["gasFlow"]),
            (FURNACE + "/Glass_Thickness_mm", st["thickness"]),
            (CONV + "/Speed_mpm", st["convSpeed"]),
            (CONV + "/Load_kg", st["convLoad"]),
            (CONV + "/Vibration_mms", st["vibration"]),
            (CUT + "/Cut_Count", st["cuts"]),
            (CUT + "/Blade_Temp_C", st["bladeTemp"]),
            (CUT + "/Quality_Score", st["quality"]),
            (KPI + "/Throughput_units_per_min", st["throughput"]),
            (KPI + "/ScrapRate_pct", st["scrap"])
        ]

        system.tag.writeBlocking([p for (p, _) in writes], [v for (_, v) in writes])
        safe_write_diag("OK", "")
        log.info("Manufacturing plant tick ok. Throughput=%.1f, Scrap=%.2f%%, Quality=%.1f" % (st["throughput"], st["scrap"], st["quality"]))

except Exception as e:
    safe_write_diag("ERROR", str(e))
    log.error("Manufacturing plant timer failed", e)


