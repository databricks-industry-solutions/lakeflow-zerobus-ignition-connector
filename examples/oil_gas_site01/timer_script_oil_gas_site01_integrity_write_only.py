# OilGas Site01 - Integrity (WRITE-ONLY, NO FUNCTIONS)
# Provider: oil_gas_integrity
# Paste into: Gateway Timer Scripts / Gateway Events -> Timer (Fixed Delay ~10000ms)
#
# NOTE: In some Ignition timer-script contexts, `system` and other top-level names
# may not be visible inside `def` functions. This script is intentionally written
# as top-level code only (no defs) for maximum reliability.

import math, traceback

log = system.util.getLogger("oil_gas_la_calera.integrity_write_only")

BASE = "[oil_gas_integrity]OilGas/Site01"
DIAG = BASE + "/Diagnostics"
INTEG = BASE + "/Integrity"

try:
	ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")

	# SimEnabled (default True)
	try:
		sim_qv = system.tag.readBlocking([BASE + "/Config/SimEnabled"])[0]
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

		# Corrosion slowly drifts
		corr = 0.12 + 0.03 * abs(math.sin(tick / 30.0))

		# Pigging days since increments slowly, resets every so often
		pig_days = int((tick % 120) / 6)  # ~0..19

		# Leak suspected blips rarely
		leak = (tick % 200) == 0

		paths = [
			DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError", DIAG + "/TickCount",
			INTEG + "/CorrosionRate_mm_per_yr",
			INTEG + "/Pigging_DaysSince",
			INTEG + "/LeakSuspected",
		]
		vals = [ts, "OK", "", tick, float(corr), int(pig_days), bool(leak)]

		results = system.tag.writeBlocking(paths, vals)
		q = [str(r) for r in results]
		bad = [(paths[i], q[i]) for i in range(len(q)) if q[i] != "Good"]

		if bad:
			log.error("WRITE_FAIL (first 10): %r" % (bad[:10],))
		else:
			log.info("Integrity tick ok. Corrosion=%.3f mm/yr, PigDays=%d, Leak=%s" % (corr, pig_days, leak))

except:
	tb = traceback.format_exc()
	try:
		ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
		system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, "ERROR", tb])
	except:
		pass
	log.error("oil_gas integrity write-only timer failed:\n%s" % tb)


