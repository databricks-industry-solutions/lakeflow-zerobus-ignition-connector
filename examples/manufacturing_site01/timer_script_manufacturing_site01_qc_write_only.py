# Manufacturing Site01 - QC (WRITE-ONLY, NO FUNCTIONS)
# Provider: manufacturing_qc
# Paste into: Gateway Timer Scripts / Gateway Events -> Timer (e.g. Fixed Delay ~2000ms)
#
# NOTE: In some Ignition timer-script contexts, `system` and other top-level names
# may not be visible inside `def` functions. This script is intentionally written
# as top-level code only (no defs) for maximum reliability.

import math, random, traceback

log = system.util.getLogger("manufacturing_site01.qc_write_only")

BASE = "[manufacturing_qc]Manufacturing/Site01"
DIAG = BASE + "/Diagnostics"
CFG = BASE + "/Config"
QC = BASE + "/QC"

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

		# Vision (yield + defects)
		yield_pct = 98.0 + 0.4 * math.sin(tick / 15.0) + random.gauss(0, 0.05)
		defects = 6.0 + 1.2 * math.sin(tick / 18.0) + abs(random.gauss(0, 0.25))

		top_defect = "None"
		if defects > 7.5:
			top_defect = random.choice(["Chips", "Cracks", "Warp", "Inclusions", "Surface pits"])

		# Lab (slow drift)
		density = 3.84 + 0.03 * math.sin(tick / 80.0)
		porosity = 1.2 + 0.25 * abs(math.sin(tick / 70.0))
		hard = 1450.0 + 18.0 * math.sin(tick / 60.0)
		flex = 360.0 + 10.0 * math.sin(tick / 55.0)

		# SPC
		mean = 10.001 + 0.004 * math.sin(tick / 30.0)
		sigma = 0.006 + 0.0012 * abs(math.sin(tick / 40.0))
		cpk = 1.55 - 0.15 * abs(math.sin(tick / 45.0))
		ooc = (tick % 240) < 6
		ooc_reason = "SPC rule violation (trend)" if ooc else ""

		paths = [
			DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError", DIAG + "/TickCount",

			QC + "/Inspection/Vision01/Yield_pct",
			QC + "/Inspection/Vision01/Defects_per_1000",
			QC + "/Inspection/Vision01/TopDefect",

			QC + "/Lab/Density_g_cm3",
			QC + "/Lab/Porosity_pct",
			QC + "/Lab/Hardness_HV",
			QC + "/Lab/FlexuralStrength_MPa",

			QC + "/SPC/Diameter_mean_mm",
			QC + "/SPC/Diameter_sigma_mm",
			QC + "/SPC/Diameter_Cpk",
			QC + "/SPC/OutOfControl",
			QC + "/SPC/LastOOCReason",
		]

		vals = [
			ts, "OK", "", tick,

			float(yield_pct), float(defects), str(top_defect),

			float(density), float(porosity), float(hard), float(flex),

			float(mean), float(sigma), float(cpk), bool(ooc), str(ooc_reason),
		]

		results = system.tag.writeBlocking(paths, vals)
		q = [str(r) for r in results]
		bad = [(paths[i], q[i]) for i in range(len(q)) if q[i] != "Good"]
		if bad:
			log.error("WRITE_FAIL (first 10): %r" % (bad[:10],))
		elif (tick % 10) == 0:
			log.info(
				"QC tick ok. Yield=%.2f%%, Defects/1000=%.2f, Cpk=%.2f, TopDefect=%s"
				% (yield_pct, defects, cpk, top_defect)
			)

except:
	tb = traceback.format_exc()
	try:
		ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
		system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, "ERROR", tb])
	except:
		pass
	log.error("manufacturing qc write-only timer failed:\n%s" % tb)


