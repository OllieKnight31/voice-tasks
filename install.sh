#!/bin/bash
# Installs the voice-tasks skill for Claude Code.
#   bash install.sh                        install or update the skill
#   bash install.sh --with-transcription   also install the local speech-to-text engine (about 250 MB)
# Safe to run again: it never overwrites your config.json or .env.
set -euo pipefail

WITH_TRANSCRIPTION=0
for arg in "$@"; do
  case "$arg" in
    --with-transcription) WITH_TRANSCRIPTION=1 ;;
    -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skill"
DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/voice-tasks"
MARKER=".installed-by-voice-tasks-installer"

if [ ! -f "$SRC/SKILL.md" ]; then
  echo "Cannot find the skill folder next to this script (looked in $SRC)." >&2
  echo "Run install.sh from inside the folder you downloaded, with the skill folder beside it." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 was not found. Install it by running: xcode-select --install" >&2
  echo "Then run this installer again." >&2
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)'; then
  echo "python3 is too old ($(python3 --version 2>&1)). Version 3.9 or newer is needed." >&2
  exit 1
fi

# A voice-tasks skill that this installer did not put there is backed up before anything is copied.
if [ -d "$DEST" ] && [ ! -f "$DEST/$MARKER" ]; then
  BACKUP="$(dirname "$(dirname "$DEST")")/skill-backups/voice-tasks-$(date +%Y%m%d-%H%M%S)"
  echo "Found an existing voice-tasks skill. Backing it up to $BACKUP"
  mkdir -p "$(dirname "$BACKUP")"
  cp -R "$DEST" "$BACKUP"
fi

mkdir -p "$DEST/scripts"
cp "$SRC/SKILL.md" "$SRC/config.example.json" "$SRC/env.example" "$DEST/"
cp "$SRC"/scripts/*.py "$DEST/scripts/"
touch "$DEST/$MARKER"
echo "Installed the skill to $DEST"

if [ -f "$DEST/config.json" ]; then
  echo "Kept your existing config.json"
else
  cp "$SRC/config.example.json" "$DEST/config.json"
  echo "Created config.json"
fi

if [ -f "$DEST/.env" ]; then
  echo "Kept your existing .env"
else
  cp "$SRC/env.example" "$DEST/.env"
  echo "Created .env (paste your Notion key into it)"
fi
chmod 600 "$DEST/.env"

if [ "$WITH_TRANSCRIPTION" = "1" ]; then
  echo "Installing the transcription engine into $DEST/.venv (about 250 MB, takes a few minutes)"
  if [ ! -x "$DEST/.venv/bin/python" ]; then
    python3 -m venv "$DEST/.venv"
  fi
  "$DEST/.venv/bin/python" -m pip install --quiet --upgrade pip
  "$DEST/.venv/bin/python" -m pip install --quiet "faster-whisper>=1.1.0"
  if "$DEST/.venv/bin/python" -c 'import faster_whisper' 2>/dev/null; then
    echo "Transcription engine installed"
  else
    echo "The transcription engine did not install correctly. Typed task lists will still work." >&2
  fi
fi

echo ""
echo "Setup check:"
python3 "$DEST/scripts/doctor.py" || true

cat <<NEXT

Next steps (details in README.md):
  1. Paste your Notion key into:  $DEST/.env
  2. Create the tasks database:   python3 "$DEST/scripts/notion_tasks.py" setup "<link to a Notion page>"
  3. Connect Google Calendar at   https://claude.ai/settings/connectors
  4. Check everything:            python3 "$DEST/scripts/doctor.py" --online
  5. In Claude Code, type:        /voice-tasks
NEXT
