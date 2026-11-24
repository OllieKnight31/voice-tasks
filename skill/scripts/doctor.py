#!/usr/bin/env python3
"""Check that voice-tasks is set up. Offline by default; add --online to also test Notion.

Prints one line per check and exits 1 if anything that blocks a run is missing.
Never prints the Notion key.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vt_common import (CONFIG_PATH, ENV_PATH, SKILL_DIR, load_config, local_time_zone,  # noqa: E402
                       notion_key)

HERE = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(SKILL_DIR, ".venv", "bin", "python")
problems = 0


def line(ok, label, detail=""):
    global problems
    if ok is False:
        problems += 1
    mark = {True: "OK  ", False: "FAIL", None: "NOTE"}[ok]
    print(mark + "  " + label + ((": " + detail) if detail else ""))


def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__.strip())
        return 0
    line(sys.version_info >= (3, 9), "Python 3.9 or newer", sys.version.split()[0])
    if not os.path.exists(CONFIG_PATH):
        line(False, "config.json", "missing. Copy config.example.json to config.json in " + SKILL_DIR)
        cfg = load_config(required=False)
    else:
        cfg = load_config()
        line(True, "config.json", "found")

    key = notion_key(cfg, fatal=False)
    name = cfg.get("notion_key_env") or "NOTION_API_KEY"
    line(bool(key), "Notion key", "found" if key else "missing. Put " + name + "=<your key> in " + ENV_PATH)

    ds = (cfg.get("tasks_data_source_id") or "").strip()
    line(bool(ds), "Notion tasks database",
         "set" if ds else "not set. Run: python3 " + os.path.join(HERE, "notion_tasks.py") + " setup <link to a Notion page>")

    w = cfg.get("window")
    ok = isinstance(w, list) and len(w) == 2 and all(isinstance(x, str) and len(x) == 5 and x[2] == ":" for x in w) and w[0] < w[1]
    line(ok, "Day window", str(w) if ok else 'must look like ["07:00", "22:00"], got ' + repr(w))

    tz = local_time_zone(cfg)
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(tz)
        line(True, "Time zone", tz + ("" if cfg.get("time_zone") else " (from this Mac's clock)"))
    except Exception:
        line(False, "Time zone", repr(tz) + " is not a valid IANA name. Set time_zone in config.json, for example Europe/London")

    engine = False
    for py in (sys.executable, VENV_PY):
        if os.path.exists(py):
            try:
                if subprocess.run([py, "-c", "import faster_whisper"], capture_output=True, timeout=120).returncode == 0:
                    engine = True
                    break
            except (OSError, subprocess.TimeoutExpired):
                pass
    line(True if engine else None, "Transcription engine",
         "installed" if engine else "not installed. Voice notes will not work until you run "
         "`bash install.sh --with-transcription`. Typed or pasted task lists work without it.")

    line(None, "Google Calendar", "cannot be checked from a script. In Claude Code run /mcp and look for "
         "the Google Calendar connector. Connect it at https://claude.ai/settings/connectors")

    if "--online" in sys.argv[1:] and key and ds:
        r = subprocess.run([sys.executable, os.path.join(HERE, "notion_tasks.py"), "check"],
                           capture_output=True, text=True)
        line(r.returncode == 0, "Notion live check", (r.stdout or r.stderr).strip().replace("\n", "\n      "))

    print("")
    print("All set." if not problems else str(problems) + " thing(s) to fix above.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
