# Voice Tasks for Claude Code

Record a voice note of everything you need to do tomorrow. Claude turns it into a prioritised task list in
Notion and books each task into your Google Calendar, with money-making work first.

## What it does

1. Transcribes your voice note on your own Mac (nothing is uploaded for transcription). You can also type
   or paste the list instead.
2. Splits it into clear tasks and ranks them: revenue first, then client delivery, growth, admin, personal.
3. Asks you about anything unclear instead of guessing.
4. Creates the tasks in a Notion database.
5. Reads your Google Calendar for that day and books each task into free time inside your working window
   (07:00 to 22:00 by default), highest priority first, with a 10 minute gap between blocks.
6. Writes the booked times and calendar links back to Notion and gives you a short summary.

It only ever adds calendar events. It never moves or deletes existing ones.

## What you need

| Thing | Why | Cost |
|---|---|---|
| A Mac with Claude Code installed and signed in with a Claude account (Pro, Max, Team or Enterprise) | Runs the skill. The Google Calendar connector needs a Claude account sign-in, not an API key | Your Claude plan |
| Python 3.9 or newer (`python3 --version`) | Runs the helper scripts. If it is missing, run `xcode-select --install` | Free |
| A Notion account and an internal integration key | Stores the tasks | Free |
| Google Calendar connected to Claude | Reads your day and books the blocks | Free |
| About 400 MB of disk space (optional) | Local speech-to-text engine and model. Not needed if you type your list | Free |

No other skills, apps or background services are needed.

## Setup (about 10 minutes)

### 1. Install the skill

Open Terminal, go into the folder you downloaded and run:

```bash
bash install.sh --with-transcription
```

Leave off `--with-transcription` if you only want to type or paste your lists (you can add it later by
running the same command again). The installer copies the skill to `~/.claude/skills/voice-tasks`, creates
`config.json` and `.env` there, and never overwrites those two files if they already exist. If you already
had a different skill called voice-tasks, it is backed up to `~/.claude/skill-backups/` first.

### 2. Create a Notion key

1. Go to https://www.notion.so/profile/integrations and click **New integration**.
2. Name it "Voice Tasks", choose your workspace, type **Internal**, and save.
3. Under Capabilities, make sure Read content, Update content and Insert content are ticked.
4. Copy the **Internal Integration Secret**.
5. Open `~/.claude/skills/voice-tasks/.env` in a text editor (in Finder press Cmd+Shift+G and paste
   `~/.claude/skills/voice-tasks`, then Cmd+Shift+. to show hidden files) and paste the key after
   `NOTION_API_KEY=` so the line reads `NOTION_API_KEY=your-key-here`. Save.

Keep that file private. Do not paste the key into a chat.

### 3. Create the tasks database

1. In Notion, create or pick a page where the tasks should live.
2. On that page click the three dots (top right), **Connections**, and add your "Voice Tasks" integration.
3. Click **Share**, **Copy link**.
4. In Terminal run (with your link in the quotes):

```bash
python3 ~/.claude/skills/voice-tasks/scripts/notion_tasks.py setup "PASTE-YOUR-PAGE-LINK-HERE"
```

This creates a database called "Voice Tasks" on that page with these columns: Task, Status, Urgency, Area,
Due Date, Scheduled, Est. minutes, Source, Notes, Calendar link.

**Already have a tasks database?** Connect the integration to it (step 2 above, on the database), copy its
link and run `python3 ~/.claude/skills/voice-tasks/scripts/notion_tasks.py use "PASTE-DATABASE-LINK"`
instead. The skill fills whichever of the columns above exist and skips the rest. Only a title column is
required.

### 4. Connect Google Calendar

1. Go to https://claude.ai/settings/connectors, find **Google Calendar** and click **Connect**.
2. Quit Claude Code and open it again.
3. Type `/mcp` in Claude Code. You should see the Google Calendar connector in the list.

### 5. Check everything

```bash
python3 ~/.claude/skills/voice-tasks/scripts/doctor.py --online
```

Every line should say `OK` (the Google Calendar line always says `NOTE` because a script cannot check it).

## First run

1. Record a voice note on your phone or Mac (Voice Memos is fine): "Tomorrow I need to follow up with the
   six leads from Tuesday, record two reels, send the invoice to Sam, and go to the gym at five."
2. Get the file onto your Mac (AirDrop works).
3. Open Claude Code and type `/voice-tasks`, then drag the audio file into the window and press Enter.
   Or type: `/voice-tasks follow up with six leads, record two reels, invoice Sam, gym at 5pm`.
4. Answer any questions. Claude then shows the plan for the day with a link to your Notion tasks.

The first voice note takes longer because the speech model (about 150 MB) downloads once.
Claude Code will ask permission the first time it runs a script or books an event. Choose
"Yes, and don't ask again" if you want it to run hands-free.

## Settings

Edit `~/.claude/skills/voice-tasks/config.json`:

| Setting | Meaning | Default |
|---|---|---|
| `window` | Earliest and latest time a task can be booked | `["07:00", "22:00"]` |
| `buffer_min` | Minutes left free between blocks | `10` |
| `time_zone` | Your time zone as an IANA name, for example `Europe/London`. Leave empty to use your Mac's clock. Set it if your calendar is in a different zone from your Mac | empty |
| `whisper_model` | Speech model: `tiny`, `base`, `small`, `medium`, `large-v3`. Bigger is more accurate and slower | `base` |
| `areas` | The Area labels Claude can choose from | Sales, Client, Content, Marketing, Operations, Admin, Personal |
| `notion_key_env` | Name of the variable that holds your Notion key | `NOTION_API_KEY` |
| `tasks_database_id`, `tasks_data_source_id`, `tasks_url` | Filled in for you by `setup` or `use` | empty |

## Troubleshooting

| What you see | Fix |
|---|---|
| `no Notion key found` | Paste the key into `~/.claude/skills/voice-tasks/.env` (Setup step 2) |
| `Notion 401` | The key is wrong or was revoked. Copy it again from the integrations page |
| `Notion 404` | The page or database is not shared with your integration. Add it under Connections (Setup step 3) |
| `tasks_data_source_id is empty` | Run the `setup` or `use` command from Setup step 3 |
| `config.json is missing` or `not valid JSON` | Run `bash install.sh` again, or copy `config.example.json` over `config.json` |
| `the transcription engine (faster-whisper) is not installed` | Run `bash install.sh --with-transcription`, or type your list instead |
| `could not load the speech model` | The first voice note needs an internet connection to download the model |
| Claude says the Google Calendar tools are not available | Do Setup step 4, then restart Claude Code |
| Blocks land at the wrong time of day | Set `time_zone` in `config.json` to your calendar's time zone |
| Tasks were created twice | The same note was run twice. Delete the extras in Notion. The skill never removes anything itself |
| `/voice-tasks` is not recognised | Check the folder `~/.claude/skills/voice-tasks/SKILL.md` exists, then restart Claude Code |
| `python3: command not found` | Run `xcode-select --install`, then run the installer again |

## Privacy

- Audio is transcribed on your Mac. The transcript is then read by Claude in your own Claude Code session.
- Your Notion key stays in `~/.claude/skills/voice-tasks/.env` on your Mac and is only sent to Notion.
- The skill talks to two services: Notion (your tasks) and Google Calendar (through Claude's connector).

## Uninstall

Delete the folder `~/.claude/skills/voice-tasks`. Your Notion tasks and calendar events stay where they are.
