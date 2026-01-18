# OilGas Site01 - Process/SCADA (WRITE-ONLY, NO FUNCTIONS)
# Provider: oil_gas
# Paste into: Gateway Timer Scripts / Gateway Events -> Timer (Fixed Delay ~1000ms)
#
# NOTE: In some Ignition timer-script contexts, `system` and other top-level names
# may not be visible inside `def` functions. This script is intentionally written
# as top-level code only (no defs) for maximum reliability.

import math, random, traceback

log = system.util.getLogger("oil_gas_la_calera.process_write_only")

BASE = "[oil_gas]OilGas/Site01"
DIAG = BASE + "/Diagnostics"

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

		# --- Wells (simple deterministic oscillations) ---
		wells = [
			("PadA", "W01", 155.0, 95.0, 0.30),
			("PadA", "W02", 140.0, 88.0, 1.20),
			("PadB", "W11", 165.0, 102.0, 2.00),
		]

		writes = []
		total_liq = 0.0
		total_gas = 0.0

		for (pad, well, base_liq, base_gas, phase) in wells:
			choke = 0.60 + 0.06 * math.sin((tick / 25.0) + phase)
			choke_pct = max(0.0, min(100.0, choke * 100.0))

			liq = base_liq * choke * (1.0 + 0.05 * math.sin((tick / 18.0) + phase))
			gas = base_gas * choke * (0.98 + 0.04 * math.sin((tick / 21.0) + phase))
			whp = 150.0 + 22.0 * (1.0 - choke) + 2.0 * math.sin((tick / 14.0) + phase)
			wht = 70.0 + 2.5 * math.sin((tick / 17.0) + phase)
			vib = 1.1 + 0.25 * abs(math.sin((tick / 9.0) + phase))
			wc = 42.0 + 2.0 * math.sin((tick / 60.0) + phase)
			sand = 3.0 + 0.8 * abs(math.sin((tick / 40.0) + phase))

			total_liq += liq
			total_gas += gas

			prefix = "%s/Wells/%s/%s" % (BASE, pad, well)
			writes.extend([
				(prefix + "/Enabled", True),
				(prefix + "/Choke_pct", float(choke_pct)),

				(prefix + "/Wellhead/Pressure_bar", float(whp)),
				(prefix + "/Wellhead/Temperature_C", float(wht)),
				(prefix + "/Wellhead/Vibration_mm_s", float(vib)),

				(prefix + "/Production/LiquidRate_m3_d", float(liq)),
				(prefix + "/Production/GasRate_kSm3_d", float(gas)),
				(prefix + "/Production/WaterCut_pct", float(wc)),
				(prefix + "/Production/SandRate_kg_h", float(sand)),
			])

		# --- Processing ---
		sep_p = 28.0 + 0.06 * total_gas + 0.02 * math.sin(tick / 20.0)
		sep_t = 44.0 + 0.02 * total_liq + 0.3 * math.sin(tick / 25.0)
		sep_level = 52.0 + 3.0 * math.sin(tick / 30.0)
		sep_dp = 0.12 + 0.02 * abs(math.sin(tick / 18.0))

		heater_in = sep_t - 1.0 + 0.2 * math.sin(tick / 16.0)
		heater_out = heater_in + 12.0 + 0.8 * math.sin(tick / 22.0)
		fuel_gas = 8.0 + 0.02 * total_gas + 0.3 * abs(math.sin(tick / 20.0))

		comp_running = True
		suction = 18.0 + 0.8 * math.sin(tick / 22.0)
		discharge = 72.0 + 3.0 * math.sin(tick / 18.0)
		speed = 8900.0 + 220.0 * math.sin(tick / 12.0)
		comp_vib = 2.2 + 0.5 * abs(math.sin(tick / 10.0))
		bearing_t = 68.0 + 2.5 * abs(math.sin(tick / 14.0))

		header_p = 64.0 + 1.5 * math.sin(tick / 25.0)
		export_flow = 24.0 + 2.0 * math.sin(tick / 20.0)

		writes.extend([
			(BASE + "/Processing/Separator01/Pressure_bar", float(sep_p)),
			(BASE + "/Processing/Separator01/Temperature_C", float(sep_t)),
			(BASE + "/Processing/Separator01/Level_pct", float(sep_level)),
			(BASE + "/Processing/Separator01/DP_bar", float(sep_dp)),

			(BASE + "/Processing/Heater01/InletTemperature_C", float(heater_in)),
			(BASE + "/Processing/Heater01/OutletTemperature_C", float(heater_out)),
			(BASE + "/Processing/Heater01/FuelGas_kSm3_d", float(fuel_gas)),

			(BASE + "/Processing/Compressor01/Running", bool(comp_running)),
			(BASE + "/Processing/Compressor01/SuctionPressure_bar", float(suction)),
			(BASE + "/Processing/Compressor01/DischargePressure_bar", float(discharge)),
			(BASE + "/Processing/Compressor01/Speed_RPM", float(speed)),
			(BASE + "/Processing/Compressor01/Vibration_mm_s", float(comp_vib)),
			(BASE + "/Processing/Compressor01/BearingTemp_C", float(bearing_t)),

			(BASE + "/Processing/Export/HeaderPressure_bar", float(header_p)),
			(BASE + "/Processing/Export/ExportFlow_m3_h", float(export_flow)),
		])

		# --- Tanks + Flare ---
		t1_lvl = 35.0 + 2.0 * math.sin(tick / 45.0)
		t2_lvl = 22.0 + 1.6 * math.sin(tick / 50.0)
		t1_t = 28.0 + 0.6 * math.sin(tick / 60.0)
		t2_t = 27.0 + 0.6 * math.sin(tick / 65.0)
		t1_wb = 6.0 + 0.4 * abs(math.sin(tick / 70.0))
		t2_wb = 8.0 + 0.4 * abs(math.sin(tick / 75.0))

		flare = 0.3 + 0.2 * abs(math.sin(tick / 30.0))
		smoke = (flare > 0.6)

		writes.extend([
			(BASE + "/Tanks/Tank01/Level_pct", float(t1_lvl)),
			(BASE + "/Tanks/Tank01/Temperature_C", float(t1_t)),
			(BASE + "/Tanks/Tank01/WaterBottom_pct", float(t1_wb)),
			(BASE + "/Tanks/Tank02/Level_pct", float(t2_lvl)),
			(BASE + "/Tanks/Tank02/Temperature_C", float(t2_t)),
			(BASE + "/Tanks/Tank02/WaterBottom_pct", float(t2_wb)),

			(BASE + "/Flare/PilotLit", True),
			(BASE + "/Flare/FlareRate_kSm3_h", float(flare)),
			(BASE + "/Flare/SmokelessAssist_On", bool(smoke)),
		])

		# --- Write (single batch) ---
		paths = [p for (p, _) in writes]
		vals = [v for (_, v) in writes]

		# Prepend diagnostics updates
		paths = [DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError", DIAG + "/TickCount"] + paths
		vals = [ts, "OK", "", tick] + vals

		results = system.tag.writeBlocking(paths, vals)
		q = [str(r) for r in results]
		bad = [(paths[i], q[i]) for i in range(len(q)) if q[i] != "Good"]

		if bad:
			log.error("WRITE_FAIL (first 10): %r" % (bad[:10],))
		elif (tick % 10) == 0:
			log.info(
				"Process tick ok. liq=%.1f m3/d, gas=%.1f kSm3/d, SepLvl=%.1f%%, Disch=%.1f bar, Flare=%.2f"
				% (total_liq, total_gas, sep_level, discharge, flare)
			)

except:
	tb = traceback.format_exc()
	try:
		ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
		system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, "ERROR", tb])
	except:
		pass
	log.error("oil_gas process write-only timer failed:\n%s" % tb)


