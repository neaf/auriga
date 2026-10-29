"""Capture-session naming, retention and manifest parsing.

Pure functions over directory names and JSON text: no filesystem and no wall
clock, so `tests/` covers them without a head unit. The on-disk contract is
documented in `docs/Android Auto head unit.md`; the stream server's view of it
in `docs/Stream protocol.md`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, Mapping

SESSION_PREFIX = "session-"
SESSION_TIME_FORMAT = "%Y%m%d-%H%M%S"
CURRENT_NAME = "current"
MANIFEST_NAME = "manifest.json"

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 30.0
STREAMS = ("video", "audio-media", "audio-guidance", "audio-system")


def mint_session_id(now: datetime | None = None) -> str:
    """Session id from the wall clock; ids sort lexicographically by time."""
    return (now or datetime.now()).strftime(SESSION_TIME_FORMAT)


def session_name(session_id: str) -> str:
    return SESSION_PREFIX + session_id


def is_session_name(name: str) -> bool:
    return name.startswith(SESSION_PREFIX) and len(name) > len(SESSION_PREFIX)


def session_id_from_name(name: str) -> str | None:
    return name[len(SESSION_PREFIX):] if is_session_name(name) else None


def plan_retention(names: Iterable[str], keep: int, current: str | None = None):
    """Session directory names to delete, oldest first.

    `keep` is the number of most recent sessions retained; `current` is always
    retained even when it falls outside that window. Non-session entries (the
    `current` pointer, stray files) are ignored.
    """
    sessions = sorted(name for name in names if is_session_name(name))
    if keep < 0:
        keep = 0
    retained = set(sessions[len(sessions) - keep:]) if keep else set()
    if current in sessions:
        retained.add(current)
    return [name for name in sessions if name not in retained]


@dataclass(frozen=True)
class Manifest:
    session: str = ""
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: float = DEFAULT_FPS
    segments: Mapping[str, int] = field(default_factory=dict)

    def segment_count(self, stream: str) -> int:
        return int(self.segments.get(stream, 0))


def _positive_int(value, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _positive_float(value, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _count(value) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def parse_manifest(text) -> Manifest | None:
    """Parse `manifest.json` text. Returns None for anything that is not an object."""
    try:
        data = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    segments = {stream: _count(data.get(stream)) for stream in STREAMS}
    return Manifest(
        session=str(data.get("session", "")),
        width=_positive_int(data.get("width"), DEFAULT_WIDTH),
        height=_positive_int(data.get("height"), DEFAULT_HEIGHT),
        fps=_positive_float(data.get("fps"), DEFAULT_FPS),
        segments=segments,
    )
