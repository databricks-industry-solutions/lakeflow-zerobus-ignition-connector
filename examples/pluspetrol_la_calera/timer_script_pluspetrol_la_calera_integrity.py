def handleTimerEvent():
	"""
	Ignition Gateway Timer Script (Jython) — Ignition 8.1 compatible
	Pluspetrol demo: Asset integrity signals (corrosion, pigging interval, leak suspected)

	Recommended timer delay: 10000ms (Fixed Delay)
	Tag provider must be named: pluspetrol_integrity
	"""

	import random

	BASE = "[pluspetrol_integrity]Pluspetrol/Argentina/LaCalera"

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
		if not bool(read(BASE + "/Config/SimEnabled")):
			write([
				(BASE + "/Diagnostics/LastRun", now_iso()),
				(BASE + "/Diagnostics/LastStatus", "Sim disabled"),
				(BASE + "/Diagnostics/LastError", "")
			])
			return

		tick = int(read(BASE + "/Diagnostics/TickCount")) + 1

		corr = float(read(BASE + "/Integrity/CorrosionRate_mm_per_yr"))
		pig = int(read(BASE + "/Integrity/Pigging_DaysSince"))
		leak = bool(read(BASE + "/Integrity/LeakSuspected"))

		# corrosion drifts slowly (bounded)
		corr = clamp(corr + random.gauss(0, 0.002), 0.02, 0.45)

		# pigging counter increments slowly (simulate “days” using ticks)
		# With a 10s timer: 1 "day" every ~360 ticks (~1 hour) to keep the demo lively.
		if tick % 360 == 0:
			pig = pig + 1

		# rare leak-suspected event that clears
		if (not leak) and random.random() < 0.01:
			leak = True
		if leak and random.random() < 0.12:
			leak = False

		write([
			(BASE + "/Integrity/CorrosionRate_mm_per_yr", float(corr)),
			(BASE + "/Integrity/Pigging_DaysSince", int(pig)),
			(BASE + "/Integrity/LeakSuspected", bool(leak)),

			(BASE + "/Diagnostics/TickCount", int(tick)),
			(BASE + "/Diagnostics/LastRun", now_iso()),
			(BASE + "/Diagnostics/LastStatus", "Integrity: corr=%.2f pigDays=%d leak=%s" % (corr, pig, leak)),
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


