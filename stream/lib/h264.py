"""Annex-B H.264 helpers for the Auriga stream server.

Pure parsing plus two file readers: no asyncio, no network, so the logic can be
tested without a head unit. Wire framing and the avcC layout are documented in
`docs/Stream protocol.md`.
"""

import os
import struct

LAST_IDR_WINDOW = 8 * 1024 * 1024


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
