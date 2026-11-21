"""Parsing of BepInEx LogOutput.log text. Pure functions."""
from __future__ import annotations

import re

from .models import LogSummary

_LINE = re.compile(r"^\[(?P<level>Fatal|Error|Warning|Message|Info|Debug)\s*:\s*(?P<source>[^\]]+?)\s*\]\s?(?P<msg>.*)$")
_LOADING = re.compile(r"Loading \[(?P<name>.+?) (?P<version>[\d.]+)\]")
_TS_MANIFEST = re.compile(r"TS Manifest: (?P<full>[^\s|]+-[^\s|]+)-(?P<version>\d+\.\d+\.\d+)")

# Messages the base game or the OS always print; they are not caused by mods.
KNOWN_NOISE = (
    "has multiple NetworkIdentity components",
    'is defined in this project\'s "Tags and Layers"',
    "The referenced script",
    "Internal: deleting an allocation",
    "JobTempAlloc has allocations",
    "PopulateTypeFields issues",
    "Duplicate SkillFamily name",
    "[AkGameObjManager]",
    "Parent of RectTransform is being set",
    # Windows refuses ClipCursor while the game window is in the background (normal in automated tests).
    "Failed to confine the cursor",
)


def is_noise(message: str) -> bool:
    return any(n in message for n in KNOWN_NOISE)


def parse_log(text: str) -> LogSummary:
    s = LogSummary()
    for raw in text.splitlines():
        m = _LINE.match(raw)
        if not m:
            continue
        level, source, msg = m["level"], m["source"].strip(), m["msg"].strip()
        if source == "BepInEx" and (lm := _LOADING.search(msg)):
            s.loaded[lm["name"]] = lm["version"]
        elif tm := _TS_MANIFEST.search(msg):
            s.manifests[tm["full"]] = tm["version"]
        if "Chainloader startup complete" in msg:
            s.chainloader_done = True
        if "was built for build id" in msg:
            s.game_version_warning = msg
        if level in ("Error", "Fatal", "Warning") and not is_noise(msg):
            s.errors[(level, source, msg)] += 1
            if level in ("Error", "Fatal") and "Exception" in msg:
                s.exceptions.append(f"[{source}] {msg}")
    return s
