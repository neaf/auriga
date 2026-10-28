#!/usr/bin/env python3
"""Auriga live stream server.

Tails the OpenAuto capture files and serves them to a browser client over
WebSocket (H.264 in AVCC framing, PCM s16le stereo). Touch commands from the
client are written to the input FIFO.

Run on the Pi:
  python3 auriga_stream.py --video .../video.h264 --audio .../audio-media.wav
"""

import argparse
import asyncio
import base64
import json
import os
import struct
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import websockets

AUDIO_HEADER = 44
AUDIO_CHUNK = 7680          # 20 ms, 48 kHz, stereo, s16
VIDEO_FPS = 30
VIDEO_FRAME_US = 1_000_000 // VIDEO_FPS
LAST_IDR_WINDOW = 8 * 1024 * 1024


def split_nals(data: bytes):
    """Split Annex-B data into complete NAL units. Returns (nals, remainder)."""
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

    # The last NAL may still be growing; keep its start code for the next read.
    return nals, data[starts[-1][0]:]


def extract_sps_pps(path: str, limit: int = 512 * 1024):
    try:
        with open(path, "rb") as f:
            data = f.read(limit)
    except OSError:
        return None, None

    sps = pps = None
    nals, _ = split_nals(data)
    for nal in nals:
        if not nal:
            continue
        nal_type = nal[0] & 0x1f
        if nal_type == 7 and sps is None:
            sps = nal
        elif nal_type == 8 and pps is None:
            pps = nal
    return sps, pps


def build_avcc(sps: bytes, pps: bytes) -> bytes:
    return (
        bytes([1, sps[1], sps[2], sps[3], 0xFF, 0xE1])
        + struct.pack(">H", len(sps))
        + sps
        + bytes([1])
        + struct.pack(">H", len(pps))
        + pps
    )


def find_last_idr(path: str, window: int = LAST_IDR_WINDOW):
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
        if j + 3 < len(data) and (data[j + 3] & 0x1f) == 5:
            last = start + nal_start
        i = j + 3
    return last


class Streamer:
    def __init__(self, video_path: str, audio_path: str, fifo_path: str):
        self.video_path = video_path
        self.audio_path = audio_path
        self.fifo_path = fifo_path
        self.clients = set()
        self.t0 = time.monotonic()
        self.lock = asyncio.Lock()
        self.gop = []
        self.max_gop = 100000

        self.sps, self.pps = extract_sps_pps(video_path)
        if self.sps is not None and self.pps is not None:
            self.description = build_avcc(self.sps, self.pps)
            self.codec = "avc1.%02x%02x%02x" % (self.sps[1], self.sps[2], self.sps[3])
        else:
            self.description = None
            self.codec = "avc1.42c01f"

        last_idr = find_last_idr(video_path)
        self.video_offset = last_idr if last_idr is not None else 0
        self.audio_offset = max(AUDIO_HEADER, os.path.getsize(audio_path))
        print(
            "stream: codec=%s sps=%s pps=%s video_offset=%s audio_offset=%s"
            % (
                self.codec,
                len(self.sps) if self.sps else None,
                len(self.pps) if self.pps else None,
                self.video_offset,
                self.audio_offset,
            ),
            flush=True,
        )

    def timestamp(self) -> int:
        return int((time.monotonic() - self.t0) * 1_000_000)

    async def broadcast(self, message):
        if not self.clients:
            return
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def hello(self):
        return json.dumps(
            {
                "type": "hello",
                "width": 1280,
                "height": 720,
                "fps": VIDEO_FPS,
                "codec": self.codec,
                "description": base64.b64encode(self.description).decode()
                if self.description
                else None,
            }
        )

    async def send_hello(self, ws):
        await ws.send(self.hello())

    async def video_loop(self):
        f = open(self.video_path, "rb")
        f.seek(self.video_offset)
        buf = b""
        pending = []
        frame = []
        frame_has_vcl = False
        frame_key = False

        while True:
            if self.description is None:
                sps, pps = extract_sps_pps(self.video_path)
                if sps is not None and pps is not None:
                    self.sps, self.pps = sps, pps
                    self.description = build_avcc(self.sps, self.pps)
                    self.codec = "avc1.%02x%02x%02x" % (
                        self.sps[1],
                        self.sps[2],
                        self.sps[3],
                    )
                    print("stream: got SPS/PPS, codec=%s" % self.codec, flush=True)
                    await self.broadcast(self.hello())

            try:
                size = os.path.getsize(self.video_path)
            except OSError:
                await asyncio.sleep(0.2)
                continue

            if size < self.video_offset:
                # New AA session: the file was truncated.
                print("stream: video truncated, resetting", flush=True)
                f.close()
                await self.broadcast(json.dumps({"type": "reset"}))
                self.sps, self.pps = extract_sps_pps(self.video_path)
                if self.sps is not None and self.pps is not None:
                    self.description = build_avcc(self.sps, self.pps)
                    self.codec = "avc1.%02x%02x%02x" % (self.sps[1], self.sps[2], self.sps[3])
                self.video_offset = 0
                self.gop = []
                f = open(self.video_path, "rb")
                f.seek(0)
                buf = b""
                pending = []
                frame = []
                frame_has_vcl = False
                frame_key = False
                await self.broadcast(self.hello())
                await asyncio.sleep(0.1)
                continue

            if size > self.video_offset:
                chunk = f.read(size - self.video_offset)
                self.video_offset += len(chunk)
                buf += chunk
                nals, buf = split_nals(buf)

                for nal in nals:
                    if not nal:
                        continue
                    nal_type = nal[0] & 0x1f

                    if nal_type in (7, 8, 9):
                        if frame_has_vcl:
                            await self.flush_frame(frame, frame_key)
                            frame = []
                            frame_has_vcl = False
                            frame_key = False
                        pending.append(nal)
                    elif 1 <= nal_type <= 5:
                        if frame_has_vcl:
                            await self.flush_frame(frame, frame_key)
                            frame = []
                            frame_has_vcl = False
                            frame_key = False
                        frame = pending + [nal]
                        pending = []
                        frame_has_vcl = True
                        frame_key = frame_key or nal_type == 5
                    else:
                        if frame_has_vcl:
                            frame.append(nal)
                        else:
                            pending.append(nal)

                if frame_has_vcl:
                    # Flush the completed frame; a following VCL will start a
                    # new one. This adds one-frame latency but keeps slices
                    # together.
                    await self.flush_frame(frame, frame_key)
                    frame = []
                    frame_has_vcl = False
                    frame_key = False

            await asyncio.sleep(0.008)

    async def flush_frame(self, frame, key):
        sample = b"".join(struct.pack(">I", len(nal)) + nal for nal in frame)
        if not sample:
            return
        message = struct.pack(">BQ", 1 if key else 3, self.timestamp()) + sample
        async with self.lock:
            if key:
                self.gop = [message]
            elif self.gop:
                self.gop.append(message)
                if len(self.gop) > self.max_gop:
                    # A very long GOP is not useful for a late client; wait for
                    # the next keyframe instead of sending broken references.
                    self.gop = []
            await self.broadcast(message)

    async def audio_loop(self):
        f = open(self.audio_path, "rb")
        f.seek(self.audio_offset)
        remainder = b""

        while True:
            try:
                size = os.path.getsize(self.audio_path)
            except OSError:
                await asyncio.sleep(0.2)
                continue

            if size < self.audio_offset:
                print("stream: audio truncated, resetting", flush=True)
                f.close()
                self.audio_offset = AUDIO_HEADER
                f = open(self.audio_path, "rb")
                f.seek(AUDIO_HEADER)
                remainder = b""
                await asyncio.sleep(0.1)
                continue

            if size > self.audio_offset:
                chunk = f.read(size - self.audio_offset)
                self.audio_offset += len(chunk)
                chunk = remainder + chunk
                usable = len(chunk) // 4 * 4
                remainder = chunk[usable:]
                chunk = chunk[:usable]

                for i in range(0, len(chunk), AUDIO_CHUNK):
                    pcm = chunk[i:i + AUDIO_CHUNK]
                    if not pcm:
                        continue
                    header = struct.pack(">BQ", 2, self.timestamp())
                    await self.broadcast(header + pcm)

            await asyncio.sleep(0.008)

    async def handle(self, ws):
        peer = getattr(ws, "remote_address", "?")
        print("stream: client connected %s" % (peer,), flush=True)
        try:
            async with self.lock:
                await self.send_hello(ws)
                for message in list(self.gop):
                    await ws.send(message)
                self.clients.add(ws)
            async for message in ws:
                if not isinstance(message, str):
                    continue
                try:
                    data = json.loads(message)
                except ValueError:
                    continue
                command = data.get("type")
                if command not in ("tap", "down", "move", "up"):
                    continue
                try:
                    x = int(data["x"])
                    y = int(data["y"])
                except (KeyError, TypeError, ValueError):
                    continue
                line = "%s %d %d\n" % (command, x, y)
                try:
                    fd = os.open(self.fifo_path, os.O_WRONLY | os.O_NONBLOCK)
                    try:
                        os.write(fd, line.encode())
                    finally:
                        os.close(fd)
                    print("stream: input %s" % line.strip(), flush=True)
                except OSError as error:
                    print("stream: input fifo error: %s" % error, flush=True)
        finally:
            self.clients.discard(ws)
            print("stream: client disconnected %s" % (peer,), flush=True)


def serve_http(web_dir: str, port: int):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=web_dir, **kwargs)

        def log_message(self, *_args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    print("http: http://127.0.0.1:%d (web dir %s)" % (port, web_dir), flush=True)


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="/home/pi/auriga/captures-openauto/video.h264")
    parser.add_argument("--audio", default="/home/pi/auriga/captures-openauto/audio-media.wav")
    parser.add_argument("--fifo", default="/tmp/auriga-in")
    parser.add_argument("--http-port", type=int, default=8080)
    parser.add_argument("--ws-port", type=int, default=8081)
    parser.add_argument("--web", default=str(Path(__file__).resolve().parent / "web"))
    args = parser.parse_args()

    serve_http(args.web, args.http_port)
    streamer = Streamer(args.video, args.audio, args.fifo)

    asyncio.create_task(streamer.video_loop())
    asyncio.create_task(streamer.audio_loop())

    async with websockets.serve(streamer.handle, "127.0.0.1", args.ws_port, max_size=None):
        print("ws: ws://127.0.0.1:%d" % args.ws_port, flush=True)
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
