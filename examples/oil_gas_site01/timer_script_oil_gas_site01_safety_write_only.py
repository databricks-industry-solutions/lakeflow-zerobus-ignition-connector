# OilGas Site01 - Safety (WRITE-ONLY, NO FUNCTIONS)
# Provider: oil_gas_safety
# Paste into: Gateway Timer Scripts / Gateway Events -> Timer (Fixed Delay ~2000ms)
#
# NOTE: In some Ignition timer-script contexts, `system` and other top-level names
# may not be visible inside `def` functions. This script is intentionally written
# as top-level code only (no defs) for maximum reliability.

import math, random, traceback

log = system.util.getLogger("oil_gas_la_calera.safety_write_only")

BASE = "[oil_gas_safety]OilGas/Site01"
DIAG = BASE + "/Diagnostics"
SAF = BASE + "/Safety"

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

		# Baseline H2S with occasional small spikes
		h2s = 2.0 + 1.0 * abs(math.sin(tick / 18.0)) + random.gauss(0, 0.2)

		# Fire & gas toggles rarely
		firegas = (tick % 180) < 3

		# ESD drills occasionally
		esd = (tick % 240) < 2

		paths = [
			DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError", DIAG + "/TickCount",
			SAF + "/H2S_ppm",
			SAF + "/FireGas_Alarm",
			SAF + "/ESD_Active",
		]
		vals = [ts, "OK", "", tick, float(max(0.0, h2s)), bool(firegas), bool(esd)]

		results = system.tag.writeBlocking(paths, vals)
		q = [str(r) for r in results]
		bad = [(paths[i], q[i]) for i in range(len(q)) if q[i] != "Good"]

		if bad:
			log.error("WRITE_FAIL (first 10): %r" % (bad[:10],))
		elif (tick % 10) == 0:
			log.info("Safety tick ok. ESD=%s, FG=%s, H2S=%.1f ppm" % (esd, firegas, h2s))

except:
	tb = traceback.format_exc()
	try:
		ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
		system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, "ERROR", tb])
	except:
		pass
	log.error("oil_gas safety write-only timer failed:\n%s" % tb)


