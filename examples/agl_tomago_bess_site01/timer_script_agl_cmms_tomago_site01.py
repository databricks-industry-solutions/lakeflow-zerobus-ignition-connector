# AGL Tomago CMMS simulator (memory tags)
# Intended for a Gateway Timer Script (e.g., 10s).
#
# Provider: agl_cmms
# Root: [agl_cmms]AGL/Australia/NSW/Tomago/Site01/...

import random

root = "[agl_cmms]AGL/Australia/NSW/Tomago/Site01"
cfg = root + "/Config"
diag = root + "/Diagnostics"
cmms = root + "/CMMS"

sim_enabled = system.tag.readBlocking([cfg + "/SimEnabled"])[0].value
if not sim_enabled:
    system.tag.writeBlocking([diag + "/LastStatus"], ["Sim disabled"])
else:
    open_wo = int(system.tag.readBlocking([cmms + "/OpenWorkOrders"])[0].value or 7)
    hi_wo = int(system.tag.readBlocking([cmms + "/HighPriorityWorkOrders"])[0].value or 1)
    planned = bool(system.tag.readBlocking([cmms + "/PlannedOutageActive"])[0].value or False)
    forced = bool(system.tag.readBlocking([cmms + "/ForcedOutageActive"])[0].value or False)
    last_wo = system.tag.readBlocking([cmms + "/LastWorkOrder"])[0].value or ""

    # Slow drift: work orders open/close
    open_wo = max(0, open_wo + random.choice([-1, 0, 0, 1]))
    hi_wo = max(0, min(open_wo, hi_wo + random.choice([-1, 0, 0, 1])))

    # Rare outage toggles
    if random.random() < 0.01:
        planned = not planned
        last_wo = "PM-HVAC-Filter-Replace" if planned else ""
    if random.random() < 0.005:
        forced = not forced
        last_wo = "CM-PCS-Inverter-Fault" if forced else last_wo

    writes = [
        diag + "/TickCount",
        diag + "/LastRun",
        diag + "/LastStatus",
        diag + "/LastError",

        cmms + "/OpenWorkOrders",
        cmms + "/HighPriorityWorkOrders",
        cmms + "/PlannedOutageActive",
        cmms + "/ForcedOutageActive",
        cmms + "/LastWorkOrder"
    ]
    values = [
        int(system.tag.readBlocking([diag + "/TickCount"])[0].value or 0) + 1,
        system.date.now().toString(),
        "tick ok",
        "",

        open_wo,
        hi_wo,
        planned,
        forced,
        last_wo
    ]
    system.tag.writeBlocking(writes, values)

