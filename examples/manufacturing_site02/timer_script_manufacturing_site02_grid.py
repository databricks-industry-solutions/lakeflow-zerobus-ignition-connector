# Ignition Gateway Timer Script (Jython) - Manufacturing Grid/Dispatch (TOP-LEVEL)
# Provider: manufacturing_grid
# Writes:   [manufacturing_grid]Manufacturing/Site02/...
# Reads:    [manufacturing] KPIs (throughput, scrap) to generate realistic dispatch/constraint behavior

import math, random

GRID = "[manufacturing_grid]Manufacturing/Site02"
Manufacturing = "[manufacturing]Manufacturing/Site02"

DISPATCH = GRID + "/Dispatch"
ENERGY = GRID + "/Energy"
EVENTS = GRID + "/Events"
DIAG = GRID + "/Diagnostics"

log = system.util.getLogger("manufacturing_site02.grid")

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
    st = g.get("manufacturing_site02_grid_state")
    if st is None:
        st = {"lastTs": now, "spikeUntil": None, "constraintUntil": None}
        g["manufacturing_site02_grid_state"] = st

    dt_ms = system.date.millisBetween(st["lastTs"], now)
    dt_s = max(0.2, min(5.0, float(dt_ms) / 1000.0))
    st["lastTs"] = now

    hour = system.date.getHour24(now)

    # Base target rate varies by shift (day vs night)
    shift = 1.0 if 6 <= hour <= 20 else 0.85
    target = 120.0 * shift + 10.0 * math.sin(((hour - 8) / 24.0) * 2.0 * math.pi) + random.gauss(0, 1.5)
    target = clamp(target, 60.0, 180.0)

    # Read current throughput/scrap to trigger constraints
    throughput = 0.0
    scrap = 1.5
    try:
        pv = system.tag.readBlocking([Manufacturing + "/KPIs/Throughput_units_per_min", Manufacturing + "/KPIs/ScrapRate_pct"])
        throughput = float(pv[0].value or 0.0)
        scrap = float(pv[1].value or 1.5)
    except:
        pass

    # Constraint logic: if scrap rising or energy spike, curtail a bit
    constraint = False
    if st["constraintUntil"] is not None and system.date.isAfter(st["constraintUntil"], now):
        constraint = True
    elif scrap >= 4.0 and random.random() < 0.15:
        st["constraintUntil"] = system.date.addSeconds(now, random.randint(60, 180))
        constraint = True

    # Energy prices with occasional spikes
    spike = False
    if st["spikeUntil"] is not None and system.date.isAfter(st["spikeUntil"], now):
        spike = True
    elif random.random() < (0.0008 * dt_s):
        st["spikeUntil"] = system.date.addSeconds(now, random.randint(30, 120))
        spike = True

    gas_price = clamp(14.0 + 1.5 * math.sin(((hour - 7) / 24.0) * 2.0 * math.pi) + random.gauss(0, 0.3), 8.0, 40.0)
    elec_price = clamp(120.0 + 30.0 * math.sin(((hour - 12) / 24.0) * 2.0 * math.pi) + random.gauss(0, 4.0), 20.0, 600.0)
    if spike:
        elec_price = clamp(elec_price + random.uniform(150.0, 500.0), 20.0, 1500.0)

    curtail_pct = 0.0
    if constraint:
        curtail_pct = clamp(5.0 + (scrap - 2.0) * 4.0 + random.uniform(0.0, 5.0), 0.0, 40.0)
    if spike:
        curtail_pct = max(curtail_pct, clamp(5.0 + random.uniform(0.0, 15.0), 0.0, 50.0))

    last_event = ""
    if spike:
        last_event = "ENERGY_SPIKE"
    elif constraint:
        last_event = "CONSTRAINT"

    writes = [
        (DISPATCH + "/TargetRate_units_per_min", target),
        (DISPATCH + "/Curtailment_pct", curtail_pct),
        (DISPATCH + "/ConstraintActive", bool(constraint)),
        (ENERGY + "/GasPrice_EUR_per_GJ", gas_price),
        (ENERGY + "/ElectricityPrice_EUR_per_MWh", elec_price),
        (EVENTS + "/EnergySpikeActive", bool(spike)),
        (EVENTS + "/LastEvent", last_event),
    ]
    system.tag.writeBlocking([p for (p, _) in writes], [v for (_, v) in writes])

    safe_write_diag("OK", "")
    log.info("Manufacturing grid tick ok. Target=%.1f, Curtail=%.1f%%, ElecPrice=%.1f" % (target, curtail_pct, elec_price))

except Exception as e:
    safe_write_diag("ERROR", str(e))
    log.error("Manufacturing grid timer failed", e)


