def handleTimerEvent():
	"""
	Ignition Gateway Timer Script (Jython) — Ignition 8.1 compatible
	CoorsTek demo: Process / SCADA signals (mixing → spray dryer → pressing → kiln → grinding)

	Recommended timer delay: 1000ms (Fixed Delay)
	Tag provider must be named: coorstek
	"""

	import random
	import math
	import time

	BASE = "[coorstek]CoorsTek/Site01"

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

	def st():
		g = system.util.getGlobals()
		if "coorstek_process_state" not in g:
			g["coorstek_process_state"] = {
				"t0": time.time(),
				"kiln_bias3": 0.0,
				"dryer_fouling": 0.0,
				"tool_wear": 0.15,
				"last_alarm": "",
			}
		return g["coorstek_process_state"]

	try:
		if not bool(read(BASE + "/Config/SimEnabled")):
			write([
				(BASE + "/Diagnostics/LastRun", now_iso()),
				(BASE + "/Diagnostics/LastStatus", "Sim disabled"),
				(BASE + "/Diagnostics/LastError", "")
			])
			return

		s = st()

		tick = int(read(BASE + "/Diagnostics/TickCount")) + 1

		# --- Raw materials slowly deplete/replenish ---
		al_lvl = float(read(BASE + "/RawMaterials/AluminaHopper_Level_pct"))
		bi_lvl = float(read(BASE + "/RawMaterials/BinderTank_Level_pct"))
		di_lvl = float(read(BASE + "/RawMaterials/DispersantTank_Level_pct"))

		# consumption per tick with occasional replenishment
		al_lvl = clamp(al_lvl - 0.004 + random.gauss(0, 0.002), 15.0, 95.0)
		bi_lvl = clamp(bi_lvl - 0.003 + random.gauss(0, 0.002), 10.0, 90.0)
		di_lvl = clamp(di_lvl - 0.0015 + random.gauss(0, 0.001), 10.0, 90.0)
		if tick % 1800 == 0:  # periodic top-up
			al_lvl = clamp(al_lvl + 18.0, 0.0, 100.0)
		if tick % 2400 == 0:
			bi_lvl = clamp(bi_lvl + 12.0, 0.0, 100.0)

		# --- Mixing: viscosity depends on solids%, temperature, and small drift ---
		solids = float(read(BASE + "/Mixing/SlurryTank01/Solids_pct"))
		visc = float(read(BASE + "/Mixing/SlurryTank01/Viscosity_cP"))
		ph = float(read(BASE + "/Mixing/SlurryTank01/pH"))
		temp = float(read(BASE + "/Mixing/SlurryTank01/Temperature_C"))
		agit = float(read(BASE + "/Mixing/SlurryTank01/Agitator_RPM"))

		solids = clamp(solids + random.gauss(0, 0.05), 58.0, 66.0)
		temp = clamp(temp + random.gauss(0, 0.08), 24.0, 33.0)
		ph = clamp(ph + random.gauss(0, 0.01), 8.7, 9.6)
		agit = clamp(agit + random.gauss(0, 2.0), 180.0, 320.0)

		# viscosity rises with solids and drops with temperature
		target_visc = 650.0 + 55.0 * (solids - 60.0) - 8.0 * (temp - 28.0)
		visc = clamp(0.88 * visc + 0.12 * (target_visc + random.gauss(0, 18.0)), 520.0, 1150.0)

		# --- Spray dryer: outlet temp and moisture drift with fouling ---
		inlet = float(read(BASE + "/SprayDryer01/InletTemp_C"))
		outlet = float(read(BASE + "/SprayDryer01/OutletTemp_C"))
		atom = float(read(BASE + "/SprayDryer01/Atomizer_RPM"))
		moist = float(read(BASE + "/SprayDryer01/PowderMoisture_pct"))
		dp = float(read(BASE + "/SprayDryer01/CycloneDP_kPa"))

		# fouling grows slowly, resets on "clean"
		s["dryer_fouling"] = clamp(s["dryer_fouling"] + 0.0004 + abs(random.gauss(0, 0.0003)), 0.0, 1.0)
		if tick % 3600 == 0:  # scheduled clean
			s["dryer_fouling"] = clamp(s["dryer_fouling"] - 0.6, 0.0, 1.0)

		inlet = clamp(210.0 + random.gauss(0, 1.2), 195.0, 230.0)
		atom = clamp(12500.0 + random.gauss(0, 120.0), 11800.0, 13200.0)
		outlet = clamp(92.0 + 6.0 * s["dryer_fouling"] + random.gauss(0, 0.8), 80.0, 112.0)
		moist = clamp(0.70 + 0.25 * s["dryer_fouling"] + 0.00025 * (visc - 800.0) + abs(random.gauss(0, 0.03)), 0.4, 2.0)
		dp = clamp(2.1 + 1.8 * s["dryer_fouling"] + abs(random.gauss(0, 0.05)), 1.2, 6.5)

		# --- Pressing: rate depends on powder moisture ---
		press_run = bool(read(BASE + "/Pressing/Press01/Running"))
		press_force = float(read(BASE + "/Pressing/Press01/PressForce_kN"))
		cycle = float(read(BASE + "/Pressing/Press01/CycleTime_s"))
		rate = float(read(BASE + "/Pressing/Press01/PartRate_parts_per_min"))
		hyd = float(read(BASE + "/Pressing/Press01/HydraulicPressure_bar"))
		die_t = float(read(BASE + "/Pressing/Press01/DieTemp_C"))
		alarm = bool(read(BASE + "/Pressing/Press01/AlarmActive"))
		last_alarm = str(read(BASE + "/Pressing/Press01/LastAlarm") or "")

		# occasional short press stops (die jam)
		if press_run and random.random() < 0.002:
			press_run = False
			s["press_restart_at"] = time.time() + random.randint(10, 25)
			alarm = True
			last_alarm = "Die jam / ejection fault"
		if (not press_run) and ("press_restart_at" in s) and (time.time() >= s["press_restart_at"]):
			press_run = True
			alarm = False
			last_alarm = ""

		press_force = clamp(1180.0 + random.gauss(0, 18.0), 1050.0, 1400.0)
		hyd = clamp(165.0 + random.gauss(0, 2.5), 150.0, 190.0)
		die_t = clamp(42.0 + random.gauss(0, 0.3), 38.0, 50.0)

		# moisture too high slows cycle and reduces rate
		cycle = clamp(4.1 + 0.8 * max(0.0, moist - 0.9) + abs(random.gauss(0, 0.05)), 3.8, 6.5)
		rate = 60.0 / cycle if press_run else 0.0
		rate = clamp(rate + random.gauss(0, 0.4), 0.0, 18.0)

		# --- Kiln: zones track targets, with occasional zone3 drift event ---
		z1_tgt = float(read(BASE + "/Config/KilnProfile_TargetZone1_C"))
		z2_tgt = float(read(BASE + "/Config/KilnProfile_TargetZone2_C"))
		z3_tgt = float(read(BASE + "/Config/KilnProfile_TargetZone3_C"))

		z1 = float(read(BASE + "/Kiln01/Zones/Zone1_Temp_C"))
		z2 = float(read(BASE + "/Kiln01/Zones/Zone2_Temp_C"))
		z3 = float(read(BASE + "/Kiln01/Zones/Zone3_Temp_C"))

		# rare thermocouple drift drives a slow bias on zone3
		if random.random() < 0.0008:
			s["kiln_bias3"] = clamp(s["kiln_bias3"] + random.choice([-1.0, 1.0]) * (0.8 + 0.6 * random.random()), -18.0, 18.0)
		# slow recovery
		s["kiln_bias3"] *= 0.9996

		z1 = clamp(0.96 * z1 + 0.04 * (z1_tgt + random.gauss(0, 2.0)), z1_tgt - 25.0, z1_tgt + 25.0)
		z2 = clamp(0.96 * z2 + 0.04 * (z2_tgt + random.gauss(0, 3.0)), z2_tgt - 35.0, z2_tgt + 35.0)
		z3 = clamp(0.96 * z3 + 0.04 * (z3_tgt + s["kiln_bias3"] + random.gauss(0, 4.0)), z3_tgt - 60.0, z3_tgt + 60.0)

		belt = float(read(BASE + "/Kiln01/BeltSpeed_mm_s"))
		o2 = float(read(BASE + "/Kiln01/Atmosphere_O2_pct"))
		dew = float(read(BASE + "/Kiln01/Dewpoint_C"))
		exh = float(read(BASE + "/Kiln01/ExhaustTemp_C"))

		belt = clamp(belt + random.gauss(0, 0.05), 14.0, 26.0)
		o2 = clamp(1.8 + random.gauss(0, 0.12) + 0.001 * max(0.0, s["kiln_bias3"]), 0.6, 4.0)
		dew = clamp(-18.0 + random.gauss(0, 0.8) + 0.02 * max(0.0, s["kiln_bias3"]), -35.0, 5.0)
		exh = clamp(255.0 + 0.04 * (z3 - z3_tgt) + random.gauss(0, 1.0), 220.0, 320.0)

		# --- Grinding: tool wear increases with time and with press/kiln disturbances ---
		tool = float(read(BASE + "/Grinding/Grinder01/ToolWear_Index"))
		tool = clamp(tool + 0.00002 + abs(random.gauss(0, 0.00003)) + 0.00001 * max(0.0, moist - 0.9), 0.05, 0.95)
		if tick % 7200 == 0:  # tool change
			tool = clamp(tool - 0.35, 0.05, 0.95)

		spindle_a = clamp(18.0 + 18.0 * tool + random.gauss(0, 0.9), 10.0, 55.0)
		feed = clamp(6.8 - 2.6 * tool + random.gauss(0, 0.2), 2.2, 8.0)
		cool = clamp(18.0 + random.gauss(0, 0.4), 12.0, 26.0)

		# Narrative status
		kiln_dev3 = z3 - z3_tgt
		status = "OK"
		if abs(kiln_dev3) > 20.0:
			status = "Kiln Zone3 deviation %.1fC" % kiln_dev3
		elif moist > 1.2:
			status = "Powder moisture high (%.2f%%)" % moist
		elif press_run is False:
			status = "Press stopped"

		write([
			(BASE + "/RawMaterials/AluminaHopper_Level_pct", float(al_lvl)),
			(BASE + "/RawMaterials/BinderTank_Level_pct", float(bi_lvl)),
			(BASE + "/RawMaterials/DispersantTank_Level_pct", float(di_lvl)),

			(BASE + "/Mixing/SlurryTank01/Solids_pct", float(solids)),
			(BASE + "/Mixing/SlurryTank01/Viscosity_cP", float(visc)),
			(BASE + "/Mixing/SlurryTank01/pH", float(ph)),
			(BASE + "/Mixing/SlurryTank01/Temperature_C", float(temp)),
			(BASE + "/Mixing/SlurryTank01/Agitator_RPM", float(agit)),

			(BASE + "/SprayDryer01/InletTemp_C", float(inlet)),
			(BASE + "/SprayDryer01/OutletTemp_C", float(outlet)),
			(BASE + "/SprayDryer01/Atomizer_RPM", float(atom)),
			(BASE + "/SprayDryer01/PowderMoisture_pct", float(moist)),
			(BASE + "/SprayDryer01/CycloneDP_kPa", float(dp)),

			(BASE + "/Pressing/Press01/Running", bool(press_run)),
			(BASE + "/Pressing/Press01/PressForce_kN", float(press_force)),
			(BASE + "/Pressing/Press01/CycleTime_s", float(cycle)),
			(BASE + "/Pressing/Press01/PartRate_parts_per_min", float(rate)),
			(BASE + "/Pressing/Press01/HydraulicPressure_bar", float(hyd)),
			(BASE + "/Pressing/Press01/DieTemp_C", float(die_t)),
			(BASE + "/Pressing/Press01/AlarmActive", bool(alarm)),
			(BASE + "/Pressing/Press01/LastAlarm", str(last_alarm)),

			(BASE + "/Kiln01/Zones/Zone1_Temp_C", float(z1)),
			(BASE + "/Kiln01/Zones/Zone2_Temp_C", float(z2)),
			(BASE + "/Kiln01/Zones/Zone3_Temp_C", float(z3)),
			(BASE + "/Kiln01/BeltSpeed_mm_s", float(belt)),
			(BASE + "/Kiln01/Atmosphere_O2_pct", float(o2)),
			(BASE + "/Kiln01/Dewpoint_C", float(dew)),
			(BASE + "/Kiln01/ExhaustTemp_C", float(exh)),

			(BASE + "/Grinding/Grinder01/SpindleCurrent_A", float(spindle_a)),
			(BASE + "/Grinding/Grinder01/FeedRate_mm_s", float(feed)),
			(BASE + "/Grinding/Grinder01/CoolantFlow_L_min", float(cool)),
			(BASE + "/Grinding/Grinder01/ToolWear_Index", float(tool)),

			(BASE + "/Diagnostics/TickCount", int(tick)),
			(BASE + "/Diagnostics/LastRun", now_iso()),
			(BASE + "/Diagnostics/LastStatus", status),
			(BASE + "/Diagnostics/LastError", "")
		])

	except Exception as e:
		try:
			write([
				(BASE + "/Diagnostics/LastRun", now_iso()),
				(BASE + "/Diagnostics/LastStatus", "ERROR"),
				(BASE + "/Diagnostics/LastError", repr(e))
			])
		except:
			pass


handleTimerEvent()


