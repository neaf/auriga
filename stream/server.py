"""HTTP + WebSocket server for the Auriga live stream.

Follows `<capture-dir>/current` (see `stream/lib/session.py`) and tails the
session's `video.h264` and `audio-media.wav` into the wire protocol documented
in `docs/Stream protocol.md`. `stream/auriga_stream.py` is the CLI wrapper.
"""

import asyncio
import base64
import json
import os
import struct
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

if __package__:
    from .lib.h264 import build_avcc, extract_sps_pps, find_last_idr, split_nals
    from .lib.session import SessionFollower
else:
    from lib.h264 import build_avcc, extract_sps_pps, find_last_idr, split_nals
    from lib.session import SessionFollower

AUDIO_HEADER = 44
AUDIO_CHUNK = 7680          # 40 ms, 48 kHz, stereo, s16
VIDEO_FPS = 30
POLL_INTERVAL = 0.008
SESSION_POLL_INTERVAL = 0.05
TRAILED_STREAMS = ("video", "audio-media")


def stream_path(directory: str, stream: str) -> str:
    """File name of `stream` inside a session directory."""
    if stream == "video":
        return os.path.join(directory, "video.h264")
    return os.path.join(directory, stream + ".wav")


class Streamer:
    def __init__(self, capture_dir: str, fifo_path: str):
        self.capture_dir = capture_dir
        self.fifo_path = fifo_path
        self.follower = SessionFollower(capture_dir)
        self.session = None
        self.stream_epoch = {stream: 0 for stream in TRAILED_STREAMS}
        self.clients = set()
        self.t0 = time.monotonic()
        self.lock = asyncio.Lock()
        self.gop = []
        self.max_gop = 100000

        self.sps = None
        self.pps = None
        self.description = None
        self.codec = "avc1.42c01f"

    def video_path(self) -> str:
        return stream_path(self.session.directory, "video")

    def audio_path(self) -> str:
        return stream_path(self.session.directory, "audio-media")

    def timestamp(self) -> int:
        return int((time.monotonic() - self.t0) * 1_000_000)

    def refresh_codec(self) -> bool:
        """Re-read SPS/PPS from the current segment; True when they changed."""
        if self.session is None:
            return False
        sps, pps = extract_sps_pps(self.video_path())
        if sps is None or pps is None:
            return False
        if sps == self.sps and pps == self.pps:
            return False
        self.sps, self.pps = sps, pps
        self.description = build_avcc(sps, pps)
        self.codec = "avc1.%02x%02x%02x" % (sps[1], sps[2], sps[3])
        print("stream: codec=%s" % self.codec, flush=True)
        return True

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

    async def session_loop(self):
        while True:
            event = self.follower.poll()
            if event is not None:
                await self.adopt(event)
            await asyncio.sleep(SESSION_POLL_INTERVAL)

    async def adopt(self, event):
        initial = self.session is None
        self.session = event
        print(
            "stream: session %s (%s)"
            % (event.name, "adopted" if initial else "changed" if event.changed else "rolled"),
            flush=True,
        )
        if initial:
            # A client may already be connected; it gets a configured hello as
            # soon as the session's SPS/PPS exist.
            if self.refresh_codec():
                await self.broadcast(self.hello())
            return

        if event.changed:
            for stream in self.stream_epoch:
                self.stream_epoch[stream] += 1
            self.description = None
            self.sps = None
            self.pps = None
            self.codec = "avc1.42c01f"
            self.refresh_codec()
            await self.broadcast(json.dumps({"type": "reset"}))
            await self.broadcast(self.hello())
            return

        for stream in event.streams:
            if stream in self.stream_epoch:
                self.stream_epoch[stream] += 1
                print(
                    "stream: %s segment %d"
                    % (stream, event.manifest.segment_count(stream)),
                    flush=True,
                )

    async def open_when_ready(self, path: str, offset: int):
        """Open `path` at `offset` once it exists.

        A new session's files appear when the AA channels open, which can be
        seconds after `current` moves; the tail loop must wait rather than die.
        """
        while True:
            try:
                handle = open(path, "rb")
            except OSError:
                await asyncio.sleep(0.2)
                continue
            handle.seek(offset)
            return handle

    async def video_loop(self):
        # `current` appears when the head unit mints the first session; wait for
        # it instead of failing at startup.
        while self.session is None:
            await asyncio.sleep(SESSION_POLL_INTERVAL)

        seen_epoch = self.stream_epoch["video"]
        path = self.video_path()
        last_idr = find_last_idr(path)
        self.video_offset = last_idr if last_idr is not None else 0
        f = await self.open_when_ready(path, self.video_offset)
        buf = b""
        pending = []
        frame = []
        frame_has_vcl = False
        frame_key = False
        print("stream: video_offset=%s" % self.video_offset, flush=True)

        while True:
            epoch = self.stream_epoch["video"]
            if epoch != seen_epoch:
                # New session or a video segment rollover: the manifest tells
                # us; the file content must not be inspected for a size drop.
                seen_epoch = epoch
                f.close()
                self.video_offset = 0
                path = self.video_path()
                f = await self.open_when_ready(path, 0)
                buf = b""
                pending = []
                frame = []
                frame_has_vcl = False
                frame_key = False
                print("stream: video reopened %s" % path, flush=True)

            if self.description is None and self.refresh_codec():
                await self.broadcast(self.hello())

            try:
                size = os.path.getsize(path)
            except OSError:
                await asyncio.sleep(0.2)
                continue

            # A segment rollover truncates the file before the manifest poll
            # sees the count. Wait for the reopen instead of replaying bytes at
            # a stale offset.
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

            await asyncio.sleep(POLL_INTERVAL)

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
        while self.session is None:
            await asyncio.sleep(SESSION_POLL_INTERVAL)

        seen_epoch = self.stream_epoch["audio-media"]
        path = self.audio_path()
        try:
            self.audio_offset = max(AUDIO_HEADER, os.path.getsize(path))
        except OSError:
            self.audio_offset = AUDIO_HEADER
        f = await self.open_when_ready(path, self.audio_offset)
        remainder = b""
        print("stream: audio_offset=%s" % self.audio_offset, flush=True)

        while True:
            epoch = self.stream_epoch["audio-media"]
            if epoch != seen_epoch:
                seen_epoch = epoch
                f.close()
                self.audio_offset = AUDIO_HEADER
                path = self.audio_path()
                f = await self.open_when_ready(path, AUDIO_HEADER)
                remainder = b""
                print("stream: audio reopened %s" % path, flush=True)

            try:
                size = os.path.getsize(path)
            except OSError:
                await asyncio.sleep(0.2)
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

            await asyncio.sleep(POLL_INTERVAL)

    async def handle(self, ws):
        peer = getattr(ws, "remote_address", "?")
        print("stream: client connected %s" % (peer,), flush=True)
        try:
            async with self.lock:
                try:
                    await self.send_hello(ws)
                    for message in list(self.gop):
                        await ws.send(message)
                except Exception:
                    # Client went away between the HTTP page load and the WS
                    # handshake; drop it without a noisy traceback.
                    return
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
