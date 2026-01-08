def handleTimerEvent():
	"""
	Ignition Gateway Timer Script (Jython) — Ignition 8.1 compatible
	CoorsTek demo: Maintenance + condition monitoring + work orders

	Recommended timer delay: 10000ms (Fixed Delay)
	Tag provider must be named: coorstek_maintenance

	Reads a few process tags to create realistic maintenance narratives:
	- kiln zone deviation → thermocouple drift work order
	- press alarm → inspection / hydraulic check
	- grinder tool wear → wheel change / bearing check
	"""

	import random

	BASE_MA = "[coorstek_maintenance]CoorsTek/Site01"
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
		if not bool(read(BASE_MA + "/Config/SimEnabled")):
			write([
				(BASE_MA + "/Diagnostics/LastRun", now_iso()),
				(BASE_MA + "/Diagnostics/LastStatus", "Sim disabled"),
				(BASE_MA + "/Diagnostics/LastError", "")
			])
			return

		tick = int(read(BASE_MA + "/Diagnostics/TickCount")) + 1

		z3 = float(read(BASE_P + "/Kiln01/Zones/Zone3_Temp_C"))
		z3_tgt = float(read(BASE_P + "/Config/KilnProfile_TargetZone3_C"))
		kiln_dev = z3 - z3_tgt
		press_alarm = bool(read(BASE_P + "/Pressing/Press01/AlarmActive"))
		tool = float(read(BASE_P + "/Grinding/Grinder01/ToolWear_Index"))

		# condition metrics
		tc_drift = clamp(abs(kiln_dev) * 0.06 + abs(random.gauss(0, 0.3)), 0.0, 25.0)
		kiln_vib = clamp(1.7 + 0.03 * abs(kiln_dev) + abs(random.gauss(0, 0.2)), 0.6, 8.0)
		press_vib = clamp(2.2 + (1.2 if press_alarm else 0.0) + abs(random.gauss(0, 0.2)), 0.8, 9.0)
		gr_vib = clamp(1.3 + 2.8 * max(0.0, tool - 0.5) + abs(random.gauss(0, 0.2)), 0.5, 9.0)

		active = int(read(BASE_MA + "/Maintenance/WorkOrders/ActiveCount"))
		high = int(read(BASE_MA + "/Maintenance/WorkOrders/HighPriorityCount"))
		last_id = str(read(BASE_MA + "/Maintenance/WorkOrders/LastWorkOrderId") or "")
		last_sum = str(read(BASE_MA + "/Maintenance/WorkOrders/LastWorkOrderSummary") or "")

		# create work orders when conditions are bad
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

		# occasionally close some work orders
		if active > 0 and random.random() < 0.25:
			active = max(0, active - 1)
			if high > 0 and random.random() < 0.35:
				high = max(0, high - 1)

		# spares consumption
		press_seals = int(read(BASE_MA + "/Maintenance/Spares/Press01_SealKit_Stock"))
		tc_stock = int(read(BASE_MA + "/Maintenance/Spares/Kiln01_Thermocouple_Stock"))
		gr_bear = int(read(BASE_MA + "/Maintenance/Spares/Grinder01_Bearing_Stock"))

		if press_alarm and random.random() < 0.2:
			press_seals = max(0, press_seals - 1)
		if abs(kiln_dev) > 30.0 and random.random() < 0.2:
			tc_stock = max(0, tc_stock - 1)
		if tool > 0.75 and random.random() < 0.15:
			gr_bear = max(0, gr_bear - 1)

		write([
			(BASE_MA + "/Maintenance/Condition/Kiln01_ThermocoupleDrift_C", float(tc_drift)),
			(BASE_MA + "/Maintenance/Condition/Kiln01_BlowerVibration_mm_s", float(kiln_vib)),
			(BASE_MA + "/Maintenance/Condition/Press01_PumpVibration_mm_s", float(press_vib)),
			(BASE_MA + "/Maintenance/Condition/Grinder01_SpindleVibration_mm_s", float(gr_vib)),

			(BASE_MA + "/Maintenance/WorkOrders/ActiveCount", int(active)),
			(BASE_MA + "/Maintenance/WorkOrders/HighPriorityCount", int(high)),
			(BASE_MA + "/Maintenance/WorkOrders/LastWorkOrderId", str(last_id)),
			(BASE_MA + "/Maintenance/WorkOrders/LastWorkOrderSummary", str(last_sum)),

			(BASE_MA + "/Maintenance/Spares/Press01_SealKit_Stock", int(press_seals)),
			(BASE_MA + "/Maintenance/Spares/Kiln01_Thermocouple_Stock", int(tc_stock)),
			(BASE_MA + "/Maintenance/Spares/Grinder01_Bearing_Stock", int(gr_bear)),

			(BASE_MA + "/Diagnostics/TickCount", int(tick)),
			(BASE_MA + "/Diagnostics/LastRun", now_iso()),
			(BASE_MA + "/Diagnostics/LastStatus", "WO active=%d high=%d kilnDev=%.1fC" % (active, high, kiln_dev)),
			(BASE_MA + "/Diagnostics/LastError", "")
		])

	except Exception as e:
		try:
			write([
				(BASE_MA + "/Diagnostics/LastRun", now_iso()),
				(BASE_MA + "/Diagnostics/LastStatus", "ERROR"),
				(BASE_MA + "/Diagnostics/LastError", repr(e))
			])
		except:
			pass


handleTimerEvent()


