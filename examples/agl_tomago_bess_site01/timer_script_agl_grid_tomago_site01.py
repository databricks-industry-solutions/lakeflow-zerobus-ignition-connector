# AGL Tomago grid/dispatch simulator (memory tags)
# Intended for a Gateway Timer Script (e.g., 1000ms).
#
# Provider: agl_grid
# Root: [agl_grid]AGL/Australia/NSW/Tomago/Site01/...
#
# This drives:
# - dispatch target
# - constraint/curtailment events
# - POI export/import (proxy)

import random

root = "[agl_grid]AGL/Australia/NSW/Tomago/Site01"
cfg = root + "/Config"
diag = root + "/Diagnostics"

poi = root + "/Substation01/POI"
disp = root + "/Dispatch"
events = root + "/Events"

sim_enabled = system.tag.readBlocking([cfg + "/SimEnabled"])[0].value
if not sim_enabled:
    system.tag.writeBlocking([diag + "/LastStatus"], ["Sim disabled"])
else:
    target = float(system.tag.readBlocking([disp + "/TargetNetPower_MW"])[0].value or 0.0)
    constraint = bool(system.tag.readBlocking([disp + "/ConstraintActive"])[0].value or False)
    curtail = float(system.tag.readBlocking([disp + "/Curtailment_pct"])[0].value or 0.0)

    # Occasionally toggle constraints (demo)
    if random.random() < 0.01:
        constraint = not constraint
        if constraint:
            system.tag.writeBlocking([disp + "/ConstraintReason"], ["NETWORK_LIMIT"])
        else:
            system.tag.writeBlocking([disp + "/ConstraintReason"], [""])

    # Price-driven dispatch target proxy: swing between charge/discharge.
    # (Market provider can also influence target later in Databricks Silver/Gold.)
    target = target + random.uniform(-35.0, 35.0)
    target = max(-450.0, min(450.0, target))

    # Curtailment when constrained: reduce effective target magnitude
    if constraint:
        curtail = min(40.0, max(5.0, curtail + random.uniform(-1.5, 3.0)))
    else:
        curtail = max(0.0, curtail - 2.0)

    eff_target = target * (1.0 - (curtail / 100.0))

    # POI export/import (simple)
    # convention: positive net means export, negative means import
    net = eff_target + random.uniform(-8.0, 8.0)
    export_mw = max(0.0, net)
    import_mw = max(0.0, -net)

    # Grid events (rare)
    freq_evt = bool(system.tag.readBlocking([events + "/FrequencyEventActive"])[0].value or False)
    volt_evt = bool(system.tag.readBlocking([events + "/VoltageSagActive"])[0].value or False)
    last_evt = system.tag.readBlocking([events + "/LastEvent"])[0].value or ""
    if random.random() < 0.002:
        freq_evt = True
        volt_evt = False
        last_evt = "FREQUENCY_EVENT"
    elif random.random() < 0.002:
        volt_evt = True
        freq_evt = False
        last_evt = "VOLTAGE_SAG"
    else:
        freq_evt = False
        volt_evt = False

    writes = [
        diag + "/TickCount",
        diag + "/LastRun",
        diag + "/LastStatus",
        diag + "/LastError",

        disp + "/TargetNetPower_MW",
        disp + "/ConstraintActive",
        disp + "/Curtailment_pct",

        poi + "/ExportPower_MW",
        poi + "/ImportPower_MW",
        poi + "/NetPower_MW",
        poi + "/Voltage_kV",
        poi + "/Frequency_Hz",

        events + "/FrequencyEventActive",
        events + "/VoltageSagActive",
        events + "/LastEvent"
    ]
    values = [
        int(system.tag.readBlocking([diag + "/TickCount"])[0].value or 0) + 1,
        system.date.now().toString(),
        "tick ok",
        "",

        target,
        constraint,
        curtail,

        export_mw,
        import_mw,
        net,
        330.0 + random.uniform(-1.2, 1.2),
        50.0 + random.uniform(-0.05, 0.05),

        freq_evt,
        volt_evt,
        last_evt
    ]
    system.tag.writeBlocking(writes, values)

