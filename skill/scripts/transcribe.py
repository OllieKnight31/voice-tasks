#!/usr/bin/env python3
"""Transcribe a voice note on this Mac and print the text.

  python3 transcribe.py <audio file> [--model base] [--language en]

Works with .ogg, .opus, .m4a, .mp3, .wav, .mp4 and most other formats.
Uses faster-whisper, installed into the skill's own .venv by `install.sh --with-transcription`.
The first run downloads the speech model (about 150 MB for "base"). After that it runs offline.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vt_common import SKILL_DIR, die, load_config  # noqa: E402

VENV_PY = os.path.join(SKILL_DIR, ".venv", "bin", "python")
INSTALL_HELP = (
    "the transcription engine (faster-whisper) is not installed.\n"
    "Install it once with either of these, then run this again:\n"
    "  bash install.sh --with-transcription      (from the folder you downloaded)\n"
    "  python3 -m venv " + os.path.join(SKILL_DIR, ".venv") + " && "
    + VENV_PY + " -m pip install faster-whisper\n"
    "Or skip transcription: type or paste your task list into Claude instead of sending audio."
)


def main():
    ap = argparse.ArgumentParser(description="Transcribe a voice note locally and print the text.")
    ap.add_argument("audio", help="path to the audio file")
    ap.add_argument("--model", help="tiny, base, small, medium or large-v3 (default: whisper_model in config.json)")
    ap.add_argument("--language", help="language code such as en (default: detect)")
    a = ap.parse_args()

    path = os.path.expanduser(a.audio)
    if not os.path.isfile(path):
        die("audio file not found: " + path)
    if os.path.getsize(path) == 0:
        die("audio file is empty: " + path)

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        # Not in this Python: hand over to the skill's own virtual environment if it exists.
        if os.path.exists(VENV_PY) and os.environ.get("VOICE_TASKS_IN_VENV") != "1":
            os.environ["VOICE_TASKS_IN_VENV"] = "1"
            os.execv(VENV_PY, [VENV_PY, os.path.abspath(__file__)] + sys.argv[1:])
        die(INSTALL_HELP)

    model_name = a.model or load_config(required=False).get("whisper_model") or "base"
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
    except Exception as e:
        die("could not load the speech model " + repr(model_name) + " (" + str(e)[:300] + ").\n"
            "The first run needs an internet connection to download it.")
    try:
        segments, _info = model.transcribe(path, language=a.language, vad_filter=True,
                                           vad_parameters={"min_silence_duration_ms": 500})
        text = " ".join(s.text.strip() for s in segments).strip()
    except Exception as e:
        die("could not read the audio in " + path + " (" + str(e)[:300] + ").")
    if not text:
        die("no speech was found in " + path + ".")
    print(text)


if __name__ == "__main__":
    main()
