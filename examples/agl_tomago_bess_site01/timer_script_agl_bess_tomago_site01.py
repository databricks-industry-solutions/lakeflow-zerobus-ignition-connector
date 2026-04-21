# AGL Tomago BESS demo simulator (memory tags)
# Intended for a Gateway Timer Script (e.g., 1000ms).
#
# Provider: agl_bess
# Root: [agl_bess]AGL/Australia/NSW/Tomago/Site01/...
#
# Notes:
# - Written as top-level code (no defs) for max compatibility across Ignition timer contexts.
# - This script updates SoC + power + thermal/derate + alarm counters.

import random

root = "[agl_bess]AGL/Australia/NSW/Tomago/Site01"
cfg = root + "/Config"
diag = root + "/Diagnostics"
bess = root + "/BESS01"

sim_enabled = system.tag.readBlocking([cfg + "/SimEnabled"])[0].value
if not sim_enabled:
    system.tag.writeBlocking([diag + "/LastStatus"], ["Sim disabled"])
else:
    # Read key values
    soc = float(system.tag.readBlocking([bess + "/Telemetry/SoC_pct"])[0].value or 50.0)
    p_mw = float(system.tag.readBlocking([bess + "/Telemetry/ActivePower_MW"])[0].value or 0.0)
    max_ch = float(system.tag.readBlocking([bess + "/Limits/MaxCharge_MW"])[0].value or 500.0)
    max_dis = float(system.tag.readBlocking([bess + "/Limits/MaxDischarge_MW"])[0].value or 500.0)

    amb = float(system.tag.readBlocking([bess + "/Thermal/AmbientTemp_C"])[0].value or 22.0)
    rack = float(system.tag.readBlocking([bess + "/Thermal/MaxRackTemp_C"])[0].value or 31.0)

    # Simple ambient drift + HVAC effect
    amb = amb + random.uniform(-0.2, 0.2)
    hvac = True
    rack = rack + (0.03 * (amb - rack)) + random.uniform(-0.15, 0.15)

    # Thermal derate model (demo): derate above ~38C rack temp
    derate_active = False
    derate_reason = ""
    derate_factor = 1.0
    if rack > 38.0:
        derate_active = True
        derate_reason = "THERMAL"
        # reduce available power as temp rises
        derate_factor = max(0.4, 1.0 - (rack - 38.0) * 0.06)

    # Apply derate to limits
    eff_max_ch = max_ch * derate_factor
    eff_max_dis = max_dis * derate_factor

    # Power drift (actual power will be driven by dispatch script via grid provider in a real stack).
    # Here we just keep it close to previous value and bounded by limits.
    p_mw = p_mw + random.uniform(-8.0, 8.0)
    if p_mw < -eff_max_ch:
        p_mw = -eff_max_ch
    if p_mw > eff_max_dis:
        p_mw = eff_max_dis

    # Update SoC: positive power means discharge (SoC decreases), negative means charge.
    # Assume 2000 MWh capacity.
    # dt ~ 1s, so delta MWh = MW * (1/3600)
    cap_mwh = 2000.0
    soc_delta = (-p_mw / cap_mwh) * (100.0 / 3600.0)
    soc = soc + soc_delta
    soc = max(5.0, min(98.0, soc))

    # Derived energy
    e_avail = cap_mwh * (soc / 100.0)

    # Basic alarm demo: occasional transient alarm
    alarm_count = int(system.tag.readBlocking([bess + "/Alarms/AlarmCount"])[0].value or 0)
    crit = bool(system.tag.readBlocking([bess + "/Alarms/CriticalAlarmActive"])[0].value or False)
    last_alarm = system.tag.readBlocking([bess + "/Alarms/LastAlarm"])[0].value or ""

    if random.random() < 0.003:
        alarm_count = alarm_count + 1
        last_alarm = "Rack temp sensor noisy"
    if rack > 45.0:
        crit = True
        last_alarm = "THERMAL TRIP RISK"
    else:
        crit = False

    # Mode string
    mode = "STANDBY"
    if p_mw > 5.0:
        mode = "DISCHARGE"
    elif p_mw < -5.0:
        mode = "CHARGE"

    # Writes
    writes = [
        diag + "/TickCount",
        diag + "/LastRun",
        diag + "/LastStatus",
        diag + "/LastError",

        bess + "/Telemetry/SoC_pct",
        bess + "/Telemetry/EnergyAvailable_MWh",
        bess + "/Telemetry/ActivePower_MW",
        bess + "/Telemetry/Mode",
        bess + "/Telemetry/DerateActive",
        bess + "/Telemetry/DerateReason",

        bess + "/Thermal/AmbientTemp_C",
        bess + "/Thermal/HVAC_Running",
        bess + "/Thermal/MaxRackTemp_C",
        bess + "/Alarms/AlarmCount",
        bess + "/Alarms/CriticalAlarmActive",
        bess + "/Alarms/LastAlarm"
    ]
    values = [
        int(system.tag.readBlocking([diag + "/TickCount"])[0].value or 0) + 1,
        system.date.now().toString(),
        "tick ok",
        "",

        soc,
        e_avail,
        p_mw,
        mode,
        derate_active,
        derate_reason,

        amb,
        hvac,
        rack,
        alarm_count,
        crit,
        last_alarm
    ]
    system.tag.writeBlocking(writes, values)

