# Ignition Gateway Timer Script (Jython) - Manufacturing Process/SCADA (TOP-LEVEL)
# Provider: manufacturing
# Writes:   [manufacturing]Manufacturing/Site01/...

import random, math, time

BASE = "[manufacturing]Manufacturing/Site01"
DIAG = BASE + "/Diagnostics"
log = system.util.getLogger("manufacturing_site01.process")

DEBUG_WINDOW_S = 60.0   # after script reload, emit extra debug for this many seconds
DEBUG_EVERY_S = 5.0     # emit debug at most this often


def now_iso():
	return system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")


def clamp(x, lo, hi):
	return max(lo, min(hi, x))


def read(path):
	qv = system.tag.readBlocking([path])[0]
	try:
		if qv.quality is not None and (not qv.quality.isGood()):
			return None
	except:
		pass
	return qv.value


def read_float(path, default):
	try:
		v = read(path)
		return default if v is None else float(v)
	except:
		return default


def write_pairs(pairs):
	paths = [p for (p, _) in pairs]
	vals = [v for (_, v) in pairs]
	results = system.tag.writeBlocking(paths, vals)
	# Return + log write qualities so failures can't be silent.
	try:
		# Summarize qualities
		qstr = [str(x) for x in results]
		bad = []
		for i in range(len(results)):
			qi = results[i]
			try:
				is_good = qi is not None and qi.isGood()
			except:
				is_good = (str(qi) == "Good")
			if not is_good:
				bad.append((paths[i], str(qi)))

		# Log qualities periodically (or always on failure)
		try:
			g = system.util.getGlobals()
			last = float(g.get("manufacturing_site01_process_last_writeq", 0.0) or 0.0)
			now = time.time()
			if bad or (now - last) >= 60.0:
				g["manufacturing_site01_process_last_writeq"] = now
				log.info("write qualities: %r" % qstr)
		except:
			pass

		if bad:
			log.error("WRITE_FAIL (first 10): %r" % bad[:10])
	except:
		pass
	return results


def safe_write_diag(status, msg):
	try:
		ts = now_iso()
		r = system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, status, msg or ""])
		try:
			if any(str(x) != "Good" for x in r):
				log.error("WRITE_FAIL diag fields: %r" % ([str(x) for x in r],))
		except:
			pass
		try:
			cur = system.tag.readBlocking([DIAG + "/TickCount"])[0].value
			cur = int(cur or 0)
			r2 = system.tag.writeBlocking([DIAG + "/TickCount"], [cur + 1])
			try:
				if any(str(x) != "Good" for x in r2):
					log.error("WRITE_FAIL diag TickCount: %r" % ([str(x) for x in r2],))
			except:
				pass
		except:
			pass
	except:
		pass


try:
	safe_write_diag("START", "")
	# Low-noise heartbeat: log about once per minute so wrapper.log proves execution.
	g_hb = system.util.getGlobals()
	last_hb = float(g_hb.get("manufacturing_site01_process_last_hb", 0.0) or 0.0)
	now_hb = time.time()
	if (now_hb - last_hb) >= 60.0:
		g_hb["manufacturing_site01_process_last_hb"] = now_hb
		log.info("tick (heartbeat): process timer executing")

	# Short debug window right after a script restart so we can quickly diagnose "runs but no changes".
	try:
		dbg_until = g_hb.get("manufacturing_site01_process_dbg_until")
		dbg_until = float(dbg_until) if dbg_until is not None else 0.0
		if dbg_until <= now_hb:
			g_hb["manufacturing_site01_process_dbg_until"] = now_hb + DEBUG_WINDOW_S
			g_hb["manufacturing_site01_process_dbg_last"] = 0.0
	except:
		pass

	# IMPORTANT: If Config/SimEnabled is missing (e.g. tags not imported yet),
	# don't silently skip forever. Only skip when it's explicitly present AND false.
	sim_enabled = read(BASE + "/Config/SimEnabled")
	if (sim_enabled is not None) and (not bool(sim_enabled)):
		safe_write_diag("SKIP", "Sim disabled (Config/SimEnabled=false)")
	else:
		g = system.util.getGlobals()
		st = g.get("manufacturing_process_state")
		if st is None:
			st = {
				"t0": time.time(),
				"kiln_bias3": 0.0,
				"dryer_fouling": 0.0,
				"press_restart_at": 0.0,
			}
			g["manufacturing_process_state"] = st

		tick = int(read(DIAG + "/TickCount") or 0) + 1

		# Emit a small debug line every few seconds during the debug window.
		try:
			dbg_until = float(g_hb.get("manufacturing_site01_process_dbg_until", 0.0) or 0.0)
			dbg_last = float(g_hb.get("manufacturing_site01_process_dbg_last", 0.0) or 0.0)
			if (now_hb <= dbg_until) and ((now_hb - dbg_last) >= DEBUG_EVERY_S):
				g_hb["manufacturing_site01_process_dbg_last"] = now_hb
				log.info("debug: tick=%d simEnabled=%r base=%s" % (tick, sim_enabled, BASE))
		except:
			pass

		# --- Raw materials slowly deplete/replenish ---
		al_lvl = read_float(BASE + "/RawMaterials/AluminaHopper_Level_pct", 72.0)
		bi_lvl = read_float(BASE + "/RawMaterials/BinderTank_Level_pct", 55.0)
		di_lvl = read_float(BASE + "/RawMaterials/DispersantTank_Level_pct", 61.0)

		al_lvl = clamp(al_lvl - 0.004 + random.gauss(0, 0.002), 15.0, 95.0)
		bi_lvl = clamp(bi_lvl - 0.003 + random.gauss(0, 0.002), 10.0, 90.0)
		di_lvl = clamp(di_lvl - 0.0015 + random.gauss(0, 0.001), 10.0, 90.0)
		if tick % 1800 == 0:
			al_lvl = clamp(al_lvl + 18.0, 0.0, 100.0)
		if tick % 2400 == 0:
			bi_lvl = clamp(bi_lvl + 12.0, 0.0, 100.0)

		# --- Mixing ---
		solids = read_float(BASE + "/Mixing/SlurryTank01/Solids_pct", 62.0)
		visc = read_float(BASE + "/Mixing/SlurryTank01/Viscosity_cP", 850.0)
		ph = read_float(BASE + "/Mixing/SlurryTank01/pH", 9.2)
		temp = read_float(BASE + "/Mixing/SlurryTank01/Temperature_C", 28.0)
		agit = read_float(BASE + "/Mixing/SlurryTank01/Agitator_RPM", 240.0)

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
		press_run = bool(read(BASE + "/Pressing/Press01/Running") if read(BASE + "/Pressing/Press01/Running") is not None else True)
		alarm = bool(read(BASE + "/Pressing/Press01/AlarmActive") if read(BASE + "/Pressing/Press01/AlarmActive") is not None else False)
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
		z1_tgt = read_float(BASE + "/Config/KilnProfile_TargetZone1_C", 850.0)
		z2_tgt = read_float(BASE + "/Config/KilnProfile_TargetZone2_C", 1350.0)
		z3_tgt = read_float(BASE + "/Config/KilnProfile_TargetZone3_C", 1600.0)

		z1 = read_float(BASE + "/Kiln01/Zones/Zone1_Temp_C", z1_tgt - 5.0)
		z2 = read_float(BASE + "/Kiln01/Zones/Zone2_Temp_C", z2_tgt - 5.0)
		z3 = read_float(BASE + "/Kiln01/Zones/Zone3_Temp_C", z3_tgt - 8.0)

		if random.random() < 0.0008:
			st["kiln_bias3"] = clamp(st["kiln_bias3"] + random.choice([-1.0, 1.0]) * (0.8 + 0.6 * random.random()), -18.0, 18.0)
		st["kiln_bias3"] *= 0.9996

		z1 = clamp(0.96 * z1 + 0.04 * (z1_tgt + random.gauss(0, 2.0)), z1_tgt - 25.0, z1_tgt + 25.0)
		z2 = clamp(0.96 * z2 + 0.04 * (z2_tgt + random.gauss(0, 3.0)), z2_tgt - 35.0, z2_tgt + 35.0)
		z3 = clamp(0.96 * z3 + 0.04 * (z3_tgt + st["kiln_bias3"] + random.gauss(0, 4.0)), z3_tgt - 60.0, z3_tgt + 60.0)

		belt = clamp(read_float(BASE + "/Kiln01/BeltSpeed_mm_s", 18.0) + random.gauss(0, 0.05), 14.0, 26.0)
		o2 = clamp(1.8 + random.gauss(0, 0.12) + 0.001 * max(0.0, st["kiln_bias3"]), 0.6, 4.0)
		dew = clamp(-18.0 + random.gauss(0, 0.8) + 0.02 * max(0.0, st["kiln_bias3"]), -35.0, 5.0)
		exh = clamp(255.0 + 0.04 * (z3 - z3_tgt) + random.gauss(0, 1.0), 220.0, 320.0)

		# --- Grinding ---
		tool = read_float(BASE + "/Grinding/Grinder01/ToolWear_Index", 0.15)
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

		results = write_pairs([
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

		# If any write failed, make it visible in Diagnostics (so it can’t “look stuck” quietly).
		try:
			bad_count = sum(1 for x in results if str(x) != "Good")
		except:
			bad_count = 0

		if bad_count > 0:
			safe_write_diag("WRITE_FAILED", "%s (bad=%d)" % (status, bad_count))
		else:
			safe_write_diag("OK", status)

except Exception as e:
	try:
		log.error("timer failed", e)
	except:
		pass
	safe_write_diag("ERROR", str(e))


