# Ignition Gateway Timer Script (Jython) - Manufacturing CMMS (TOP-LEVEL)
# Provider: manufacturing_cmms
# Writes:   [manufacturing_cmms]Manufacturing/Site02/...
# Reads:    optional [manufacturing_grid] events

import random

CMMS = "[manufacturing_cmms]Manufacturing/Site02"
GRID = "[manufacturing_grid]Manufacturing/Site02"

WO = CMMS + "/WorkOrders"
ASSETS = CMMS + "/Assets"
DIAG = CMMS + "/Diagnostics"

log = system.util.getLogger("manufacturing_site02.cmms")

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
    st = g.get("manufacturing_site02_cmms_state")
    if st is None:
        st = {"nextWoSeq": 2001, "outageUntil": {}}
        g["manufacturing_site02_cmms_state"] = st

    # create/close work orders
    v = system.tag.readBlocking([WO + "/ActiveCount", WO + "/HighPriorityCount"])
    active = int(v[0].value or 0)
    high = int(v[1].value or 0)

    created = False
    if random.random() < 0.04:
        created = True
        wo_id = "WO-%d" % int(st["nextWoSeq"])
        st["nextWoSeq"] = int(st["nextWoSeq"]) + 1
        summary = random.choice([
            "Inspect furnace pressure drift",
            "Conveyor vibration investigation",
            "Cutting blade temp high",
            "Thickness gauge calibration",
            "Gas valve tuning"
        ])
        prio_high = (random.random() < 0.25)
        active += 1
        if prio_high:
            high += 1
        system.tag.writeBlocking([WO + "/LastWorkOrderId", WO + "/LastWorkOrderSummary"], [wo_id, summary])

    if active > 0 and random.random() < 0.05:
        active -= 1
        if high > 0 and random.random() < 0.4:
            high -= 1

    # outages
    assets = ["Furnace", "Conveyor", "CuttingStation"]
    for a in assets:
        until = st["outageUntil"].get(a)
        in_out = (until is not None) and system.date.isAfter(until, now)
        if in_out:
            if random.random() < 0.04:
                st["outageUntil"][a] = None
                in_out = False
        else:
            if random.random() < 0.01:
                st["outageUntil"][a] = system.date.addMinutes(now, random.randint(15, 90))
                in_out = True

        reason = "" if not in_out else random.choice(["Preventive maintenance", "Corrective maintenance", "Sensor replacement"])
        system.tag.writeBlocking(
            [ASSETS + "/" + a + "/ForcedOutage", ASSETS + "/" + a + "/OutageReason"],
            [bool(in_out), reason]
        )
        hs = system.tag.readBlocking([ASSETS + "/" + a + "/HealthScore"])[0].value
        hs = float(hs or 92.0)
        hs = max(60.0, hs - random.uniform(0.05, 0.25)) if in_out else min(99.0, hs + random.uniform(0.02, 0.10))
        system.tag.writeBlocking([ASSETS + "/" + a + "/HealthScore"], [hs])

    system.tag.writeBlocking([WO + "/ActiveCount", WO + "/HighPriorityCount"], [active, high])

    safe_write_diag("OK", "")
    if created:
        log.info("CMMS created WO, active=%d high=%d" % (active, high))
    else:
        log.info("CMMS tick ok, active=%d high=%d" % (active, high))

except Exception as e:
    safe_write_diag("ERROR", str(e))
    log.error("CMMS timer failed", e)



