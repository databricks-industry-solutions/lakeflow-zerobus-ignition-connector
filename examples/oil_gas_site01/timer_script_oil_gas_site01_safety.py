# Ignition Gateway Timer Script (Jython) - OilGas Safety (TOP-LEVEL)
# Provider: oil_gas_safety
# Writes:   [oil_gas_safety]OilGas/Site01/Safety/...

import random

BASE = "[oil_gas_safety]OilGas/Site01"
DIAG = BASE + "/Diagnostics"


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

	if not bool(read(BASE + "/Config/SimEnabled")):
		safe_write_diag("SKIP", "Sim disabled")
	else:
		esd = bool(read(BASE + "/Safety/ESD_Active"))
		firegas = bool(read(BASE + "/Safety/FireGas_Alarm"))

		h2s = float(read(BASE + "/Safety/H2S_ppm"))
		if h2s < 10.0:
			h2s = clamp(2.0 + random.gauss(0, 0.5), 0.0, 12.0)

		if firegas and random.random() < 0.35:
			firegas = False

		system.tag.writeBlocking(
			[
				BASE + "/Safety/H2S_ppm",
				BASE + "/Safety/FireGas_Alarm",
				BASE + "/Safety/ESD_Active",
			],
			[
				float(h2s),
				bool(firegas),
				bool(esd),
			],
		)

		safe_write_diag("OK", "Safety: esd=%s fg=%s h2s=%.1f" % (esd, firegas, h2s))

except Exception as e:
	safe_write_diag("ERROR", str(e))


