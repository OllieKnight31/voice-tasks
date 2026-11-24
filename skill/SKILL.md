---
name: voice-tasks
description: >
  Turn a voice note (or a typed list) of tomorrow's to-dos into Notion tasks and Google Calendar time
  blocks. Transcribes the audio locally, splits it into clear tasks, ranks them with money-making work
  first (sales messages, DMs, follow-ups, calls, sales assets, anything that directly brings in cash),
  writes them to your Notion tasks database, then books each one into the day's calendar inside your
  working window around existing events, highest priority first. Asks before guessing when something
  is unclear. Use when: the user drops an audio or voice file and mentions tasks, says "/voice-tasks",
  "plan my day from this voice note", "put these into Notion and my calendar" or "tomorrow's tasks".
category: productivity
tags: [voice, tasks, notion, calendar, planning]
version: 1.1.0
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
  - mcp__claude_ai_Google_Calendar__list_events
  - mcp__claude_ai_Google_Calendar__create_event
  - mcp__claude_ai_Google_Calendar__list_calendars
---

# Voice Tasks

`SKILL_DIR` = the folder this file is in (normally `~/.claude/skills/voice-tasks`). Use the real path in
every command. Settings live in `SKILL_DIR/config.json`: the Notion tasks database, the day window, the
buffer between blocks, the time zone and the Area options. The Notion key lives in `SKILL_DIR/.env`.
Never print the key or the contents of `.env`.

## Steps

### 0. Check the setup (every run, takes a second, no network)
```bash
python3 SKILL_DIR/scripts/doctor.py
```
- Any `FAIL` line: stop, show the user that line and help them fix it (the README that came with the
  skill has the steps). Do not continue until `doctor.py` passes.
- "Notion tasks database: not set": ask the user for a link to a Notion page that is shared with their
  integration, then run `python3 SKILL_DIR/scripts/notion_tasks.py setup "<link>"` (creates a "Voice Tasks"
  database there). If they already have a tasks database, run `... notion_tasks.py use "<database link>"`.
- If the Google Calendar tools (`mcp__claude_ai_Google_Calendar__*`) are not available in this session,
  tell the user to connect Google Calendar at https://claude.ai/settings/connectors and restart Claude Code.
  You may still do steps 1 to 5 and 7, then show the plan as text and say that nothing was booked.

### 1. Get the words
- Audio file (`.ogg`, `.opus`, `.m4a`, `.mp3`, `.wav` and similar):
  ```bash
  python3 SKILL_DIR/scripts/transcribe.py "<audio file>"
  ```
  It prints the transcript. If it says the transcription engine is not installed, show the user the
  install command it printed and offer to carry on from a typed or pasted list instead.
- Typed or pasted list: use the text as it is. No transcription needed.

If there are fewer than about 5 words, say so and stop.

### 2. Work out the target day
Default: **tomorrow** (local date). If the note says "today" or names a day or date, use that.

### 3. Extract tasks
One task per action, written as a short imperative title ("Follow up with the 6 warm leads from Tuesday").
For each task decide:
- `tier` (priority):
  1. **Revenue**: anything that directly makes money. Outreach and DMs, replying to leads, follow-ups,
     sales and closing calls, booking calls, proposals and quotes, sales assets (sales videos, decks,
     offers, landing pages, ads, sales emails), invoicing and chasing payment, onboarding a new paying client.
  2. **Client delivery**: work for existing paying clients.
  3. **Growth**: content, marketing, audience building, recording, editing.
  4. **Ops and admin**: systems, finance admin, hiring, team, tools, email clean-up.
  5. **Personal**: gym, errands, life admin.
- `area`: one of the `areas` in `config.json` (the closest fit).
- `minutes`: the duration if spoken, else estimate (DM or follow-up block 45, call 30 to 60, sales asset 90,
  content piece 60, admin 30). Round to 15. Always a whole number.
- `fixed_start`: only when a time was spoken ("call with Sam at 3"): local ISO `YYYY-MM-DDTHH:MM:SS`.
- `notes`: names, numbers and context from the note, so the task makes sense later.
- `order`: position in the voice note, starting at 0.
- `key`: `t1`, `t2`, and so on.

### 4. Ask, do not guess
Collect **every** unclear point into one round of questions with `AskUserQuestion` (up to 4 questions, more
rounds only if needed): who someone is, an ambiguous time or day, a vague task ("sort the thing"), a duration
that is clearly unknowable, or whether two items are one task. If nothing is unclear, do not ask.

### 5. Write to Notion
Write the tasks JSON to a temporary file first with a quoted heredoc (`cat > /tmp/voice-tasks-create.json <<'JSON'`),
which avoids shell quoting problems with apostrophes. Do the same for the files in steps 7 and 8. Then:
```bash
python3 SKILL_DIR/scripts/notion_tasks.py create < /tmp/voice-tasks-create.json
```
Input: `[{"key","title","tier","area","minutes","due":"<target date YYYY-MM-DD>","notes"}]`.
Output: `[{key, page_id, url}]`. If the command fails, show the error (it says what to fix) and stop:
do not run it a second time for tasks that were already created.

### 6. Read the day's calendar
`mcp__claude_ai_Google_Calendar__list_events` with `startTime` `<date>T00:00:00`, `endTime` `<date+1>T00:00:00`,
`orderBy` `startTime`. Busy = every timed event that is not marked free and not declined. Ignore all-day events
unless they are out-of-office (then nothing can be booked that day: tell the user and leave tasks unscheduled).
Note the time zone the events come back in. Pass busy times as local wall-clock times with no offset.

### 7. Plan
```bash
python3 SKILL_DIR/scripts/plan.py < /tmp/voice-tasks-plan.json
```
Input: `{"date":"<date>","time_zone":"<IANA tz from step 6>","busy":[[start,end],...],"tasks":[{"key","tier","minutes","order","fixed_start"}]}`.
The window and buffer come from `config.json`. Revenue tasks land in the earliest free slots. Spoken fixed
times are kept. Output: `{"scheduled":[{key,start,end}],"unscheduled":[key]}`.

### 8. Book the calendar
For each scheduled task, `mcp__claude_ai_Google_Calendar__create_event`:
- `summary`: `💰 <title>` for tier 1, `🎯 <title>` tier 2, `📣 <title>` tier 3, `⚙️ <title>` tier 4, `🌿 <title>` tier 5
- `startTime` / `endTime` from the plan (local, no offset, no `timeZone` field)
- `description`: the notes plus `Notion: <task url>`
- `colorId`: tier 1 `"11"` (red), tier 2 `"6"`, tier 3 `"5"`, tier 4 `"8"`, tier 5 `"2"`
- `overrideReminders`: `[{"method":"popup","minutes":5}]`

Then write the times and event links back:
```bash
python3 SKILL_DIR/scripts/notion_tasks.py schedule < /tmp/voice-tasks-schedule.json
```
Input: `[{"page_id","start","end","calendar_link","time_zone":"<IANA tz from step 6>"}]`.
Delete the three `/tmp/voice-tasks-*.json` files when finished.

### 9. Report
Short summary, in the order of the day: time, priority icon, title. Then any unscheduled tasks (no room in
the window) and the Notion tasks link (`tasks_url` in `config.json`).

## Rules
- Never delete or move existing calendar events. Only add.
- Never schedule outside the window in `config.json` unless a time was explicitly spoken.
- Running the same note twice creates duplicates. If the user says it was already processed, stop.
- Never print, log or send the Notion key.
