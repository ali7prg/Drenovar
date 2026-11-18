#!/usr/bin/env python3
"""Run a Blender (bpy) build script with a global cap on concurrent heavy jobs.

Usage: python3 forest_rescue/blender/run_limited.py <script.py> [args...]
Env: FRLIB_SLOTS (default 3). Runs under xvfb-run so EEVEE/Workbench work headless.
"""
import fcntl, os, subprocess, sys, time

SLOTS = int(os.environ.get("FRLIB_SLOTS", "3"))
LOCKDIR = "/tmp/frlib_slots"
PY = "/opt/tools/blender-venv/bin/python"
HERE = os.path.dirname(os.path.abspath(__file__))

def main():
    os.makedirs(LOCKDIR, exist_ok=True)
    fh = None
    waited = 0.0
    while fh is None:
        for i in range(SLOTS):
            f = open(os.path.join(LOCKDIR, f"slot{i}.lock"), "w")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fh = f
                break
            except BlockingIOError:
                f.close()
        if fh is None:
            time.sleep(2.0)
            waited += 2.0
    if waited:
        print(f"[run_limited] waited {waited:.0f}s for a slot", flush=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = HERE + os.pathsep + env.get("PYTHONPATH", "")
    cmd = ["xvfb-run", "-a", "-s", "-screen 0 1280x720x24", PY, "-u"] + sys.argv[1:]
    rc = subprocess.call(cmd, env=env)
    sys.exit(rc)

if __name__ == "__main__":
    main()
