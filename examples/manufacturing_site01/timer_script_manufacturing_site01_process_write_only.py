# Manufacturing Site01 - Process (WRITE-ONLY, NO FUNCTIONS)
# Provider: manufacturing
# Paste into: Gateway Timer Scripts / Gateway Events -> Timer (Fixed Delay ~1000ms)
#
# NOTE: In some Ignition timer-script contexts, `system` and other top-level names
# may not be visible inside `def` functions. This script is intentionally written
# as top-level code only (no defs) for maximum reliability.

import math, traceback

log = system.util.getLogger("manufacturing_site01.process_write_only")

BASE = "[manufacturing]Manufacturing/Site01"
DIAG = BASE + "/Diagnostics"
RM = BASE + "/RawMaterials"
MIX = BASE + "/Mixing/SlurryTank01"
PRESS = BASE + "/Pressing/Press01"
KILN = BASE + "/Kiln01"
DRY = BASE + "/SprayDryer01"
GRIND = BASE + "/Grinding/Grinder01"

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

		# Raw materials
		al = 72.0 + 6.0 * math.sin(tick / 200.0)
		bi = 55.0 + 4.0 * math.sin(tick / 240.0)
		di = 61.0 + 3.0 * math.sin(tick / 300.0)

		# Kiln
		z1 = 850.0  + 10.0 * math.sin(tick / 12.0)
		z2 = 1350.0 + 18.0 * math.sin(tick / 15.0)
		z3 = 1600.0 + 25.0 * math.sin(tick / 10.0)
		belt = 18.0 + 0.4 * math.sin(tick / 20.0)
		o2   = 1.8  + 0.15 * math.sin(tick / 18.0)
		dew  = -18.0 + 1.2 * math.sin(tick / 25.0)
		exh  = 260.0 + 8.0 * math.sin(tick / 14.0)

		# Slurry / Mixing
		solids = 62.0 + 0.6 * math.sin(tick / 17.0)
		temp   = 28.0 + 0.8 * math.sin(tick / 19.0)
		ph     = 9.2  + 0.06 * math.sin(tick / 23.0)
		agit   = 240.0 + 18.0 * math.sin(tick / 11.0)
		visc   = 850.0 + 70.0 * math.sin(tick / 13.0) - 15.0 * math.sin(tick / 29.0)

		# Pressing
		alarm = (tick % 120) < 6
		running = (not alarm)
		last_alarm = "Die jam / ejection fault" if alarm else ""
		cycle = 4.2 + 0.25 * math.sin(tick / 16.0) + (0.9 if alarm else 0.0)
		rate  = (60.0 / max(3.8, cycle)) if running else 0.0
		press_force = 1200.0 + 35.0 * math.sin(tick / 9.0)
		hyd = 165.0 + 3.0 * math.sin(tick / 14.0)
		die_t = 42.0 + 0.6 * math.sin(tick / 21.0)

		# Spray dryer
		inlet = 210.0 + 4.0 * math.sin(tick / 20.0)
		outlet = 92.0 + 2.0 * math.sin(tick / 22.0)
		atom = 12500.0 + 220.0 * math.sin(tick / 18.0)
		moist = 0.8 + 0.12 * math.sin(tick / 25.0)
		cdp = 2.2 + 0.15 * math.sin(tick / 16.0)

		# Grinding
		tool = 0.15 + 0.03 * math.sin(tick / 400.0)
		spindle = 22.0 + 2.2 * math.sin(tick / 13.0)
		feed = 6.5 + 0.4 * math.sin(tick / 15.0)
		cool = 18.0 + 0.6 * math.sin(tick / 17.0)

		paths = [
			DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError", DIAG + "/TickCount",

			RM + "/AluminaHopper_Level_pct", RM + "/BinderTank_Level_pct", RM + "/DispersantTank_Level_pct",

			KILN + "/Zones/Zone1_Temp_C", KILN + "/Zones/Zone2_Temp_C", KILN + "/Zones/Zone3_Temp_C",
			KILN + "/BeltSpeed_mm_s", KILN + "/Atmosphere_O2_pct", KILN + "/Dewpoint_C", KILN + "/ExhaustTemp_C",

			MIX + "/Solids_pct", MIX + "/Viscosity_cP", MIX + "/pH", MIX + "/Temperature_C", MIX + "/Agitator_RPM",

			PRESS + "/Running", PRESS + "/PressForce_kN", PRESS + "/CycleTime_s", PRESS + "/PartRate_parts_per_min",
			PRESS + "/HydraulicPressure_bar", PRESS + "/DieTemp_C", PRESS + "/AlarmActive", PRESS + "/LastAlarm",

			DRY + "/InletTemp_C", DRY + "/OutletTemp_C", DRY + "/Atomizer_RPM", DRY + "/PowderMoisture_pct", DRY + "/CycloneDP_kPa",

			GRIND + "/SpindleCurrent_A", GRIND + "/FeedRate_mm_s", GRIND + "/CoolantFlow_L_min", GRIND + "/ToolWear_Index",
		]

		vals = [
			ts, "OK", "", tick,

			float(al), float(bi), float(di),

			float(z1), float(z2), float(z3), float(belt), float(o2), float(dew), float(exh),

			float(solids), float(visc), float(ph), float(temp), float(agit),

			bool(running), float(press_force), float(cycle), float(rate), float(hyd), float(die_t), bool(alarm), str(last_alarm),

			float(inlet), float(outlet), float(atom), float(moist), float(cdp),

			float(spindle), float(feed), float(cool), float(tool),
		]

		results = system.tag.writeBlocking(paths, vals)
		q = [str(r) for r in results]
		bad = [(paths[i], q[i]) for i in range(len(q)) if q[i] != "Good"]
		if bad:
			log.error("WRITE_FAIL (first 10): %r" % (bad[:10],))
		elif (tick % 10) == 0:
			log.info(
				"Process tick ok. KilnZ3=%.1fC, PressForce=%.0fkN, Moist=%.2f%%, ToolWear=%.3f"
				% (z3, press_force, moist, tool)
			)

except:
	tb = traceback.format_exc()
	try:
		ts = system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")
		system.tag.writeBlocking([DIAG + "/LastRun", DIAG + "/LastStatus", DIAG + "/LastError"], [ts, "ERROR", tb])
	except:
		pass
	log.error("manufacturing process write-only timer failed:\n%s" % tb)


