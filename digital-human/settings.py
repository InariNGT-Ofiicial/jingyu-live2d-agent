"""Project-local defaults, overridden by explicit environment variables."""
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL = Path(os.environ.get("JINGYU_DATA", ROOT / ".local")).expanduser().resolve()
def path(name, default):
    return Path(os.environ.get(name, default)).expanduser().resolve()

DECISION = path("JINGYU_DECISION", LOCAL / "models/decision")
ASR = path("JINGYU_ASR", LOCAL / "models/asr")
COSY_SOURCE = path("JINGYU_COSY_SOURCE", LOCAL / "CosyVoice")
COSY_MODEL = path("JINGYU_COSY_MODEL", LOCAL / "models/cosyvoice")
REFERENCE = path("JINGYU_VOICE_REFERENCE", LOCAL / "reference.wav")
PORT = int(os.environ.get("JINGYU_PORT", "18982"))
VOICE_PORT = int(os.environ.get("JINGYU_VOICE_PORT", "18983"))
WORKER = f"http://127.0.0.1:{VOICE_PORT}"
NAME = json.loads((ROOT / "character.json").read_text(encoding="utf8"))["name"]
if not isinstance(NAME, str) or not re.fullmatch(r"[\w ·-]{1,28}", NAME):
    raise ValueError("character.json 中的 name 允许 1～28 个文字、数字、空格及 · - _。")
