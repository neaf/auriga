"""Pure, hardware-free helpers for the Auriga stream server.

`h264` parses Annex-B video, `clock` derives content timestamps, `session`
names capture sessions and parses manifests. None of them open sockets or
touch asyncio, so `tests/` runs without the head unit.
"""
