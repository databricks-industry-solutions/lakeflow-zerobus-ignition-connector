# Ignition Gateway Timer Script (Jython) - OilGas Upsets (TOP-LEVEL)
# Provider: oil_gas (writes some SCADA tags) + oil_gas_safety (writes safety tags)

import random, time

BASE_P = "[oil_gas]OilGas/Site01"
BASE_S = "[oil_gas_safety]OilGas/Site01"
DIAG = BASE_P + "/Diagnostics"


def now_iso():
	return system.date.format(system.date.now(), "yyyy-MM-dd HH:mm:ss")


def clamp(x, lo, hi):
	return max(lo, min(hi, x))


def read(path):
	return system.tag.readBlocking([path])[0].value


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

	if not bool(read(BASE_P + "/Config/SimEnabled")):
		safe_write_diag("SKIP", "Sim disabled")
	else:
		g = system.util.getGlobals()
		st = g.get("oil_gas_upsets_state")
		if st is None:
			st = {
				"last_trip": 0.0, "trip_until": 0.0,
				"last_esd": 0.0, "esd_until": 0.0,
				"last_h2s": 0.0, "h2s_until": 0.0,
				"last_fg": 0.0, "fg_until": 0.0,
				"last_tank_hh": 0.0, "tank_hh_until": 0.0,
			}
			g["oil_gas_upsets_state"] = st

		now_s = time.time()
		writes = []

		# Compressor trip
		if (now_s > st["trip_until"]) and (now_s - st["last_trip"] > 900) and (random.random() < 0.06):
			st["last_trip"] = now_s
			st["trip_until"] = now_s + random.randint(40, 90)
		trip_active = (now_s <= st["trip_until"])
		if trip_active:
			writes.extend([
				(BASE_P + "/Processing/Compressor01/Running", False),
				(BASE_P + "/Processing/Compressor01/Vibration_mm_s", float(clamp(8.0 + random.random() * 2.0, 0.0, 12.0))),
				(BASE_P + "/Processing/Compressor01/BearingTemp_C", float(clamp(95.0 + random.random() * 8.0, 20.0, 120.0))),
			])

		# ESD drill
		if (now_s > st["esd_until"]) and (now_s - st["last_esd"] > 1800) and (random.random() < 0.03):
			st["last_esd"] = now_s
			st["esd_until"] = now_s + random.randint(15, 35)
		esd_active = (now_s <= st["esd_until"])
		if esd_active:
			writes.extend([
				(BASE_S + "/Safety/ESD_Active", True),
				(BASE_P + "/Processing/Compressor01/Running", False),
				(BASE_P + "/Flare/FlareRate_kSm3_h", float(clamp(6.0 + random.random() * 3.0, 0.0, 12.0))),
			])
		else:
			writes.append((BASE_S + "/Safety/ESD_Active", False))

		# H2S spike
		if (now_s > st["h2s_until"]) and (now_s - st["last_h2s"] > 1200) and (random.random() < 0.05):
			st["last_h2s"] = now_s
			st["h2s_until"] = now_s + random.randint(20, 60)
		h2s_active = (now_s <= st["h2s_until"])
		if h2s_active:
			writes.append((BASE_S + "/Safety/H2S_ppm", float(clamp(18.0 + random.random() * 35.0, 0.0, 80.0))))

		# Fire & gas alarm
		if (now_s > st["fg_until"]) and (now_s - st["last_fg"] > 2400) and (random.random() < 0.02):
			st["last_fg"] = now_s
			st["fg_until"] = now_s + random.randint(10, 25)
		fg_active = (now_s <= st["fg_until"])
		writes.append((BASE_S + "/Safety/FireGas_Alarm", bool(fg_active)))

		# Tank high-high
		if (now_s > st["tank_hh_until"]) and (now_s - st["last_tank_hh"] > 1500) and (random.random() < 0.04):
			st["last_tank_hh"] = now_s
			st["tank_hh_until"] = now_s + random.randint(30, 90)
		tank_hh_active = (now_s <= st["tank_hh_until"])
		if tank_hh_active:
			writes.extend([
				(BASE_P + "/Tanks/Tank01/Level_pct", float(clamp(90.0 + random.random() * 8.0, 0.0, 100.0))),
				(BASE_P + "/Flare/SmokelessAssist_On", True),
			])

		if writes:
			system.tag.writeBlocking([p for (p, _) in writes], [v for (_, v) in writes])

		safe_write_diag(
			"OK",
			"Upsets: trip=%s esd=%s h2s=%s fg=%s tankHH=%s" % (trip_active, esd_active, h2s_active, fg_active, tank_hh_active),
		)

except Exception as e:
	safe_write_diag("ERROR", str(e))


