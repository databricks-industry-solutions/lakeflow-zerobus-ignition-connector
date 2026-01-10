# Ignition Gateway Timer Script (Jython) - CoorsTek Process/SCADA (TOP-LEVEL)
# Provider: coorstek
# Writes:   [coorstek]CoorsTek/Site01/...

import random, math, time

BASE = "[coorstek]CoorsTek/Site01"
DIAG = BASE + "/Diagnostics"


def now_iso():
	return system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")


def clamp(x, lo, hi):
	return max(lo, min(hi, x))


def read(path):
	return system.tag.readBlocking([path])[0].value


def write_pairs(pairs):
	system.tag.writeBlocking([p for (p, _) in pairs], [v for (_, v) in pairs])


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


try:
	safe_write_diag("START", "")

	if not bool(read(BASE + "/Config/SimEnabled")):
		safe_write_diag("SKIP", "Sim disabled")
	else:
		g = system.util.getGlobals()
		st = g.get("coorstek_process_state")
		if st is None:
			st = {
				"t0": time.time(),
				"kiln_bias3": 0.0,
				"dryer_fouling": 0.0,
				"press_restart_at": 0.0,
			}
			g["coorstek_process_state"] = st

		tick = int(read(DIAG + "/TickCount") or 0) + 1

		# --- Raw materials slowly deplete/replenish ---
		al_lvl = float(read(BASE + "/RawMaterials/AluminaHopper_Level_pct"))
		bi_lvl = float(read(BASE + "/RawMaterials/BinderTank_Level_pct"))
		di_lvl = float(read(BASE + "/RawMaterials/DispersantTank_Level_pct"))

		al_lvl = clamp(al_lvl - 0.004 + random.gauss(0, 0.002), 15.0, 95.0)
		bi_lvl = clamp(bi_lvl - 0.003 + random.gauss(0, 0.002), 10.0, 90.0)
		di_lvl = clamp(di_lvl - 0.0015 + random.gauss(0, 0.001), 10.0, 90.0)
		if tick % 1800 == 0:
			al_lvl = clamp(al_lvl + 18.0, 0.0, 100.0)
		if tick % 2400 == 0:
			bi_lvl = clamp(bi_lvl + 12.0, 0.0, 100.0)

		# --- Mixing ---
		solids = float(read(BASE + "/Mixing/SlurryTank01/Solids_pct"))
		visc = float(read(BASE + "/Mixing/SlurryTank01/Viscosity_cP"))
		ph = float(read(BASE + "/Mixing/SlurryTank01/pH"))
		temp = float(read(BASE + "/Mixing/SlurryTank01/Temperature_C"))
		agit = float(read(BASE + "/Mixing/SlurryTank01/Agitator_RPM"))

		solids = clamp(solids + random.gauss(0, 0.05), 58.0, 66.0)
		temp = clamp(temp + random.gauss(0, 0.08), 24.0, 33.0)
		ph = clamp(ph + random.gauss(0, 0.01), 8.7, 9.6)
		agit = clamp(agit + random.gauss(0, 2.0), 180.0, 320.0)

		target_visc = 650.0 + 55.0 * (solids - 60.0) - 8.0 * (temp - 28.0)
		visc = clamp(0.88 * visc + 0.12 * (target_visc + random.gauss(0, 18.0)), 520.0, 1150.0)

		# --- Spray dryer ---
		st["dryer_fouling"] = clamp(st["dryer_fouling"] + 0.0004 + abs(random.gauss(0, 0.0003)), 0.0, 1.0)
		if tick % 3600 == 0:
			st["dryer_fouling"] = clamp(st["dryer_fouling"] - 0.6, 0.0, 1.0)

		inlet = clamp(210.0 + random.gauss(0, 1.2), 195.0, 230.0)
		atom = clamp(12500.0 + random.gauss(0, 120.0), 11800.0, 13200.0)
		outlet = clamp(92.0 + 6.0 * st["dryer_fouling"] + random.gauss(0, 0.8), 80.0, 112.0)
		moist = clamp(0.70 + 0.25 * st["dryer_fouling"] + 0.00025 * (visc - 800.0) + abs(random.gauss(0, 0.03)), 0.4, 2.0)
		dp = clamp(2.1 + 1.8 * st["dryer_fouling"] + abs(random.gauss(0, 0.05)), 1.2, 6.5)

		# --- Pressing ---
		press_run = bool(read(BASE + "/Pressing/Press01/Running"))
		alarm = bool(read(BASE + "/Pressing/Press01/AlarmActive"))
		last_alarm = str(read(BASE + "/Pressing/Press01/LastAlarm") or "")

		now_s = time.time()
		if press_run and random.random() < 0.002:
			press_run = False
			st["press_restart_at"] = now_s + random.randint(10, 25)
			alarm = True
			last_alarm = "Die jam / ejection fault"
		if (not press_run) and (now_s >= float(st.get("press_restart_at", 0.0))):
			press_run = True
			alarm = False
			last_alarm = ""

		press_force = clamp(1180.0 + random.gauss(0, 18.0), 1050.0, 1400.0)
		hyd = clamp(165.0 + random.gauss(0, 2.5), 150.0, 190.0)
		die_t = clamp(42.0 + random.gauss(0, 0.3), 38.0, 50.0)

		cycle = clamp(4.1 + 0.8 * max(0.0, moist - 0.9) + abs(random.gauss(0, 0.05)), 3.8, 6.5)
		rate = 60.0 / cycle if press_run else 0.0
		rate = clamp(rate + random.gauss(0, 0.4), 0.0, 18.0)

		# --- Kiln ---
		z1_tgt = float(read(BASE + "/Config/KilnProfile_TargetZone1_C"))
		z2_tgt = float(read(BASE + "/Config/KilnProfile_TargetZone2_C"))
		z3_tgt = float(read(BASE + "/Config/KilnProfile_TargetZone3_C"))

		z1 = float(read(BASE + "/Kiln01/Zones/Zone1_Temp_C"))
		z2 = float(read(BASE + "/Kiln01/Zones/Zone2_Temp_C"))
		z3 = float(read(BASE + "/Kiln01/Zones/Zone3_Temp_C"))

		if random.random() < 0.0008:
			st["kiln_bias3"] = clamp(st["kiln_bias3"] + random.choice([-1.0, 1.0]) * (0.8 + 0.6 * random.random()), -18.0, 18.0)
		st["kiln_bias3"] *= 0.9996

		z1 = clamp(0.96 * z1 + 0.04 * (z1_tgt + random.gauss(0, 2.0)), z1_tgt - 25.0, z1_tgt + 25.0)
		z2 = clamp(0.96 * z2 + 0.04 * (z2_tgt + random.gauss(0, 3.0)), z2_tgt - 35.0, z2_tgt + 35.0)
		z3 = clamp(0.96 * z3 + 0.04 * (z3_tgt + st["kiln_bias3"] + random.gauss(0, 4.0)), z3_tgt - 60.0, z3_tgt + 60.0)

		belt = clamp(float(read(BASE + "/Kiln01/BeltSpeed_mm_s")) + random.gauss(0, 0.05), 14.0, 26.0)
		o2 = clamp(1.8 + random.gauss(0, 0.12) + 0.001 * max(0.0, st["kiln_bias3"]), 0.6, 4.0)
		dew = clamp(-18.0 + random.gauss(0, 0.8) + 0.02 * max(0.0, st["kiln_bias3"]), -35.0, 5.0)
		exh = clamp(255.0 + 0.04 * (z3 - z3_tgt) + random.gauss(0, 1.0), 220.0, 320.0)

		# --- Grinding ---
		tool = float(read(BASE + "/Grinding/Grinder01/ToolWear_Index"))
		tool = clamp(tool + 0.00002 + abs(random.gauss(0, 0.00003)) + 0.00001 * max(0.0, moist - 0.9), 0.05, 0.95)
		if tick % 7200 == 0:
			tool = clamp(tool - 0.35, 0.05, 0.95)

		spindle_a = clamp(18.0 + 18.0 * tool + random.gauss(0, 0.9), 10.0, 55.0)
		feed = clamp(6.8 - 2.6 * tool + random.gauss(0, 0.2), 2.2, 8.0)
		cool = clamp(18.0 + random.gauss(0, 0.4), 12.0, 26.0)

		kiln_dev3 = z3 - z3_tgt
		status = "OK"
		if abs(kiln_dev3) > 20.0:
			status = "Kiln Zone3 deviation %.1fC" % kiln_dev3
		elif moist > 1.2:
			status = "Powder moisture high (%.2f%%)" % moist
		elif press_run is False:
			status = "Press stopped"

		write_pairs([
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
		])

		safe_write_diag("OK", status)

except Exception as e:
	safe_write_diag("ERROR", str(e))


