def handleTimerEvent():
	"""
	Ignition Gateway Timer Script (Jython) — Ignition 8.1 compatible
	Demo: Pluspetrol (Argentina) — La Calera upsets / incidents (slow cadence)

	Purpose:
	- Inject occasional upsets to "wow" (compressor trip, tank high-high, H2S spike, fire/gas alarm, ESD drill)
	- Keep the base process sim (timer_script_pluspetrol_la_calera.py) running at 1s

	Recommended timer delay: 5000ms or 10000ms (Fixed Delay)
	Tag provider must be named: pluspetrol
	"""

	import random
	import time

	BASE_P = "[pluspetrol]Pluspetrol/Argentina/LaCalera"
	BASE_S = "[pluspetrol_safety]Pluspetrol/Argentina/LaCalera"

	def now_iso():
		return system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")

	def read(path):
		return system.tag.readBlocking([path])[0].value

	def write(pairs):
		paths = [p for (p, _) in pairs]
		vals = [v for (_, v) in pairs]
		system.tag.writeBlocking(paths, vals)

	def clamp(x, lo, hi):
		return max(lo, min(hi, x))

	def st():
		g = system.util.getGlobals()
		if "pluspetrol_upsets_state" not in g:
			g["pluspetrol_upsets_state"] = {
				"last_trip": 0.0,
				"trip_until": 0.0,
				"last_esd": 0.0,
				"esd_until": 0.0,
				"last_h2s": 0.0,
				"h2s_until": 0.0,
				"last_fg": 0.0,
				"fg_until": 0.0,
				"last_tank_hh": 0.0,
				"tank_hh_until": 0.0,
			}
		return g["pluspetrol_upsets_state"]

	try:
		if not bool(read(BASE_P + "/Config/SimEnabled")):
			write([
				(BASE_P + "/Diagnostics/LastRun", now_iso()),
				(BASE_P + "/Diagnostics/LastStatus", "Upsets script: Sim disabled"),
				(BASE_P + "/Diagnostics/LastError", "")
			])
			return

		s = st()
		now = time.time()

		# Cooldowns keep events sparse and plausible.
		# We use short "active windows" so you visibly see alarms/trips in the tag browser.
		events = []

		# --- Compressor trip (bearing / vibration) ---
		if (now > s["trip_until"]) and (now - s["last_trip"] > 900) and (random.random() < 0.06):
			s["last_trip"] = now
			s["trip_until"] = now + random.randint(40, 90)
			events.append(("CompressorTrip", True))

		trip_active = (now <= s["trip_until"])
		if trip_active:
			events.extend([
				(BASE_P + "/Processing/Compressor01/Running", False),
				(BASE_P + "/Processing/Compressor01/Vibration_mm_s", float(clamp(8.0 + random.random() * 2.0, 0.0, 12.0))),
				(BASE_P + "/Processing/Compressor01/BearingTemp_C", float(clamp(95.0 + random.random() * 8.0, 20.0, 120.0))),
			])

		# --- ESD drill ---
		if (now > s["esd_until"]) and (now - s["last_esd"] > 1800) and (random.random() < 0.03):
			s["last_esd"] = now
			s["esd_until"] = now + random.randint(15, 35)
			events.append(("ESD", True))

		esd_active = (now <= s["esd_until"])
		if esd_active:
			events.extend([
				(BASE_S + "/Safety/ESD_Active", True),
				(BASE_P + "/Processing/Compressor01/Running", False),
				(BASE_P + "/Flare/FlareRate_kSm3_h", float(clamp(6.0 + random.random() * 3.0, 0.0, 12.0))),
			])
		else:
			# don't fight the base sim too much; just ensure ESD releases back to false
			events.append((BASE_S + "/Safety/ESD_Active", False))

		# --- H2S spike ---
		if (now > s["h2s_until"]) and (now - s["last_h2s"] > 1200) and (random.random() < 0.05):
			s["last_h2s"] = now
			s["h2s_until"] = now + random.randint(20, 60)
			events.append(("H2S", True))

		h2s_active = (now <= s["h2s_until"])
		if h2s_active:
			events.extend([
				(BASE_S + "/Safety/H2S_ppm", float(clamp(18.0 + random.random() * 35.0, 0.0, 80.0))),
			])

		# --- Fire & Gas alarm (short) ---
		if (now > s["fg_until"]) and (now - s["last_fg"] > 2400) and (random.random() < 0.02):
			s["last_fg"] = now
			s["fg_until"] = now + random.randint(10, 25)
			events.append(("FireGas", True))

		fg_active = (now <= s["fg_until"])
		if fg_active:
			events.extend([
				(BASE_S + "/Safety/FireGas_Alarm", True),
			])
		else:
			events.append((BASE_S + "/Safety/FireGas_Alarm", False))

		# --- Tank high-high scenario (e.g., offtake delayed) ---
		if (now > s["tank_hh_until"]) and (now - s["last_tank_hh"] > 1500) and (random.random() < 0.04):
			s["last_tank_hh"] = now
			s["tank_hh_until"] = now + random.randint(30, 90)
			events.append(("TankHighHigh", True))

		tank_hh_active = (now <= s["tank_hh_until"])
		if tank_hh_active:
			# push Tank01 up near 90–98% and force flare assist on
			events.extend([
				(BASE_P + "/Tanks/Tank01/Level_pct", float(clamp(90.0 + random.random() * 8.0, 0.0, 100.0))),
				(BASE_P + "/Flare/SmokelessAssist_On", True),
			])

		# Only write actual tag updates (ignore the tuple markers above)
		writes = []
		for e in events:
			if isinstance(e, tuple) and isinstance(e[0], basestring) and (e[0].startswith(BASE_P) or e[0].startswith(BASE_S)):
				writes.append(e)

		# Always update diagnostics
		writes.extend([
			(BASE_P + "/Diagnostics/LastRun", now_iso()),
			(BASE_P + "/Diagnostics/LastStatus",
			 "Upsets: trip=%s esd=%s h2s=%s fg=%s tankHH=%s" % (trip_active, esd_active, h2s_active, fg_active, tank_hh_active)),
			(BASE_P + "/Diagnostics/LastError", "")
		])

		write(writes)

	except Exception as e:
		try:
			write([
				(BASE + "/Diagnostics/LastRun", now_iso()),
				(BASE + "/Diagnostics/LastStatus", "Upsets ERROR"),
				(BASE + "/Diagnostics/LastError", repr(e))
			])
		except:
			pass


handleTimerEvent()


