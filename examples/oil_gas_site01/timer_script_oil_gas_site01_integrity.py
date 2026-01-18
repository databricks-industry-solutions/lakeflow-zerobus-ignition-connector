# Ignition Gateway Timer Script (Jython) - OilGas Integrity (TOP-LEVEL)
# Provider: oil_gas_integrity
# Writes:   [oil_gas_integrity]OilGas/Site01/Integrity/...

import random

BASE = "[oil_gas_integrity]OilGas/Site01"
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
		# NOTE: we don't treat TickCount as real days; this is just to make the demo lively.
		tick = int(read(DIAG + "/TickCount") or 0) + 1

		corr = float(read(BASE + "/Integrity/CorrosionRate_mm_per_yr"))
		pig = int(read(BASE + "/Integrity/Pigging_DaysSince"))
		leak = bool(read(BASE + "/Integrity/LeakSuspected"))

		corr = clamp(corr + random.gauss(0, 0.002), 0.02, 0.45)

		# With a 10s timer: 1 "day" every ~360 ticks (~1 hour)
		if tick % 360 == 0:
			pig = pig + 1

		if (not leak) and random.random() < 0.01:
			leak = True
		if leak and random.random() < 0.12:
			leak = False

		system.tag.writeBlocking(
			[
				BASE + "/Integrity/CorrosionRate_mm_per_yr",
				BASE + "/Integrity/Pigging_DaysSince",
				BASE + "/Integrity/LeakSuspected",
			],
			[
				float(corr),
				int(pig),
				bool(leak),
			],
		)

		safe_write_diag("OK", "Integrity: corr=%.2f pigDays=%d leak=%s" % (corr, pig, leak))

except Exception as e:
	safe_write_diag("ERROR", str(e))


