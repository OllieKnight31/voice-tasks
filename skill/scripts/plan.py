#!/usr/bin/env python3
"""Deterministic day planner: slot prioritised tasks into free time around existing calendar events.

stdin JSON:
{
  "date": "2026-11-13",
  "window": ["07:00", "22:00"],          # optional, defaults to config.json
  "buffer_min": 10,                      # optional, gap after every block, defaults to config.json
  "time_zone": "Europe/London",          # optional, defaults to config.json, then this Mac's clock
  "busy": [["2026-11-13T09:00:00", "2026-11-13T10:00:00"], ...],   # local, no offset
  "tasks": [{"key": "t1", "title": "...", "tier": 1, "minutes": 45,
             "fixed_start": "2026-11-13T15:00:00" (optional), "order": 0}]
}
stdout JSON: {"scheduled": [{key, start, end}], "unscheduled": [key, ...]}

Rules: fixed-time tasks are placed first at their time. Then tasks go in tier order
(1 = revenue first), keeping the order they were spoken in within a tier, each into the
earliest free gap that fits. Nothing is placed in the past when planning for today.

Needs no network and no accounts. Run with --help to see this text.
"""
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vt_common import die, load_config, local_time_zone, read_stdin_json  # noqa: E402

FMT = "%Y-%m-%dT%H:%M:%S"
EXAMPLE = '{"date":"2026-11-13","busy":[],"tasks":[{"key":"t1","tier":1,"minutes":45}]}'


def parse_dt(value, what):
    try:
        return datetime.fromisoformat(str(value)[:19])
    except ValueError:
        die(what + " is not a valid date and time: " + repr(value) + " (use YYYY-MM-DDTHH:MM:SS).")


def as_int(value, default):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def now_in(tz_name):
    """Current wall-clock time in the planning time zone (naive)."""
    if tz_name:
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)
        except Exception:
            die("time zone " + repr(tz_name) + " is not a valid IANA name (example: Europe/London). "
                "Fix time_zone in config.json.")
    return datetime.now()


def plan(d, cfg, now=None):
    if not isinstance(d, dict):
        die("the input must be a JSON object. Example: " + EXAMPLE)
    day = d.get("date")
    if not day:
        die('"date" is missing from the input (use YYYY-MM-DD).')
    window = d.get("window") or cfg.get("window") or ["07:00", "22:00"]
    if not (isinstance(window, list) and len(window) == 2):
        die('"window" must be two times, like ["07:00", "22:00"].')
    ws = parse_dt(str(day) + "T" + str(window[0])[:5] + ":00", "window start")
    we = parse_dt(str(day) + "T" + str(window[1])[:5] + ":00", "window end")
    if we <= ws:
        die("the window must end after it starts (got " + str(window) + ").")
    if now is None:
        now = now_in(d.get("time_zone") or local_time_zone(cfg))
    if ws.date() == now.date() and now > ws:
        ws = (now + timedelta(minutes=15 - now.minute % 15)).replace(second=0, microsecond=0)
    buf_default = as_int(cfg.get("buffer_min"), 10)
    buf = timedelta(minutes=max(0, as_int(d.get("buffer_min"), buf_default)))

    busy = []
    for pair in d.get("busy") or []:
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2):
            die('each "busy" entry must be [start, end], got ' + repr(pair))
        busy.append((parse_dt(pair[0], "busy start"), parse_dt(pair[1], "busy end")))
    busy.sort()

    def free(start, end):
        for b0, b1 in busy:
            if start < b1 + buf and end + buf > b0:
                return False
        return ws <= start and end <= we

    tasks = d.get("tasks")
    if not isinstance(tasks, list):
        die('"tasks" must be a list. Example: ' + EXAMPLE)
    for i, t in enumerate(tasks):
        if not isinstance(t, dict) or "key" not in t:
            die("task number " + str(i + 1) + ' needs a "key".')

    out, left = [], []
    for t in [t for t in tasks if t.get("fixed_start")]:
        s = parse_dt(t["fixed_start"], "fixed_start of task " + str(t["key"]))
        e = s + timedelta(minutes=max(15, as_int(t.get("minutes"), 30)))
        out.append({"key": t["key"], "start": s.strftime(FMT), "end": e.strftime(FMT), "fixed": True})
        busy.append((s, e))
        busy.sort()
    flexible = [t for t in tasks if not t.get("fixed_start")]
    flexible.sort(key=lambda t: (as_int(t.get("tier"), 3), as_int(t.get("order"), 0)))
    for t in flexible:
        dur = timedelta(minutes=max(15, as_int(t.get("minutes"), 30)))
        s = ws
        placed = False
        while s + dur <= we:
            if free(s, s + dur):
                out.append({"key": t["key"], "start": s.strftime(FMT), "end": (s + dur).strftime(FMT)})
                busy.append((s, s + dur))
                busy.sort()
                placed = True
                break
            s += timedelta(minutes=15)
        if not placed:
            left.append(t["key"])
    out.sort(key=lambda x: x["start"])
    return {"scheduled": out, "unscheduled": left}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__.strip())
        sys.exit(0)
    data = read_stdin_json(EXAMPLE)
    print(json.dumps(plan(data, load_config(required=False)), indent=1))
