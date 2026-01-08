def handleTimerEvent():
	"""
	Ignition Gateway Timer Script (Jython) — Ignition 8.1 compatible
	CoorsTek demo: MES-ish order/WIP/count signals (no energy)

	Recommended timer delay: 5000ms (Fixed Delay)
	Tag provider must be named: coorstek_mes

	Reads throughput from `coorstek` and yield from `coorstek_qc` to increment good/reject counts.
	"""

	import random
	import time

	BASE_M = "[coorstek_mes]CoorsTek/Site01"
	BASE_P = "[coorstek]CoorsTek/Site01"
	BASE_Q = "[coorstek_qc]CoorsTek/Site01"

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
		if "coorstek_mes_state" not in g:
			g["coorstek_mes_state"] = {"last_ts": time.time()}
		return g["coorstek_mes_state"]

	try:
		if not bool(read(BASE_M + "/Config/SimEnabled")):
			write([
				(BASE_M + "/Diagnostics/LastRun", now_iso()),
				(BASE_M + "/Diagnostics/LastStatus", "Sim disabled"),
				(BASE_M + "/Diagnostics/LastError", "")
			])
			return

		s = st()
		now = time.time()
		dt = max(1.0, now - s["last_ts"])
		s["last_ts"] = now

		tick = int(read(BASE_M + "/Diagnostics/TickCount")) + 1

		target = int(read(BASE_M + "/MES/Orders/TargetQty"))
		good = int(read(BASE_M + "/MES/Orders/GoodCount"))
		rej = int(read(BASE_M + "/MES/Orders/RejectCount"))
		wip = int(read(BASE_M + "/MES/Orders/WIPCount"))

		status = str(read(BASE_M + "/MES/Orders/Status") or "RUNNING")

		press_running = bool(read(BASE_P + "/Pressing/Press01/Running"))
		thru = float(read(BASE_P + "/Pressing/Press01/PartRate_parts_per_min"))
		yield_pct = float(read(BASE_Q + "/QC/Inspection/Vision01/Yield_pct"))

		# simulate occasional small downtime windows (e.g., changeover/material)
		downtime = bool(read(BASE_M + "/MES/Production/DowntimeActive"))
		reason = str(read(BASE_M + "/MES/Production/DowntimeReason") or "")
		if (not downtime) and (random.random() < 0.04):
			downtime = True
			reason = random.choice(["Material staging", "Die cleaning", "QC hold review", "Minor adjustment"])
			s["downtime_until"] = now + random.randint(30, 120)
		if downtime and ("downtime_until" in s) and (now >= s["downtime_until"]):
			downtime = False
			reason = ""

		if good >= target:
			status = "COMPLETE"
			downtime = True
			reason = "Order complete"

		# compute produced parts in dt seconds
		effective_rate = 0.0
		if (not downtime) and press_running and status == "RUNNING":
			effective_rate = thru

		parts = int(round((effective_rate / 60.0) * dt))
		parts = max(0, parts)

		# yield drives good vs reject
		p_good = clamp(yield_pct / 100.0, 0.0, 1.0)
		g_inc = 0
		r_inc = 0
		for _ in range(parts):
			if random.random() < p_good:
				g_inc += 1
			else:
				r_inc += 1

		# wip fluctuates with kiln queueing
		wip = int(clamp(wip + int(random.gauss(0, 8)) + int(0.15 * parts) - int(0.1 * (g_inc + r_inc)), 0, 8000))

		good = min(target, good + g_inc)
		rej = rej + r_inc

		scrap_rate = 0.0
		if (good + rej) > 0:
			scrap_rate = 100.0 * float(rej) / float(good + rej)

		# OEE-ish metrics (simple narrative)
		avail = 96.0 - (4.0 if downtime else 0.0) - (6.0 if not press_running else 0.0)
		perf = clamp(92.0 + 4.0 * (thru / 14.0) + random.gauss(0, 0.6), 70.0, 105.0)
		qual = clamp(yield_pct + random.gauss(0, 0.2), 75.0, 99.9)
		oee = clamp((avail * perf * qual) / 10000.0, 0.0, 99.9)

		write([
			(BASE_M + "/MES/Orders/GoodCount", int(good)),
			(BASE_M + "/MES/Orders/RejectCount", int(rej)),
			(BASE_M + "/MES/Orders/WIPCount", int(wip)),
			(BASE_M + "/MES/Orders/Status", str(status)),

			(BASE_M + "/MES/Production/Throughput_parts_per_min", float(thru)),
			(BASE_M + "/MES/Production/ScrapRate_pct", float(scrap_rate)),
			(BASE_M + "/MES/Production/DowntimeActive", bool(downtime)),
			(BASE_M + "/MES/Production/DowntimeReason", str(reason)),

			(BASE_M + "/MES/OEE/Availability_pct", float(clamp(avail, 0.0, 100.0))),
			(BASE_M + "/MES/OEE/Performance_pct", float(clamp(perf, 0.0, 110.0))),
			(BASE_M + "/MES/OEE/Quality_pct", float(clamp(qual, 0.0, 100.0))),
			(BASE_M + "/MES/OEE/OEE_pct", float(oee)),

			(BASE_M + "/Diagnostics/TickCount", int(tick)),
			(BASE_M + "/Diagnostics/LastRun", now_iso()),
			(BASE_M + "/Diagnostics/LastStatus", "good=%d/%d rej=%d wip=%d" % (good, target, rej, wip)),
			(BASE_M + "/Diagnostics/LastError", "")
		])

	except Exception as e:
		try:
			write([
				(BASE_M + "/Diagnostics/LastRun", now_iso()),
				(BASE_M + "/Diagnostics/LastStatus", "ERROR"),
				(BASE_M + "/Diagnostics/LastError", repr(e))
			])
		except:
			pass


handleTimerEvent()


