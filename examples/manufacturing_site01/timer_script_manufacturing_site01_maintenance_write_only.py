# Manufacturing Site01 - Maintenance (WRITE-ONLY, NO FUNCTIONS)
# Provider: manufacturing_maintenance
# Paste into: Gateway Timer Scripts / Gateway Events -> Timer (e.g. Fixed Delay ~10000ms)
#
# NOTE: In some Ignition timer-script contexts, `system` and other top-level names
# may not be visible inside `def` functions. This script is intentionally written
# as top-level code only (no defs) for maximum reliability.

import math, random, traceback

log = system.util.getLogger("manufacturing_site01.maintenance_write_only")

BASE = "[manufacturing_maintenance]Manufacturing/Site01"
DIAG = BASE + "/Diagnostics"
CFG = BASE + "/Config"
MA = BASE + "/Maintenance"

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

		# Work order counts fluctuate slowly
		active = 4 + int(abs(2.0 * math.sin(tick / 6.0)))
		high = 1 if (tick % 12) < 3 else 0

		wo_id = "WO-%05d" % (77821 + (tick % 500))
		wo_sum = random.choice([
			"Inspect kiln zone 3 thermocouple drift",
			"Replace press hydraulic seals",
			"Balance blower impeller",
			"Lubricate grinder spindle",
			"Check spray dryer cyclone DP trend",
		])

		# Condition signals (light oscillation)
		tc_drift = 1.5 + 0.8 * abs(math.sin(tick / 10.0))
		blower_vib = 2.1 + 0.6 * abs(math.sin(tick / 9.0))
		pump_vib = 2.4 + 0.7 * abs(math.sin(tick / 8.0))
		spindle_vib = 1.7 + 0.5 * abs(math.sin(tick / 11.0))

		# Spares counts drift occasionally
		seal = 6 - int((tick % 30) == 0)
		tc_stock = 12 - int((tick % 48) == 0)
		bearing = 4 - int((tick % 60) == 0)

		paths = [
			DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError", DIAG + "/TickCount",

			MA + "/WorkOrders/ActiveCount",
			MA + "/WorkOrders/HighPriorityCount",
			MA + "/WorkOrders/LastWorkOrderId",
			MA + "/WorkOrders/LastWorkOrderSummary",

			MA + "/Condition/Kiln01_ThermocoupleDrift_C",
			MA + "/Condition/Kiln01_BlowerVibration_mm_s",
			MA + "/Condition/Press01_PumpVibration_mm_s",
			MA + "/Condition/Grinder01_SpindleVibration_mm_s",

			MA + "/Spares/Press01_SealKit_Stock",
			MA + "/Spares/Kiln01_Thermocouple_Stock",
			MA + "/Spares/Grinder01_Bearing_Stock",
		]

		vals = [
			ts, "OK", "", tick,

			int(active), int(high), str(wo_id), str(wo_sum),

			float(tc_drift), float(blower_vib), float(pump_vib), float(spindle_vib),

			int(max(0, seal)), int(max(0, tc_stock)), int(max(0, bearing)),
		]

		results = system.tag.writeBlocking(paths, vals)
		q = [str(r) for r in results]
		bad = [(paths[i], q[i]) for i in range(len(q)) if q[i] != "Good"]
		if bad:
			log.error("WRITE_FAIL (first 10): %r" % (bad[:10],))
		else:
			log.info(
				"Maint tick ok. ActiveWO=%d, HighPrio=%d, TCDrift=%.2fC, BlowerVib=%.2f"
				% (active, high, tc_drift, blower_vib)
			)

except:
	tb = traceback.format_exc()
	try:
		ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
		system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, "ERROR", tb])
	except:
		pass
	log.error("manufacturing maintenance write-only timer failed:\n%s" % tb)


