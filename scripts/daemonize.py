#!/usr/bin/env python3
"""Double-fork daemonizer with auto-restart for Sangam agents.
Usage: python scripts/daemonize.py agents.intake_agent logs/agent_intake.log
"""
import os, sys, subprocess, time

module = sys.argv[1]
logfile = os.path.abspath(sys.argv[2])
repo = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
uv = os.path.expanduser("~/.local/bin/uv")

pid = os.fork()
if pid > 0:
    os.waitpid(pid, 0)
    os._exit(0)

os.setsid()

pid2 = os.fork()
if pid2 > 0:
    os._exit(0)

try:
    fd_null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(fd_null, 0)
    os.close(fd_null)

    fd_log = os.open(logfile, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.dup2(fd_log, 1)
    os.dup2(fd_log, 2)
    os.close(fd_log)

    os.chdir(repo)

    # Restart loop: Band WebSocket closes with code 1000 (SDK doesn't reconnect).
    # Restart the agent process automatically so it reconnects.
    while True:
        ret = subprocess.call([uv, "run", "python", "-m", module])
        # Brief delay before restart to avoid hammering the API on crash loops
        time.sleep(3)

except Exception as e:
    with open(logfile, "a") as f:
        f.write(f"DAEMON ERROR: {e}\n")
    os._exit(1)
