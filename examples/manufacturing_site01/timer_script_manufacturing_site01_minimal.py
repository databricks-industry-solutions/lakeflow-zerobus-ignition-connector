# Minimal Manufacturing script to prove writes are working (and show failures loudly).
# Expected tag root:
#   [manufacturing]Manufacturing/Site01/...
#
# Create a Gateway Timer Event:
#   - Script: this file
#   - Delay: 1000ms
#   - Enabled: true

import random

# Bind the Ignition scripting module once to avoid any odd scoping/shadowing issues.
_sys = system
log = _sys.util.getLogger("manufacturing_site01.minimal")

BASE = "[manufacturing]Manufacturing/Site01"
TICK = BASE + "/Diagnostics/TickCount"
LAST_RUN = BASE + "/Diagnostics/LastRun"
LAST_STATUS = BASE + "/Diagnostics/LastWriteStatus"
LAST_ERROR = BASE + "/Diagnostics/LastError"
TOGGLE = BASE + "/Test/Toggle"
RANDV = BASE + "/Test/RandomValue"


def _now_iso():
	# Keep it simple and readable in the tag browser
	return _sys.date.format(_sys.date.now(), "yyyy-MM-dd HH:mm:ss")


def _write_blocking(paths, values):
	# writeBlocking returns a list of QualityCode objects
	return _sys.tag.writeBlocking(paths, values)


try:
	# Heartbeat in gateway logs (so we know the script is executing)
	log.info("tick: minimal timer executing")

	# Read current values
	read_paths = [TICK, TOGGLE]
	read_results = _sys.tag.readBlocking(read_paths)

	tick_val = read_results[0].value
	toggle_val = read_results[1].value

	# Compute next values
	next_tick = int(tick_val or 0) + 1
	next_toggle = (not bool(toggle_val))
	next_rand = float(random.random() * 100.0)

	# Write values
	write_paths = [TICK, LAST_RUN, TOGGLE, RANDV, LAST_ERROR]
	write_vals = [next_tick, _now_iso(), next_toggle, next_rand, ""]
	qualities = _write_blocking(write_paths, write_vals)

	# Summarize write success/failure
	bad = []
	for i in range(len(write_paths)):
		q = qualities[i]
		# QualityCode supports isGood() in Ignition scripting
		if hasattr(q, "isGood") and (not q.isGood()):
			bad.append("%s=%s" % (write_paths[i], str(q)))

	if len(bad) == 0:
		_write_blocking([LAST_STATUS], ["OK: wrote TickCount/Toggle/RandomValue"])
	else:
		msg = "WRITE_FAILED: " + "; ".join(bad)
		_write_blocking([LAST_STATUS, LAST_ERROR], [msg, msg])
		log.warn(msg)

except Exception as e:
	msg = "EXCEPTION: %s" % str(e)
	try:
		_write_blocking([LAST_STATUS, LAST_ERROR], [msg, msg])
	except:
		pass
	log.error(msg)

