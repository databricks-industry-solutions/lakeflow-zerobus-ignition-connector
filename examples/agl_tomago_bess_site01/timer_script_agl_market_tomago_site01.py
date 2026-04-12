# AGL Tomago market simulator (memory tags)
# Intended for a Gateway Timer Script (e.g., 2000ms).
#
# Provider: agl_market
# Root: [agl_market]AGL/Australia/NSW/Tomago/Site01/...

import random

root = "[agl_market]AGL/Australia/NSW/Tomago/Site01"
cfg = root + "/Config"
diag = root + "/Diagnostics"
mkt = root + "/Market"

sim_enabled = system.tag.readBlocking([cfg + "/SimEnabled"])[0].value
if not sim_enabled:
    system.tag.writeBlocking([diag + "/LastStatus"], ["Sim disabled"])
else:
    rrp = float(system.tag.readBlocking([mkt + "/RRP_AUD_per_MWh"])[0].value or 110.0)
    spike = bool(system.tag.readBlocking([mkt + "/PriceSpikeActive"])[0].value or False)
    fcas_c = float(system.tag.readBlocking([mkt + "/FCAS_ContingencyPrice_AUD_per_MWh"])[0].value or 18.0)
    fcas_r = float(system.tag.readBlocking([mkt + "/FCAS_RegPrice_AUD_per_MWh"])[0].value or 12.0)

    # Mean-reverting-ish price with occasional spikes
    rrp = rrp + (110.0 - rrp) * 0.05 + random.uniform(-8.0, 8.0)
    if random.random() < 0.02:
        spike = True
        rrp = rrp + random.uniform(150.0, 400.0)
    else:
        spike = False

    fcas_c = max(0.0, fcas_c + random.uniform(-2.0, 3.0))
    fcas_r = max(0.0, fcas_r + random.uniform(-1.5, 2.5))

    writes = [
        diag + "/TickCount",
        diag + "/LastRun",
        diag + "/LastStatus",
        diag + "/LastError",

        mkt + "/RRP_AUD_per_MWh",
        mkt + "/PriceSpikeActive",
        mkt + "/FCAS_ContingencyPrice_AUD_per_MWh",
        mkt + "/FCAS_RegPrice_AUD_per_MWh"
    ]
    values = [
        int(system.tag.readBlocking([diag + "/TickCount"])[0].value or 0) + 1,
        system.date.now().toString(),
        "tick ok",
        "",

        rrp,
        spike,
        fcas_c,
        fcas_r
    ]
    system.tag.writeBlocking(writes, values)

