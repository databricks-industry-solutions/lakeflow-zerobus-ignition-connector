# Manufacturing Site01 - MES (WRITE-ONLY, NO FUNCTIONS)
# Provider: manufacturing_mes
# Paste into: Gateway Timer Scripts / Gateway Events -> Timer (e.g. Fixed Delay ~5000ms)
#
# NOTE: In some Ignition timer-script contexts, `system` and other top-level names
# may not be visible inside `def` functions. This script is intentionally written
# as top-level code only (no defs) for maximum reliability.

import math, traceback

log = system.util.getLogger("manufacturing_site01.mes_write_only")

BASE = "[manufacturing_mes]Manufacturing/Site01"
DIAG = BASE + "/Diagnostics"
CFG = BASE + "/Config"
MES = BASE + "/MES"

try:
	ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")

	# SimEnabled (default True)
	try:
		sim_qv = system.tag.readBlocking([CFG + "/SimEnabled"])[0]
		sim_enabled = True if sim_qv.value is None else bool(sim_qv.value)
	except:
		sim_enabled = True

	if not sim_enabled:
		system.tag.writeBlocking(
			[DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"],
			[ts, "SKIP", "SimEnabled=false"],
		)
	else:
		tqv = system.tag.readBlocking([DIAG + "/TickCount"])[0]
		tick = int(tqv.value or 0) + 1

		# Deterministic-ish MES behavior (no reads required)
		downtime = (tick % 60) < 2
		dt_reason = "Changeover" if downtime else ""

		throughput = 0.0 if downtime else (14.0 + 1.0 * math.sin(tick / 6.0))
		scrap = 1.8 + 0.5 * abs(math.sin(tick / 9.0))

		# Counts increase with tick (roughly)
		good = tick * 65
		reject = tick * 2
		wip = int(2000 + 300 * math.sin(tick / 7.0))

		# OEE (toy model)
		avail = 96.0 - (4.0 if downtime else 0.0)
		perf = 94.0 + 2.0 * math.sin(tick / 10.0)
		qual = 98.0 - min(3.0, scrap)
		oee = (avail * perf * qual) / 10000.0

		paths = [
			DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError", DIAG + "/TickCount",

			MES + "/Orders/GoodCount",
			MES + "/Orders/RejectCount",
			MES + "/Orders/WIPCount",
			MES + "/Production/Throughput_parts_per_min",
			MES + "/Production/ScrapRate_pct",
			MES + "/Production/DowntimeActive",
			MES + "/Production/DowntimeReason",

			MES + "/OEE/Availability_pct",
			MES + "/OEE/Performance_pct",
			MES + "/OEE/Quality_pct",
			MES + "/OEE/OEE_pct",
		]

		vals = [
			ts, "OK", "", tick,

			int(good), int(reject), int(wip),
			float(throughput), float(scrap), bool(downtime), str(dt_reason),

			float(avail), float(perf), float(qual), float(oee),
		]

		results = system.tag.writeBlocking(paths, vals)
		q = [str(r) for r in results]
		bad = [(paths[i], q[i]) for i in range(len(q)) if q[i] != "Good"]
		if bad:
			log.error("WRITE_FAIL (first 10): %r" % (bad[:10],))
		else:
			log.info(
				"MES tick ok. Throughput=%.1f/min, Scrap=%.2f%%, OEE=%.2f%%, Downtime=%s, Good=%d"
				% (throughput, scrap, oee, downtime, good)
			)

except:
	tb = traceback.format_exc()
	try:
		ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
	except:
		ts = ""
	try:
		system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, "ERROR", tb])
	except:
		pass
	log.error("manufacturing mes write-only timer failed:\n%s" % tb)


