def handleTimerEvent():
	"""
	Ignition Gateway Timer Script (Jython) — Ignition 8.1 compatible
	Pluspetrol demo: Safety signals (H2S, Fire&GAS, ESD)

	Recommended timer delay: 2000ms (Fixed Delay)
	Tag provider must be named: pluspetrol_safety
	"""

	import random

	BASE = "[pluspetrol_safety]Pluspetrol/Argentina/LaCalera"

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

		esd = bool(read(BASE + "/Safety/ESD_Active"))
		firegas = bool(read(BASE + "/Safety/FireGas_Alarm"))

		# Baseline H2S noise (upsets script may override with spikes)
		h2s = float(read(BASE + "/Safety/H2S_ppm"))
		if h2s < 10.0:
			h2s = clamp(2.0 + random.gauss(0, 0.5), 0.0, 12.0)

		# Auto-clear short fire/gas latches unless an upset script holds it
		if firegas and random.random() < 0.35:
			firegas = False

		# ESD is controlled by operator/upsets script; do not auto-clear aggressively.
		# But if it has been left on for a long time in demo, allow auto-clear occasionally.
		if esd and random.random() < 0.05:
			esd = True  # keep latched most of the time

		write([
			(BASE + "/Safety/H2S_ppm", float(h2s)),
			(BASE + "/Safety/FireGas_Alarm", bool(firegas)),
			(BASE + "/Safety/ESD_Active", bool(esd)),

			(BASE + "/Diagnostics/TickCount", int(tick)),
			(BASE + "/Diagnostics/LastRun", now_iso()),
			(BASE + "/Diagnostics/LastStatus", "Safety: esd=%s fg=%s h2s=%.1f" % (esd, firegas, h2s)),
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


