# Ignition Gateway Timer Script (Jython) - Manufacturing MES (TOP-LEVEL)
# Provider: manufacturing_mes
# Writes:   [manufacturing_mes]Manufacturing/Site01/...
# Reads:    [manufacturing] throughput + [manufacturing_qc] yield for coupling

import random, time

BASE_M = "[manufacturing_mes]Manufacturing/Site01"
BASE_P = "[manufacturing]Manufacturing/Site01"
BASE_Q = "[manufacturing_qc]Manufacturing/Site01"
DIAG = BASE_M + "/Diagnostics"
log = system.util.getLogger("manufacturing_site01.mes")


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
	g_hb = system.util.getGlobals()
	last_hb = float(g_hb.get("manufacturing_site01_mes_last_hb", 0.0) or 0.0)
	now_hb = time.time()
	if (now_hb - last_hb) >= 60.0:
		g_hb["manufacturing_site01_mes_last_hb"] = now_hb
		log.info("tick (heartbeat): mes timer executing")

	if not bool(read(BASE_M + "/Config/SimEnabled")):
		safe_write_diag("SKIP", "Sim disabled")
	else:
		g = system.util.getGlobals()
		st = g.get("manufacturing_mes_state")
		if st is None:
			st = {"last_ts": time.time(), "downtime_until": 0.0}
			g["manufacturing_mes_state"] = st

		now_s = time.time()
		dt = max(1.0, now_s - float(st.get("last_ts", now_s)))
		st["last_ts"] = now_s

		target = read_int(BASE_M + "/MES/Orders/TargetQty", 25000)
		good = read_int(BASE_M + "/MES/Orders/GoodCount", 0)
		rej = read_int(BASE_M + "/MES/Orders/RejectCount", 0)
		wip = read_int(BASE_M + "/MES/Orders/WIPCount", 0)
		status = str(read(BASE_M + "/MES/Orders/Status") or "RUNNING")

		press_running = read_bool(BASE_P + "/Pressing/Press01/Running", True)
		thru = read_float(BASE_P + "/Pressing/Press01/PartRate_parts_per_min", 14.0)
		yield_pct = read_float(BASE_Q + "/QC/Inspection/Vision01/Yield_pct", 98.0)

		downtime = read_bool(BASE_M + "/MES/Production/DowntimeActive", False)
		reason = str(read(BASE_M + "/MES/Production/DowntimeReason") or "")

		if (not downtime) and (random.random() < 0.04):
			downtime = True
			reason = random.choice(["Material staging", "Die cleaning", "QC hold review", "Minor adjustment"])
			st["downtime_until"] = now_s + random.randint(30, 120)
		if downtime and (now_s >= float(st.get("downtime_until", 0.0))):
			downtime = False
			reason = ""

		if good >= target:
			status = "COMPLETE"
			downtime = True
			reason = "Order complete"

		effective_rate = 0.0
		if (not downtime) and press_running and status == "RUNNING":
			effective_rate = thru

		parts = int(round((effective_rate / 60.0) * dt))
		parts = max(0, parts)

		p_good = clamp(yield_pct / 100.0, 0.0, 1.0)
		g_inc = 0
		r_inc = 0
		for _ in range(parts):
			if random.random() < p_good:
				g_inc += 1
			else:
				r_inc += 1

		wip = int(clamp(wip + int(random.gauss(0, 8)) + int(0.15 * parts) - int(0.1 * (g_inc + r_inc)), 0, 8000))
		good = min(target, good + g_inc)
		rej = rej + r_inc

		scrap_rate = 0.0
		if (good + rej) > 0:
			scrap_rate = 100.0 * float(rej) / float(good + rej)

		avail = 96.0 - (4.0 if downtime else 0.0) - (6.0 if not press_running else 0.0)
		perf = clamp(92.0 + 4.0 * (thru / 14.0) + random.gauss(0, 0.6), 70.0, 105.0)
		qual = clamp(yield_pct + random.gauss(0, 0.2), 75.0, 99.9)
		oee = clamp((avail * perf * qual) / 10000.0, 0.0, 99.9)

		system.tag.writeBlocking(
			[
				BASE_M + "/MES/Orders/GoodCount",
				BASE_M + "/MES/Orders/RejectCount",
				BASE_M + "/MES/Orders/WIPCount",
				BASE_M + "/MES/Orders/Status",
				BASE_M + "/MES/Production/Throughput_parts_per_min",
				BASE_M + "/MES/Production/ScrapRate_pct",
				BASE_M + "/MES/Production/DowntimeActive",
				BASE_M + "/MES/Production/DowntimeReason",
				BASE_M + "/MES/OEE/Availability_pct",
				BASE_M + "/MES/OEE/Performance_pct",
				BASE_M + "/MES/OEE/Quality_pct",
				BASE_M + "/MES/OEE/OEE_pct",
			],
			[
				int(good),
				int(rej),
				int(wip),
				str(status),
				float(thru),
				float(scrap_rate),
				bool(downtime),
				str(reason),
				float(clamp(avail, 0.0, 100.0)),
				float(clamp(perf, 0.0, 110.0)),
				float(clamp(qual, 0.0, 100.0)),
				float(oee),
			],
		)

		safe_write_diag("OK", "good=%d/%d rej=%d wip=%d" % (good, target, rej, wip))

except Exception as e:
	try:
		log.error("timer failed", e)
	except:
		pass
	safe_write_diag("ERROR", str(e))


