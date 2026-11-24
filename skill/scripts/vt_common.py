"""Shared helpers for the voice-tasks scripts: config, secrets and time zone.

Nothing here talks to the network.
"""
import json
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(SKILL_DIR, "config.json")
ENV_PATH = os.path.join(SKILL_DIR, ".env")

DEFAULTS = {
    "notion_key_env": "NOTION_API_KEY",
    "tasks_database_id": "",
    "tasks_data_source_id": "",
    "tasks_url": "",
    "window": ["07:00", "22:00"],
    "buffer_min": 10,
    "time_zone": "",
    "whisper_model": "base",
    "areas": ["Sales", "Client", "Content", "Marketing", "Operations", "Admin", "Personal"],
}


def die(msg):
    sys.exit("voice-tasks: " + msg)


def load_config(required=True):
    """Return config.json merged over the defaults.

    required=False lets the planner run before setup is finished.
    """
    cfg = dict(DEFAULTS)
    if not os.path.exists(CONFIG_PATH):
        if required:
            die("config.json is missing. Copy config.example.json to config.json in "
                + SKILL_DIR + " (or run install.sh again), then fill it in.")
        return cfg
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            user = json.load(f)
    except ValueError as e:
        die("config.json is not valid JSON (" + str(e) + "). Fix it or copy config.example.json over it.")
    if not isinstance(user, dict):
        die("config.json must be a JSON object, like config.example.json.")
    for k, v in user.items():
        if not k.startswith("_"):
            cfg[k] = v
    return cfg


def save_config(updates):
    """Merge updates into config.json, keeping everything else the user wrote."""
    current = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                current = json.load(f)
        except ValueError as e:
            die("config.json is not valid JSON (" + str(e) + "). Fix it before running setup.")
    current.update(updates)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
        f.write("\n")


def read_env_file(name):
    if not os.path.exists(ENV_PATH):
        return ""
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                line = line[7:].lstrip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def notion_key(cfg, fatal=True):
    """Find the Notion key: environment variable first, then the skill's .env file."""
    name = cfg.get("notion_key_env") or "NOTION_API_KEY"
    val = os.environ.get(name, "").strip() or read_env_file(name)
    if not val and fatal:
        die("no Notion key found. Put " + name + "=<your key> in " + ENV_PATH
            + " (or export " + name + " in your shell). Create the key at "
            + "https://www.notion.so/profile/integrations")
    return val


def local_time_zone(cfg):
    """IANA zone from config, else the one this Mac is set to, else ''."""
    tz = (cfg.get("time_zone") or "").strip()
    if tz:
        return tz
    try:
        target = os.path.realpath("/etc/localtime")
        if "/zoneinfo/" in target:
            return target.split("/zoneinfo/", 1)[1]
    except OSError:
        pass
    return ""


def read_stdin_json(example):
    raw = sys.stdin.read() if not sys.stdin.isatty() else ""
    if not raw.strip():
        die("expected JSON on stdin, got nothing. Example: " + example)
    try:
        return json.loads(raw)
    except ValueError as e:
        die("the JSON on stdin is not valid (" + str(e) + ").")
