# Ignition Gateway Timer Script (Jython) - Pluspetrol SCADA/Process (TOP-LEVEL)
# Provider: pluspetrol
# Writes:   [pluspetrol]Pluspetrol/Argentina/LaCalera/...
# Reads:    [pluspetrol_safety].../Safety/ESD_Active to model shutdown response

import random, math, time

BASE = "[pluspetrol]Pluspetrol/Argentina/LaCalera"
DIAG = BASE + "/Diagnostics"


def now_iso():
	return system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")


def clamp(x, lo, hi):
	return max(lo, min(hi, x))


def read(path):
	return system.tag.readBlocking([path])[0].value


def read_safety(path_suffix):
	return system.tag.readBlocking(["[pluspetrol_safety]Pluspetrol/Argentina/LaCalera/Safety/" + path_suffix])[0].value


def safe_write_diag(status, msg):
	try:
		ts = now_iso()
		system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, status, msg or ""])
		try:
			cur = system.tag.readBlocking([DIAG + "/TickCount"])[0].value
			cur = int(cur or 0)
			system.tag.writeBlocking([DIAG + "/TickCount"], [cur + 1])
		except:
			pass
	except:
		pass


def well_model(choke_pct, enabled, base_liq_m3d, base_gas_kSm3d, tick, noise_seed):
	if not enabled:
		return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
	osc = 1.0 + 0.06 * math.sin(2.0 * math.pi * (tick / 180.0) + noise_seed)
	choke = clamp(choke_pct / 100.0, 0.0, 1.0)
	liq = base_liq_m3d * choke * osc
	gas = base_gas_kSm3d * choke * (0.95 + 0.1 * random.random())
	whp = clamp(140.0 + 45.0 * (1.0 - choke) - 0.08 * liq + random.gauss(0, 0.8), 90.0, 220.0)
	wht = clamp(68.0 + 8.0 * random.random() + 0.01 * whp, 55.0, 95.0)
	sand = clamp(0.8 + 0.05 * liq + 2.2 * (1.0 - choke) + abs(random.gauss(0, 0.3)), 0.0, 18.0)
	vib = clamp(0.9 + 0.01 * liq + abs(random.gauss(0, 0.2)), 0.4, 6.0)
	return (liq, gas, whp, wht, sand, vib)


try:
	safe_write_diag("START", "")

	sim_enabled = bool(read(BASE + "/Config/SimEnabled"))
	if not sim_enabled:
		safe_write_diag("SKIP", "Sim disabled")
	else:
		g = system.util.getGlobals()
		st = g.get("pluspetrol_state")
		if st is None:
			st = {"decline": 1.0, "t0": time.time()}
			g["pluspetrol_state"] = st

		tick = int(read(DIAG + "/TickCount") or 0) + 1

		if tick % 30 == 0:
			st["decline"] = clamp(st["decline"] * (0.9995 + random.random() * 0.0008), 0.85, 1.02)

		res_p = float(read(BASE + "/Config/ReservoirPressure_bar"))

		esd_active = bool(read_safety("ESD_Active"))

		wells = [
			("PadA", "W01", 155.0, 95.0, 0.3),
			("PadA", "W02", 140.0, 88.0, 1.2),
			("PadB", "W11", 165.0, 102.0, 2.0),
		]

		total_liq = 0.0
		total_gas = 0.0
		writes = []

		for (pad, well, base_liq, base_gas, seed) in wells:
			enabled = bool(read("%s/Wells/%s/%s/Enabled" % (BASE, pad, well)))
			choke = float(read("%s/Wells/%s/%s/Choke_pct" % (BASE, pad, well)))
			(liq, gas, whp, wht, sand, vib) = well_model(
				choke_pct=choke,
				enabled=(enabled and (not esd_active)),
				base_liq_m3d=base_liq * st["decline"],
				base_gas_kSm3d=base_gas * st["decline"],
				tick=tick,
				noise_seed=seed,
			)
			total_liq += liq
			total_gas += gas
			writes.extend([
				("%s/Wells/%s/%s/Wellhead/Pressure_bar" % (BASE, pad, well), float(whp)),
				("%s/Wells/%s/%s/Wellhead/Temperature_C" % (BASE, pad, well), float(wht)),
				("%s/Wells/%s/%s/Wellhead/Vibration_mm_s" % (BASE, pad, well), float(vib)),
				("%s/Wells/%s/%s/Production/LiquidRate_m3_d" % (BASE, pad, well), float(liq)),
				("%s/Wells/%s/%s/Production/GasRate_kSm3_d" % (BASE, pad, well), float(gas)),
				("%s/Wells/%s/%s/Production/WaterCut_pct" % (BASE, pad, well), float(clamp(42.0 + random.gauss(0, 0.8), 20.0, 85.0))),
				("%s/Wells/%s/%s/Production/SandRate_kg_h" % (BASE, pad, well), float(sand)),
			])

		sep_p = clamp(28.0 + 0.08 * total_gas + 0.03 * (res_p - 340.0) + random.gauss(0, 0.4), 14.0, 55.0)
		sep_t = clamp(44.0 + 0.02 * total_liq + random.gauss(0, 0.4), 30.0, 70.0)
		outflow = 0.94 * total_liq * (0.8 + 0.2 * random.random())
		level = clamp(float(read(BASE + "/Processing/Separator01/Level_pct")) / 100.0, 0.02, 0.98)
		level = clamp(level + 0.0009 * (total_liq - outflow) + random.gauss(0, 0.002), 0.02, 0.98)
		dp = clamp(0.08 + 0.002 * total_liq + abs(random.gauss(0, 0.01)), 0.02, 0.6)

		heater_in = sep_t - 1.0 + random.gauss(0, 0.3)
		heater_out = clamp(heater_in + 12.0 + 2.5 * random.random(), 45.0, 85.0)
		fuel_gas = clamp(6.0 + 0.03 * total_gas + random.gauss(0, 0.3), 2.0, 20.0)

		comp_running = bool(read(BASE + "/Processing/Compressor01/Running")) and (not esd_active)
		suction = clamp(14.0 + 0.04 * total_gas + random.gauss(0, 0.3), 6.0, 28.0)
		if not comp_running:
			discharge = suction + random.gauss(0, 0.2)
			speed = 0.0
		else:
			discharge = clamp(60.0 + 0.18 * total_gas + random.gauss(0, 0.6), 30.0, 95.0)
			speed = clamp(8400.0 + 12.0 * total_gas + random.gauss(0, 80.0), 7200.0, 11500.0)

		vib_comp = clamp(1.8 + (0.00008 * speed) + abs(random.gauss(0, 0.25)), 0.6, 9.0)
		bearing_t = clamp(52.0 + (0.0016 * speed) + abs(random.gauss(0, 0.8)), 35.0, 105.0)

		header_p = clamp(58.0 + 0.05 * total_liq + random.gauss(0, 0.6), 35.0, 90.0)
		export_flow = clamp((outflow / 24.0) * (0.95 + 0.1 * random.random()), 0.0, 80.0)

		tank01 = clamp(float(read(BASE + "/Tanks/Tank01/Level_pct")) / 100.0, 0.01, 0.99)
		tank02 = clamp(float(read(BASE + "/Tanks/Tank02/Level_pct")) / 100.0, 0.01, 0.99)

		in_tank = total_liq / 24.0
		offtake = 0.0
		if (tick % 300) < 30:
			offtake = 18.0 * (0.6 + 0.4 * random.random())

		tank01 = clamp(tank01 + 0.00055 * (0.55 * in_tank - 0.6 * offtake), 0.01, 0.99)
		tank02 = clamp(tank02 + 0.00055 * (0.45 * in_tank - 0.4 * offtake), 0.01, 0.99)

		flare = clamp(0.2 + 0.02 * max(0.0, discharge - 80.0) + (2.5 if esd_active else 0.0) + abs(random.gauss(0, 0.08)), 0.0, 12.0)
		smoke_assist = (flare > 4.0)

		writes.extend([
			(BASE + "/Processing/Separator01/Pressure_bar", float(sep_p)),
			(BASE + "/Processing/Separator01/Temperature_C", float(sep_t)),
			(BASE + "/Processing/Separator01/Level_pct", float(level * 100.0)),
			(BASE + "/Processing/Separator01/DP_bar", float(dp)),
			(BASE + "/Processing/Heater01/InletTemperature_C", float(heater_in)),
			(BASE + "/Processing/Heater01/OutletTemperature_C", float(heater_out)),
			(BASE + "/Processing/Heater01/FuelGas_kSm3_d", float(fuel_gas)),
			(BASE + "/Processing/Compressor01/Running", bool(comp_running)),
			(BASE + "/Processing/Compressor01/SuctionPressure_bar", float(suction)),
			(BASE + "/Processing/Compressor01/DischargePressure_bar", float(discharge)),
			(BASE + "/Processing/Compressor01/Speed_RPM", float(speed)),
			(BASE + "/Processing/Compressor01/Vibration_mm_s", float(vib_comp)),
			(BASE + "/Processing/Compressor01/BearingTemp_C", float(bearing_t)),
			(BASE + "/Processing/Export/HeaderPressure_bar", float(header_p)),
			(BASE + "/Processing/Export/ExportFlow_m3_h", float(export_flow)),
			(BASE + "/Tanks/Tank01/Level_pct", float(tank01 * 100.0)),
			(BASE + "/Tanks/Tank02/Level_pct", float(tank02 * 100.0)),
			(BASE + "/Flare/FlareRate_kSm3_h", float(flare)),
			(BASE + "/Flare/SmokelessAssist_On", bool(smoke_assist)),
		])

		system.tag.writeBlocking([p for (p, _) in writes], [v for (_, v) in writes])
		safe_write_diag("OK", "wells=%d liq=%.1f gas=%.1f esd=%s" % (len(wells), total_liq, total_gas, esd_active))

except Exception as e:
	safe_write_diag("ERROR", str(e))


