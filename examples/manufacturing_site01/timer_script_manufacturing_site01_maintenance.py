# Ignition Gateway Timer Script (Jython) - Manufacturing Maintenance (TOP-LEVEL)
# Provider: manufacturing_maintenance
# Writes:   [manufacturing_maintenance]Manufacturing/Site01/...
# Reads:    [manufacturing] process signals for coupling

import random

BASE_MA = "[manufacturing_maintenance]Manufacturing/Site01"
BASE_P = "[manufacturing]Manufacturing/Site01"
DIAG = BASE_MA + "/Diagnostics"
log = system.util.getLogger("manufacturing_site01.maintenance")


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


def read_bool(path, default):
	try:
		v = read(path)
		return default if v is None else bool(v)
	except:
		return default


def read_int(path, default):
	try:
		v = read(path)
		return default if v is None else int(v)
	except:
		return default


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
	# Low-noise heartbeat: once per minute in wrapper.log so you can prove execution.
	g_hb = system.util.getGlobals()
	last_hb = float(g_hb.get("manufacturing_site01_maint_last_hb", 0.0) or 0.0)
	now_hb = system.date.now()
	try:
		now_s = float(system.date.toMillis(now_hb)) / 1000.0
		if (now_s - last_hb) >= 60.0:
			g_hb["manufacturing_site01_maint_last_hb"] = now_s
			log.info("tick (heartbeat): maintenance timer executing")
	except:
		pass

	if not bool(read(BASE_MA + "/Config/SimEnabled")):
		safe_write_diag("SKIP", "Sim disabled")
	else:
		# These come from the process provider. If process tags aren't imported yet, default safely.
		z3 = read_float(BASE_P + "/Kiln01/Zones/Zone3_Temp_C", 1590.0)
		z3_tgt = read_float(BASE_P + "/Config/KilnProfile_TargetZone3_C", 1600.0)
		kiln_dev = z3 - z3_tgt
		press_alarm = read_bool(BASE_P + "/Pressing/Press01/AlarmActive", False)
		tool = read_float(BASE_P + "/Grinding/Grinder01/ToolWear_Index", 0.15)

		tc_drift = clamp(abs(kiln_dev) * 0.06 + abs(random.gauss(0, 0.3)), 0.0, 25.0)
		kiln_vib = clamp(1.7 + 0.03 * abs(kiln_dev) + abs(random.gauss(0, 0.2)), 0.6, 8.0)
		press_vib = clamp(2.2 + (1.2 if press_alarm else 0.0) + abs(random.gauss(0, 0.2)), 0.8, 9.0)
		gr_vib = clamp(1.3 + 2.8 * max(0.0, tool - 0.5) + abs(random.gauss(0, 0.2)), 0.5, 9.0)

		active = read_int(BASE_MA + "/Maintenance/WorkOrders/ActiveCount", 4)
		high = read_int(BASE_MA + "/Maintenance/WorkOrders/HighPriorityCount", 1)
		last_id = str(read(BASE_MA + "/Maintenance/WorkOrders/LastWorkOrderId") or "")
		last_sum = str(read(BASE_MA + "/Maintenance/WorkOrders/LastWorkOrderSummary") or "")

		new_wo = None
		if abs(kiln_dev) > 25.0 and random.random() < 0.5:
			new_wo = ("WO-%d" % random.randint(77000, 79999), "Investigate kiln zone 3 deviation (thermocouple / tuning)")
			high = min(9, high + 1)
		elif press_alarm and random.random() < 0.5:
			new_wo = ("WO-%d" % random.randint(77000, 79999), "Press01: inspect die/ejector and hydraulic pressure stability")
			high = min(9, high + 1)
		elif tool > 0.7 and random.random() < 0.4:
			new_wo = ("WO-%d" % random.randint(77000, 79999), "Grinder01: schedule wheel/tool change; check spindle bearings")

		if new_wo is not None:
			active = min(50, active + 1)
			last_id, last_sum = new_wo

		if active > 0 and random.random() < 0.25:
			active = max(0, active - 1)
			if high > 0 and random.random() < 0.35:
				high = max(0, high - 1)

		press_seals = read_int(BASE_MA + "/Maintenance/Spares/Press01_SealKit_Stock", 6)
		tc_stock = read_int(BASE_MA + "/Maintenance/Spares/Kiln01_Thermocouple_Stock", 12)
		gr_bear = read_int(BASE_MA + "/Maintenance/Spares/Grinder01_Bearing_Stock", 4)

		if press_alarm and random.random() < 0.2:
			press_seals = max(0, press_seals - 1)
		if abs(kiln_dev) > 30.0 and random.random() < 0.2:
			tc_stock = max(0, tc_stock - 1)
		if tool > 0.75 and random.random() < 0.15:
			gr_bear = max(0, gr_bear - 1)

		system.tag.writeBlocking(
			[
				BASE_MA + "/Maintenance/Condition/Kiln01_ThermocoupleDrift_C",
				BASE_MA + "/Maintenance/Condition/Kiln01_BlowerVibration_mm_s",
				BASE_MA + "/Maintenance/Condition/Press01_PumpVibration_mm_s",
				BASE_MA + "/Maintenance/Condition/Grinder01_SpindleVibration_mm_s",
				BASE_MA + "/Maintenance/WorkOrders/ActiveCount",
				BASE_MA + "/Maintenance/WorkOrders/HighPriorityCount",
				BASE_MA + "/Maintenance/WorkOrders/LastWorkOrderId",
				BASE_MA + "/Maintenance/WorkOrders/LastWorkOrderSummary",
				BASE_MA + "/Maintenance/Spares/Press01_SealKit_Stock",
				BASE_MA + "/Maintenance/Spares/Kiln01_Thermocouple_Stock",
				BASE_MA + "/Maintenance/Spares/Grinder01_Bearing_Stock",
			],
			[
				float(tc_drift),
				float(kiln_vib),
				float(press_vib),
				float(gr_vib),
				int(active),
				int(high),
				str(last_id),
				str(last_sum),
				int(press_seals),
				int(tc_stock),
				int(gr_bear),
			],
		)

		safe_write_diag("OK", "WO active=%d high=%d kilnDev=%.1fC" % (active, high, kiln_dev))

except Exception as e:
	try:
		log.error("timer failed", e)
	except:
		pass
	safe_write_diag("ERROR", str(e))


