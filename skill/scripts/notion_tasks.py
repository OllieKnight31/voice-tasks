#!/usr/bin/env python3
"""Create and update tasks in your Notion tasks database.

  setup <page url or id>     -> creates a "Voice Tasks" database inside that page and saves its ids
                                to config.json (the page must be shared with your integration)
  use <database url or id>   -> points the skill at a database you already have and saves its ids
  check                      -> verifies the key and the database, prints which columns were found
  create  < tasks.json       -> prints [{key, page_id, url}]
      tasks.json: [{"key","title","tier","area","minutes","due","notes"}]
  schedule < updates.json    -> sets Scheduled + Calendar link
      updates.json: [{"page_id","start","end","calendar_link","time_zone"}]

Add --dry-run to create or schedule to print what would be sent without contacting Notion.
The Notion key is read from the environment or from the .env file in the skill folder.
It is never printed.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vt_common import (CONFIG_PATH, die, load_config, local_time_zone, notion_key,  # noqa: E402
                       read_stdin_json, save_config)

API = "https://api.notion.com/v1/"
NOTION_VERSION = "2026-03-11"
URGENCY = {1: "🔥 P0", 2: "⚡ P1", 3: "📌 P2", 4: "🌱 P3", 5: "🌱 P3"}
STATUS_NEW = "Not Started"
SOURCE = "Voice note"
HINTS = {
    401: "Notion rejected the key. Check the value in the .env file in the skill folder.",
    403: "The integration is not allowed to do this. Give it read, update and insert content capabilities.",
    404: "Notion cannot see that page or database. Open it in Notion, click the three dots, "
         "Connections, and add your integration. Then check the id in config.json.",
    429: "Notion is rate limiting. Wait a minute and run it again.",
}

ME = os.path.abspath(__file__)
CFG = None


def cfg():
    global CFG
    if CFG is None:
        CFG = load_config()
    return CFG


def api(method, path, body=None):
    r = urllib.request.Request(API + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={"Authorization": "Bearer " + notion_key(cfg()),
                                        "Notion-Version": NOTION_VERSION,
                                        "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        die("Notion " + str(e.code) + ": " + detail + "\n" + HINTS.get(e.code, ""))
    except urllib.error.URLError as e:
        die("could not reach Notion (" + str(e.reason) + "). Check your internet connection.")


def notion_id(text, what):
    """Pull a 32 character Notion id out of a URL or a pasted id."""
    path = str(text).strip().split("?", 1)[0].split("#", 1)[0].rstrip("/")
    # The id is the last 32 hex characters of the last path segment (page titles come before it).
    hit = re.search(r"[0-9a-fA-F]{32}$", path.split("/")[-1].replace("-", ""))
    if not hit:
        die("could not find a Notion id in " + repr(text) + ". Paste the " + what
            + " link (Share, Copy link) or its 32 character id.")
    h = hit.group(0).lower()
    return "-".join([h[:8], h[8:12], h[12:16], h[16:20], h[20:]])


def data_source_id():
    ds = (cfg().get("tasks_data_source_id") or "").strip()
    if not ds:
        die("tasks_data_source_id is empty in " + CONFIG_PATH + ". Run one of:\n"
            "  python3 " + ME + " setup <link to a Notion page>\n"
            "  python3 " + ME + " use <link to your tasks database>")
    return ds


def schema():
    return api("GET", "data_sources/" + data_source_id()).get("properties", {})


def default_schema():
    """The columns `setup` creates. Also used for --dry-run."""
    def sel(names):
        return {"select": {"options": [{"name": n} for n in names]}}
    return {
        "Task": {"title": {}},
        "Status": sel([STATUS_NEW, "In Progress", "Done"]),
        "Urgency": sel(["🔥 P0", "⚡ P1", "📌 P2", "🌱 P3"]),
        "Area": sel([str(a) for a in cfg().get("areas") or []]),
        "Due Date": {"date": {}},
        "Scheduled": {"date": {}},
        "Est. minutes": {"number": {"format": "number"}},
        "Source": sel([SOURCE]),
        "Notes": {"rich_text": {}},
        "Calendar link": {"url": {}},
    }


def typed(props):
    """Add the "type" field Notion returns, so default_schema() looks like a real schema."""
    return {k: dict(v, type=next(iter(v))) for k, v in props.items()}


def rt(s):
    return [{"type": "text", "text": {"content": str(s)[:1900]}}] if s else []


def title_prop(avail):
    for name, p in avail.items():
        if p.get("type") == "title":
            return name
    die("the database has no title column, which should be impossible. Run check and review the ids in config.json.")


def has(avail, name, kind):
    return avail.get(name, {}).get("type") == kind


def choice(avail, name, value):
    """Value for a select or status column, or None when it cannot be set safely."""
    p = avail.get(name, {})
    if p.get("type") == "select":
        return {"select": {"name": value}}
    if p.get("type") == "status":
        options = [o.get("name") for o in p.get("status", {}).get("options", [])]
        if value in options:
            return {"status": {"name": value}}
    return None


def tier_of(t):
    try:
        return min(5, max(1, int(t.get("tier") or 3)))
    except (TypeError, ValueError):
        return 3


def build_page(t, avail):
    if not isinstance(t, dict) or not str(t.get("title") or "").strip():
        die("every task needs a title. Got: " + json.dumps(t, ensure_ascii=False)[:200])
    tier = tier_of(t)
    p = {title_prop(avail): {"title": rt(t["title"])}}
    for name, value in (("Status", STATUS_NEW), ("Urgency", URGENCY[tier]),
                        ("Area", t.get("area")), ("Source", SOURCE)):
        if value:
            c = choice(avail, name, str(value))
            if c:
                p[name] = c
    if has(avail, "Due Date", "date") and t.get("due"):
        p["Due Date"] = {"date": {"start": str(t["due"])}}
    if has(avail, "Est. minutes", "number") and t.get("minutes"):
        try:
            p["Est. minutes"] = {"number": int(float(t["minutes"]))}
        except (TypeError, ValueError):
            pass
    if has(avail, "Notes", "rich_text") and t.get("notes"):
        p["Notes"] = {"rich_text": rt(t["notes"])}
    ds = (cfg().get("tasks_data_source_id") or "").strip() or "<not set yet>"
    return {"parent": {"type": "data_source_id", "data_source_id": ds},
            "properties": p, "icon": {"type": "emoji", "emoji": "💰" if tier == 1 else "🎙️"}}


def create(tasks, dry=False):
    if not isinstance(tasks, list):
        die("create expects a JSON list of tasks.")
    avail = typed(default_schema()) if dry else schema()
    bodies = [build_page(t, avail) for t in tasks]
    if dry:
        print(json.dumps({"dry_run": True, "would_create": bodies}, indent=1, ensure_ascii=False))
        return
    out = []
    for t, body in zip(tasks, bodies):
        pg = api("POST", "pages", body)
        out.append({"key": t.get("key"), "page_id": pg["id"], "url": pg.get("url")})
    print(json.dumps(out, indent=1))


def build_update(u, avail):
    if not isinstance(u, dict) or not u.get("page_id"):
        die("every update needs a page_id. Got: " + json.dumps(u, ensure_ascii=False)[:200])
    p = {}
    if has(avail, "Scheduled", "date") and u.get("start"):
        date = {"start": str(u["start"])[:19]}
        if u.get("end"):
            date["end"] = str(u["end"])[:19]
        tz = u.get("time_zone") or local_time_zone(cfg())
        if tz:
            date["time_zone"] = tz
        p["Scheduled"] = {"date": date}
    if has(avail, "Calendar link", "url") and u.get("calendar_link"):
        p["Calendar link"] = {"url": str(u["calendar_link"])}
    return p


def schedule(updates, dry=False):
    if not isinstance(updates, list):
        die("schedule expects a JSON list of updates.")
    avail = typed(default_schema()) if dry else schema()
    bodies = [(u, build_update(u, avail)) for u in updates]
    if dry:
        print(json.dumps({"dry_run": True, "would_update": [{"page_id": u["page_id"], "properties": p}
                                                           for u, p in bodies]}, indent=1, ensure_ascii=False))
        return
    done = 0
    for u, p in bodies:
        if p:
            api("PATCH", "pages/" + str(u["page_id"]), {"properties": p})
            done += 1
    print("updated " + str(done) + " of " + str(len(updates)))
    if done < len(updates):
        print("some tasks were not updated: the database has no Scheduled (date) or Calendar link (url) column.")


def remember(db):
    sources = db.get("data_sources") or []
    if not sources:
        die("Notion returned no data source for that database. Is the link a database (not a page)?")
    url = db.get("url") or ""
    save_config({"tasks_database_id": db.get("id", ""), "tasks_data_source_id": sources[0]["id"], "tasks_url": url})
    print("Saved to " + CONFIG_PATH)
    print("Tasks database: " + url)
    if len(sources) > 1:
        print("Note: that database has " + str(len(sources)) + " data sources. Using the first, "
              + repr(sources[0].get("name")) + ". Edit tasks_data_source_id in config.json to pick another.")


def setup(page):
    if (cfg().get("tasks_data_source_id") or "").strip():
        die("config.json already points at a tasks database (" + str(cfg().get("tasks_url")) + "). "
            "Clear tasks_data_source_id in config.json first if you really want a new one.")
    db = api("POST", "databases", {
        "parent": {"type": "page_id", "page_id": notion_id(page, "page")},
        "title": rt("Voice Tasks"),
        "icon": {"type": "emoji", "emoji": "🎙️"},
        "initial_data_source": {"properties": default_schema()},
    })
    remember(db)


def use(database):
    remember(api("GET", "databases/" + notion_id(database, "database")))


WANTED = [("Status", ("select", "status")), ("Urgency", ("select",)), ("Area", ("select",)),
          ("Due Date", ("date",)), ("Scheduled", ("date",)), ("Est. minutes", ("number",)),
          ("Source", ("select",)), ("Notes", ("rich_text",)), ("Calendar link", ("url",))]


def check():
    avail = schema()
    print("Notion key: found")
    print("Database reachable: yes (" + str(cfg().get("tasks_url") or data_source_id()) + ")")
    print("Title column: " + title_prop(avail))
    for name, kinds in WANTED:
        got = avail.get(name, {}).get("type")
        if got in kinds:
            note = "ok"
            if got == "status" and STATUS_NEW not in [o.get("name") for o in avail[name]["status"].get("options", [])]:
                note = 'ok, but it has no "' + STATUS_NEW + '" option, so Status will be left at its default'
        elif got:
            note = "wrong type (" + got + ", expected " + " or ".join(kinds) + "), will be skipped"
        else:
            note = "missing, will be skipped"
        print("  " + name + ": " + note)
    areas = [o.get("name") for o in avail.get("Area", {}).get("select", {}).get("options", [])]
    if areas:
        print("Area options: " + ", ".join(areas))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv[1:]
    cmd = args[0] if args else "help"
    if cmd in ("-h", "--help", "help"):
        print(__doc__.strip())
    elif cmd == "create":
        create(read_stdin_json('[{"key":"t1","title":"Follow up with leads","tier":1,"minutes":45,"due":"2026-11-13"}]'), dry)
    elif cmd == "schedule":
        schedule(read_stdin_json('[{"page_id":"...","start":"2026-11-13T07:00:00","end":"2026-11-13T07:45:00"}]'), dry)
    elif cmd == "check":
        check()
    elif cmd in ("setup", "use"):
        if len(args) < 2:
            die(cmd + " needs a Notion link or id. Example: python3 " + ME + " " + cmd + " <link>")
        (setup if cmd == "setup" else use)(args[1])
    else:
        die("unknown command " + repr(cmd) + ". Run with --help.")
