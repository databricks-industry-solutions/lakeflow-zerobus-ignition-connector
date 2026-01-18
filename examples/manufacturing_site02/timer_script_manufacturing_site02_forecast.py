# Ignition Gateway Timer Script (Jython) - Manufacturing Forecast (TOP-LEVEL)
# Provider: manufacturing_forecast
# Writes:   [manufacturing_forecast]Manufacturing/Site02/Forecast/H01/...
# Reads:    [manufacturing] KPIs + [manufacturing_grid] constraints

import random

FORE = "[manufacturing_forecast]Manufacturing/Site02/Forecast/H01"
DIAG = "[manufacturing_forecast]Manufacturing/Site02/Diagnostics"

Manufacturing = "[manufacturing]Manufacturing/Site02"
GRID = "[manufacturing_grid]Manufacturing/Site02"

log = system.util.getLogger("manufacturing_site02.forecast")

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

    now = system.date.now()

    v = system.tag.readBlocking([
        Manufacturing + "/KPIs/Throughput_units_per_min",
        Manufacturing + "/KPIs/ScrapRate_pct",
        Manufacturing + "/CuttingStation/Quality_Score",
        GRID + "/Dispatch/ConstraintActive",
        GRID + "/Dispatch/Curtailment_pct"
    ])

    thr = float(v[0].value or 0.0)
    scrap = float(v[1].value or 1.5)
    qual = float(v[2].value or 97.0)
    constraint = bool(v[3].value or False)
    curtail = float(v[4].value or 0.0)

    # Next-hour forecast: persistence + uncertainty
    thr_f = clamp(thr + random.gauss(0, 4.0) - (5.0 if constraint else 0.0), 0.0, 220.0)
    scrap_f = clamp(scrap + random.gauss(0, 0.25) + (0.4 if constraint else -0.05), 0.1, 25.0)

    conf = 80.0 - (10.0 if constraint else 0.0) - abs(random.gauss(0, 1.0)) * 8.0
    conf = clamp(conf, 35.0, 95.0)

    asof = system.date.format(now, "yyyy-MM-dd HH:mm:ss")
    system.tag.writeBlocking(
        [FORE + "/AsOfTime", FORE + "/Throughput_units_per_min", FORE + "/ScrapRate_pct", FORE + "/Confidence_pct"],
        [asof, thr_f, scrap_f, conf]
    )

    safe_write_diag("OK", "")
    log.info("Manufacturing forecast updated: thr=%.1f, scrap=%.2f%%, conf=%.0f%%, qual=%.1f, curtail=%.1f%%" % (thr_f, scrap_f, conf, qual, curtail))

except Exception as e:
    safe_write_diag("ERROR", str(e))
    log.error("Manufacturing forecast timer failed", e)



