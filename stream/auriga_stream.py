#!/usr/bin/env python3
"""Auriga live stream server (CLI).

Follows the newest capture session under the capture directory and serves it to
a browser client over WebSocket (H.264 in AVCC framing, PCM s16le stereo) and
HTTP (static files). Touch commands from the client are written to the input
FIFO. The server itself lives in `server.py`; the wire protocol is in
`docs/Stream protocol.md`.

Run on the head unit:
  python3 auriga_stream.py --capture-dir .../captures-mac
"""

import argparse
import asyncio
import os
from pathlib import Path

import websockets

from server import Streamer, serve_http

DEFAULT_CAPTURE_DIR = str(
    Path(os.environ.get("AURIGA_CAPTURE_DIR")
         or Path(__file__).resolve().parent.parent / "captures-mac")
)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture-dir", default=DEFAULT_CAPTURE_DIR)
    parser.add_argument("--fifo", default="/tmp/auriga-in")
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--ws-port", type=int, default=8081)
    parser.add_argument("--web", default=str(Path(__file__).resolve().parent / "web"))
    args = parser.parse_args()

    serve_http(args.web, args.http_port)
    streamer = Streamer(args.capture_dir, args.fifo)

    asyncio.create_task(streamer.session_loop())
    asyncio.create_task(streamer.video_loop())
    asyncio.create_task(streamer.audio_loop())

    async with websockets.serve(streamer.handle, "127.0.0.1", args.ws_port, max_size=None):
        print("ws: ws://127.0.0.1:%d (capture dir %s)" % (args.ws_port, args.capture_dir), flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
