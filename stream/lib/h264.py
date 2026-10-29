"""Annex-B H.264 helpers for the Auriga stream server.

Pure parsing, frame grouping plus two file readers: no asyncio, no network, so
the logic can be tested without a head unit. Wire framing and the avcC layout
are documented in `docs/Stream protocol.md`.
"""

import os
import struct

LAST_IDR_WINDOW = 8 * 1024 * 1024
GOP_MAX_FRAMES = 2400  # ~80 s at 30 fps; the replay bound documented in the stream doc


def split_nals(data: bytes):
    """Split Annex-B data into complete NAL units. Returns (nals, remainder).

    The last NAL may still be growing, so its start code is kept in the
    remainder and re-parsed after the next read.
    """
    starts = []
    i = 0
    while True:
        j = data.find(b"\x00\x00\x01", i)
        if j < 0:
            break
        start = j - 1 if j > 0 and data[j - 1] == 0 else j
        starts.append((start, j + 3))
        i = j + 3

    if not starts:
        return [], data[-4:] if len(data) > 4 else data

    nals = []
    for k, (_, payload) in enumerate(starts[:-1]):
        end = starts[k + 1][0]
        nal = data[payload:end]
        if nal:
            nals.append(nal)

    return nals, data[starts[-1][0]:]


def sps_pps_from_bytes(data: bytes):
    """Return the first SPS and PPS NAL units in `data`, or (None, None)."""
    sps = pps = None
    nals, _ = split_nals(data)
    for nal in nals:
        if not nal:
            continue
        nal_type = nal[0] & 0x1F
        if nal_type == 7 and sps is None:
            sps = nal
        elif nal_type == 8 and pps is None:
            pps = nal
    return sps, pps


def extract_sps_pps(path: str, limit: int = 512 * 1024):
    try:
        with open(path, "rb") as f:
            data = f.read(limit)
    except OSError:
        return None, None
    return sps_pps_from_bytes(data)


def build_avcc(sps: bytes, pps: bytes) -> bytes:
    """Build the avcC decoder description: 4-byte NAL lengths, one SPS, one PPS."""
    return (
        bytes([1, sps[1], sps[2], sps[3], 0xFF, 0xE1])
        + struct.pack(">H", len(sps))
        + sps
        + bytes([1])
        + struct.pack(">H", len(pps))
        + pps
    )


def avcc_sample(nals) -> bytes:
    """One AVCC sample: `u32 length + NAL` for every NAL in the access unit."""
    return b"".join(struct.pack(">I", len(nal)) + nal for nal in nals if nal)


def find_last_idr(path: str, window: int = LAST_IDR_WINDOW):
    """Byte offset of the last type-5 NAL start within the last `window` bytes.

    Returns None when the file is missing or holds no IDR. A server restart
    seeks here so a late viewer starts on a decodable keyframe; the window is
    bounded so the read stays cheap on a multi-gigabyte capture.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return None

    start = max(0, size - window)
    try:
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read()
    except OSError:
        return None

    i = 0
    last = None
    while True:
        j = data.find(b"\x00\x00\x01", i)
        if j < 0:
            break
        nal_start = j - 1 if j > 0 and data[j - 1] == 0 else j
        if j + 3 < len(data) and (data[j + 3] & 0x1F) == 5:
            last = start + nal_start
        i = j + 3
    return last


class FrameAssembler:
    """Groups Annex-B NALs into access units, one VCL NAL per frame.

    SPS/PPS/AUD (types 7/8/9) are held back and prepended to the next VCL NAL;
    a following VCL NAL closes the current frame. `push` returns every frame
    completed by a NAL, `flush` the frame still open at the end of a read chunk
    (one-frame latency, as the wire protocol documents). The AA stream has one
    slice per frame, so a second VCL always starts a new frame
    (`docs/Stream protocol.md`).
    """

    def __init__(self):
        self.pending = []
        self._open = []
        self._has_vcl = False
        self._key = False

    def push(self, nal) -> list:
        """Feed one NAL; returns the completed `(key, nals)` frames."""
        if not nal:
            return []
        nal_type = nal[0] & 0x1F
        completed = []
        if nal_type in (7, 8, 9):
            self._close(completed)
            self.pending.append(nal)
        elif 1 <= nal_type <= 5:
            self._close(completed)
            self._open = self.pending + [nal]
            self.pending = []
            self._has_vcl = True
            self._key = self._key or nal_type == 5
        elif self._has_vcl:
            self._open.append(nal)
        else:
            self.pending.append(nal)
        return completed

    def flush(self):
        """The frame left open by the last `push`, or None."""
        if not self._has_vcl:
            return None
        frame = (self._key, self._open)
        self._open = []
        self._has_vcl = False
        self._key = False
        return frame

    def reset(self):
        self.pending = []
        self._open = []
        self._has_vcl = False
        self._key = False

    def _close(self, completed):
        if not self._has_vcl:
            return
        completed.append((self._key, self._open))
        self._open = []
        self._has_vcl = False
        self._key = False


class GopBuffer:
    """Last keyframe plus the frames after it, bounded for memory.

    A viewer that joins mid-GOP replays this cache so it decodes immediately
    instead of waiting for the encoder's next IDR (~60 s on the AA stream).
    Deltas that arrive before any keyframe are not cached. When the cache
    exceeds `max_frames` its frames no longer decode from the keyframe, so the
    whole cache is dropped and viewers wait for the next keyframe; the bound
    keeps one long GOP from pinning memory (NFR-02, FR-STR-05).
    """

    def __init__(self, max_frames: int = GOP_MAX_FRAMES):
        self.max_frames = max_frames
        self._frames = []

    def add(self, message, key: bool) -> bool:
        """Cache one wire message; False when the cache holds no replayable GOP."""
        if key:
            self._frames = [(True, message)]
            return True
        if not self._frames:
            return False
        self._frames.append((False, message))
        if len(self._frames) > self.max_frames:
            self._frames = []
            return False
        return True

    def messages(self):
        """Copy of the cached `(key, message)` pairs, oldest first."""
        return list(self._frames)

    def clear(self):
        self._frames = []

    def __len__(self):
        return len(self._frames)

