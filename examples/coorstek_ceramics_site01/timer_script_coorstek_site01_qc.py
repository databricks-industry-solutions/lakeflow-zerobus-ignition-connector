def handleTimerEvent():
	"""
	Ignition Gateway Timer Script (Jython) — Ignition 8.1 compatible
	CoorsTek demo: Quality / SPC signals

	Recommended timer delay: 2000ms (Fixed Delay)
	Tag provider must be named: coorstek_qc

	Reads a few upstream process tags from provider `coorstek` to create realistic coupling
	(kiln deviation, powder moisture, press alarms → yield/defects/SPC).
	"""

	import random
	import math

	BASE_Q = "[coorstek_qc]CoorsTek/Site01"
	BASE_P = "[coorstek]CoorsTek/Site01"

	def now_iso():
		return system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")

	def clamp(x, lo, hi):
		return max(lo, min(hi, x))

	def read(path):
		return system.tag.readBlocking([path])[0].value

	def write(pairs):
		paths = [p for (p, _) in pairs]
		vals = [v for (_, v) in pairs]
		system.tag.writeBlocking(paths, vals)

	try:
		if not bool(read(BASE_Q + "/Config/SimEnabled")):
			write([
				(BASE_Q + "/Diagnostics/LastRun", now_iso()),
				(BASE_Q + "/Diagnostics/LastStatus", "Sim disabled"),
				(BASE_Q + "/Diagnostics/LastError", "")
			])
			return

		tick = int(read(BASE_Q + "/Diagnostics/TickCount")) + 1

		# Pull a few process drivers
		z3 = float(read(BASE_P + "/Kiln01/Zones/Zone3_Temp_C"))
		z3_tgt = float(read(BASE_P + "/Config/KilnProfile_TargetZone3_C"))
		moist = float(read(BASE_P + "/SprayDryer01/PowderMoisture_pct"))
		press_alarm = bool(read(BASE_P + "/Pressing/Press01/AlarmActive"))
		tool = float(read(BASE_P + "/Grinding/Grinder01/ToolWear_Index"))

		kiln_dev = z3 - z3_tgt

		# Yield model: best when kiln is on profile and powder moisture is in band.
		yield_base = 98.6
		yield_penalty = 0.02 * abs(kiln_dev) + 8.0 * max(0.0, moist - 1.0) + (0.8 if press_alarm else 0.0) + 0.8 * max(0.0, tool - 0.55)
		yield_pct = clamp(yield_base - yield_penalty + random.gauss(0, 0.15), 80.0, 99.8)

		defects_per_1000 = clamp(2.0 + 2.5 * (100.0 - yield_pct) + abs(random.gauss(0, 0.8)), 0.0, 250.0)

		top_defect = "None"
		if abs(kiln_dev) > 25.0:
			top_defect = "Warp/crack (sinter profile)"
		elif moist > 1.2:
			top_defect = "Lamination (moisture)"
		elif press_alarm:
			top_defect = "Chipping (press handling)"
		elif tool > 0.7:
			top_defect = "Surface finish (tool wear)"

		# Lab signals (density/porosity correlate with kiln profile)
		target_rho = float(read(BASE_Q + "/Config/Target_Density_g_cm3"))
		rho = clamp(target_rho - 0.0009 * abs(kiln_dev) - 0.006 * max(0.0, moist - 1.0) + random.gauss(0, 0.004), target_rho - 0.08, target_rho + 0.03)
		por = clamp(1.1 + 0.015 * abs(kiln_dev) + 0.4 * max(0.0, moist - 1.0) + abs(random.gauss(0, 0.05)), 0.3, 6.0)
		hard = clamp(1450.0 - 2.0 * abs(kiln_dev) + random.gauss(0, 8.0), 1200.0, 1600.0)
		flex = clamp(360.0 - 0.8 * abs(kiln_dev) - 8.0 * max(0.0, moist - 1.0) + random.gauss(0, 3.0), 250.0, 420.0)

		# SPC on diameter: moisture + press stability drives sigma; kiln drift nudges mean
		target_d = float(read(BASE_Q + "/Config/Target_Diameter_mm"))
		sigma = clamp(0.004 + 0.006 * max(0.0, moist - 0.9) + (0.003 if press_alarm else 0.0) + 0.001 * max(0.0, tool - 0.6), 0.003, 0.03)
		mean = clamp(target_d + 0.00003 * kiln_dev + random.gauss(0, sigma / 2.5), target_d - 0.03, target_d + 0.03)

		# Compute a simple Cpk proxy for +/-0.03mm tolerance
		tol = 0.03
		cpk = 0.0
		try:
			cpk = min((tol - abs(mean - target_d)) / (3.0 * max(0.0005, sigma)), 2.5)
		except:
			cpk = 0.0
		cpk = clamp(cpk, 0.0, 2.5)

		out_of_control = (cpk < 1.0) or (abs(kiln_dev) > 35.0)
		ooc_reason = ""
		if out_of_control:
			ooc_reason = "Low Cpk" if (cpk < 1.0) else "Kiln deviation"

		write([
			(BASE_Q + "/QC/Inspection/Vision01/Yield_pct", float(yield_pct)),
			(BASE_Q + "/QC/Inspection/Vision01/Defects_per_1000", float(defects_per_1000)),
			(BASE_Q + "/QC/Inspection/Vision01/TopDefect", str(top_defect)),

			(BASE_Q + "/QC/Lab/Density_g_cm3", float(rho)),
			(BASE_Q + "/QC/Lab/Porosity_pct", float(por)),
			(BASE_Q + "/QC/Lab/Hardness_HV", float(hard)),
			(BASE_Q + "/QC/Lab/FlexuralStrength_MPa", float(flex)),

			(BASE_Q + "/QC/SPC/Diameter_mean_mm", float(mean)),
			(BASE_Q + "/QC/SPC/Diameter_sigma_mm", float(sigma)),
			(BASE_Q + "/QC/SPC/Diameter_Cpk", float(cpk)),
			(BASE_Q + "/QC/SPC/OutOfControl", bool(out_of_control)),
			(BASE_Q + "/QC/SPC/LastOOCReason", str(ooc_reason)),

			(BASE_Q + "/Diagnostics/TickCount", int(tick)),
			(BASE_Q + "/Diagnostics/LastRun", now_iso()),
			(BASE_Q + "/Diagnostics/LastStatus", "Yield=%.2f%%, Cpk=%.2f, kilnDev=%.1fC" % (yield_pct, cpk, kiln_dev)),
			(BASE_Q + "/Diagnostics/LastError", "")
		])

	except Exception as e:
		try:
			write([
				(BASE_Q + "/Diagnostics/LastRun", now_iso()),
				(BASE_Q + "/Diagnostics/LastStatus", "ERROR"),
				(BASE_Q + "/Diagnostics/LastError", repr(e))
			])
		except:
			pass


handleTimerEvent()


