"""Capture-session naming, retention, manifest parsing and following.

Naming, retention and parsing are pure functions over directory names and JSON
text. `SessionFollower` is the only part that reads the filesystem: it resolves
`<capture-dir>/current` and reads `manifest.json`, so `tests/` can drive it with
a temporary directory and no head unit. The on-disk contract is documented in
`docs/Android Auto head unit.md`; the stream server's view of it in
`docs/Stream protocol.md`.
"""

from __future__ import annotations

import json
import os
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


def read_current(capture_dir, name: str = CURRENT_NAME) -> str | None:
    """Session directory name `<capture_dir>/<name>` points at, or None.

    The head unit publishes a relative symlink named `session-<id>`; anything
    that is not such a link (missing, a plain file, a foreign target) is
    reported as "no session" rather than guessed at.
    """
    try:
        target = os.readlink(os.path.join(capture_dir, name))
    except OSError:
        return None
    base = os.path.basename(target.rstrip(os.sep))
    return base if is_session_name(base) else None


def read_manifest(directory, name: str = MANIFEST_NAME) -> Manifest | None:
    """Parse `<directory>/manifest.json`, or None when it is absent or invalid."""
    try:
        with open(os.path.join(directory, name), "r", encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError):
        return None
    return parse_manifest(text)


@dataclass(frozen=True)
class SessionEvent:
    """A change the stream server has to act on.

    `changed` is True only when `current` moved to a different session; the
    first observation of a session reports `changed == False` and lists every
    stream in `streams`, so a fresh server adopts an existing session without
    broadcasting a reset. `streams` names the streams whose file must be
    reopened at offset 0: all of them for a new session, otherwise only those
    whose segment count advanced.
    """

    name: str
    directory: str
    manifest: Manifest
    changed: bool
    streams: tuple[str, ...]


class SessionFollower:
    """Follows `<capture-dir>/current` and its `manifest.json`.

    Replaces the file-size heuristic the server used to detect a session
    change: `current` names the live session, and the manifest segment counts
    name a rollover. Both are written atomically by the head unit.
    """

    def __init__(self, capture_dir, current_name: str = CURRENT_NAME,
                 manifest_name: str = MANIFEST_NAME):
        self.capture_dir = str(capture_dir)
        self.current_name = current_name
        self.manifest_name = manifest_name
        self.name: str | None = None
        self._counts: dict[str, int] | None = None

    def poll(self) -> SessionEvent | None:
        """Return the pending change, or None when nothing moved."""
        name = read_current(self.capture_dir, self.current_name)
        if name is None:
            return None

        directory = os.path.join(self.capture_dir, name)
        manifest = read_manifest(directory, self.manifest_name)
        if manifest is None:
            manifest = Manifest(session=session_id_from_name(name) or "")

        changed = self.name is not None and name != self.name
        previous = self._counts
        if changed or previous is None:
            streams = STREAMS
        else:
            streams = tuple(
                stream for stream in STREAMS
                if manifest.segment_count(stream) != previous.get(stream, 0)
            )
            if not streams:
                return None

        self.name = name
        self._counts = {stream: manifest.segment_count(stream) for stream in STREAMS}
        return SessionEvent(
            name=name,
            directory=directory,
            manifest=manifest,
            changed=changed,
            streams=tuple(streams),
        )
