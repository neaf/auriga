"""HTTP + WebSocket server for the Auriga live stream.

Follows `<capture-dir>/current` (see `stream/lib/session.py`) and tails the
session's `video.h264` and `audio-media.wav` into the wire protocol documented
in `docs/Stream protocol.md`. Exactly one browser viewer is served at a time
(FR-STR-14): the tail loops only append to that viewer's bounded drop-oldest
queue and one send task drains it, so a stalled browser never blocks capture
(NFR-02). `stream/auriga_stream.py` is the CLI wrapper.
"""

import asyncio
import base64
import json
import os
import struct
import threading
from collections import deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

if __package__:
    from .lib.clock import ContentClock
    from .lib.h264 import (
        GOP_MAX_FRAMES,
        FrameAssembler,
        GopBuffer,
        avcc_sample,
        build_avcc,
        extract_sps_pps,
        find_last_idr,
        split_nals,
    )
    from .lib.session import DEFAULT_HEIGHT, DEFAULT_WIDTH, SessionFollower
else:
    from lib.clock import ContentClock
    from lib.h264 import (
        GOP_MAX_FRAMES,
        FrameAssembler,
        GopBuffer,
        avcc_sample,
        build_avcc,
        extract_sps_pps,
        find_last_idr,
        split_nals,
    )
    from lib.session import DEFAULT_HEIGHT, DEFAULT_WIDTH, SessionFollower

AUDIO_HEADER = 44
AUDIO_CHUNK = 7680          # 40 ms, 48 kHz, stereo, s16
DEFAULT_FPS = 30
DEFAULT_WS_PORT = 8081
POLL_INTERVAL = 0.008
SESSION_POLL_INTERVAL = 0.05
VIDEO_READ_CAP = 1024 * 1024   # per poll, so a backlog cannot block the loop
AUDIO_READ_CAP = 256 * 1024
TRAILED_STREAMS = ("video", "audio-media")
VIEWER_QUEUE = 240          # messages buffered for the viewer (~8 s of A/V)
REPLACED_CODE = 4001        # WebSocket close code: another tab took the stream


def usable_parameter_sets(sps, pps) -> bool:
    """True when `sps`/`pps` are complete enough to build an avcC description.

    `split_nals` can hand back a truncated SPS while the segment head is still
    being flushed; `build_avcc` reads bytes 1..3 of the SPS.
    """
    return sps is not None and len(sps) >= 4 and pps is not None and len(pps) >= 1


def stream_path(directory: str, stream: str) -> str:
    """File name of `stream` inside a session directory."""
    if stream == "video":
        return os.path.join(directory, "video.h264")
    return os.path.join(directory, stream + ".wav")


class Viewer:
    """The single browser client, behind a bounded drop-oldest queue.

    The tail loops only append here (synchronous, never awaiting a socket); the
    `run` task is the only place that sends, so a browser that stops reading
    costs a queue, never the capture loop (NFR-02, FR-STR-14).
    """

    def __init__(self, ws, maxsize: int = VIEWER_QUEUE):
        self.ws = ws
        self.maxsize = maxsize
        self.messages = deque()   # (kind, message); kind is "json"|"audio"|"video"
        self.ready = asyncio.Event()
        self.dropped = 0
        self.synced = False       # a keyframe is queued and no frame was lost since
        self.closed = False

    def push_json(self, payload):
        self.push(json.dumps(payload), "json")

    def push_audio(self, message):
        self.push(message, "audio")

    def push_video(self, message, key: bool):
        if key:
            self.clear_video()
            self.synced = True
        elif not self.synced:
            return
        self.push(message, "video")
        if not self.synced:
            # Room was made by dropping a frame, so this delta has no
            # reference: drop the queued video and wait for the next keyframe.
            self.clear_video()

    def push(self, message, kind: str):
        if self.closed:
            return
        if len(self.messages) >= self.maxsize:
            self._make_room()
        self.messages.append((kind, message))
        self.ready.set()

    def clear_video(self):
        """Drop queued video; the decode chain restarts at the next keyframe."""
        if not self.messages:
            return
        self.messages = deque(
            (kind, message) for kind, message in self.messages if kind != "video"
        )
        self.synced = False

    def reset_stream(self):
        """Drop everything queued: what follows belongs to a new session."""
        self.messages.clear()
        self.synced = False

    def stop(self):
        self.closed = True
        self.messages.clear()
        self.ready.set()

    def _make_room(self):
        # Audio goes first: a gap in sound costs less than a broken video
        # chain. Hello/status messages are the last thing to drop.
        for wanted in ("audio", "video", "json"):
            for index, (kind, _message) in enumerate(self.messages):
                if kind != wanted:
                    continue
                del self.messages[index]
                self._count_drop()
                if wanted == "video":
                    self.synced = False
                return
        if not self.messages:
            return
        self.messages.popleft()
        self._count_drop()
        self.synced = False

    def _count_drop(self):
        self.dropped += 1
        # A queue overflow is the mechanism behind a frozen picture, so it is
        # logged, not only counted: the first one and then every 100th.
        if self.dropped == 1 or self.dropped % 100 == 0:
            print(
                "stream: viewer queue full, dropped %d message(s)" % self.dropped,
                flush=True,
            )

    async def run(self):
        while not self.closed:
            self.ready.clear()
            while self.messages and not self.closed:
                _kind, message = self.messages.popleft()
                try:
                    await self.ws.send(message)
                except Exception:
                    self.closed = True
                    return
            await self.ready.wait()


class Streamer:
    def __init__(self, capture_dir: str, fifo_path: str):
        self.capture_dir = capture_dir
        self.fifo_path = fifo_path
        self.follower = SessionFollower(capture_dir)
        self.session = None
        self.stream_epoch = {stream: 0 for stream in TRAILED_STREAMS}
        self.viewer = None
        self.lock = asyncio.Lock()   # GOP bookkeeping only; never held across a send
        self.gop = GopBuffer(GOP_MAX_FRAMES)
        self.clock = ContentClock()
        self.width = DEFAULT_WIDTH
        self.height = DEFAULT_HEIGHT
        self.fps = DEFAULT_FPS

        self.sps = None
        self.pps = None
        self.description = None
        self.codec = "avc1.42c01f"
        self.codec_stale = False

    def video_path(self) -> str:
        return stream_path(self.session.directory, "video")

    def audio_path(self) -> str:
        return stream_path(self.session.directory, "audio-media")

    def _segment_codec(self):
        """SPS/PPS found at the head of the current segment, or (None, None)."""
        if self.session is None:
            return None, None
        return extract_sps_pps(self.video_path())

    def apply_codec(self, sps, pps):
        self.sps, self.pps = sps, pps
        self.description = build_avcc(sps, pps)
        self.codec = "avc1.%02x%02x%02x" % (sps[1], sps[2], sps[3])
        print("stream: codec=%s" % self.codec, flush=True)

    def refresh_codec(self) -> bool:
        """Re-read SPS/PPS from the current segment; True when they changed."""
        sps, pps = self._segment_codec()
        if not usable_parameter_sets(sps, pps):
            return False
        if sps == self.sps and pps == self.pps:
            return False
        self.apply_codec(sps, pps)
        return True

    def hello(self):
        """`hello` payload; geometry comes from the session's `manifest.json`.

        The head unit publishes width/height/fps from its configured video
        resolution; the parser's 1280x720/30 defaults only apply to a manifest
        that is absent or carries no geometry.
        """
        return {
            "type": "hello",
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "codec": self.codec,
            "description": base64.b64encode(self.description).decode()
            if self.description
            else None,
        }

    def send_hello(self):
        if self.viewer is not None:
            self.viewer.push_json(self.hello())

    def send_json(self, payload):
        if self.viewer is not None:
            self.viewer.push_json(payload)

    async def session_loop(self):
        while True:
            try:
                event = self.follower.poll()
                if event is not None:
                    await self.adopt(event)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                # One malformed manifest or truncated segment head must not end
                # the loop; without it no new session is ever followed again.
                print("stream: session poll failed: %s" % error, flush=True)
            await asyncio.sleep(SESSION_POLL_INTERVAL)

    async def adopt(self, event):
        initial = self.session is None
        self.session = event
        print(
            "stream: session %s (%s)"
            % (event.name, "adopted" if initial else "changed" if event.changed else "rolled"),
            flush=True,
        )

        if initial or event.changed:
            self.width = event.manifest.width
            self.height = event.manifest.height
            self.fps = max(1, int(round(event.manifest.fps)))
            self.clock = ContentClock(fps=self.fps)
            self.gop.clear()
            self.sps = None
            self.pps = None
            self.description = None
            self.codec = "avc1.42c01f"
            self.codec_stale = False
            self.refresh_codec()

        if initial:
            # A client may already be connected; it gets a configured hello as
            # soon as the session's SPS/PPS exist.
            if self.description is not None:
                self.send_hello()
            return

        if event.changed:
            for stream in self.stream_epoch:
                self.stream_epoch[stream] += 1
            if self.viewer is not None:
                self.viewer.reset_stream()
            self.send_json({"type": "reset"})
            self.send_hello()
            return

        for stream in event.streams:
            if stream in self.stream_epoch:
                self.stream_epoch[stream] += 1
                print(
                    "stream: %s segment %d"
                    % (stream, event.manifest.segment_count(stream)),
                    flush=True,
                )

        if "video" in event.streams:
            # The new segment carries its own SPS/PPS; they may differ (encoder
            # reconfigure). Re-read them once the segment head exists and send a
            # fresh hello if the avcC description changed.
            self.codec_stale = True

    async def open_when_ready(self, path: str, offset: int, at_end: bool = False):
        """Open `path` at `offset` once it exists.

        A new session's files appear when the AA channels open, which can be
        seconds after `current` moves; the tail loop must wait rather than die.
        `at_end` is for the audio tail: when the WAV appears late, the whole
        existing file is backlog, so start at its end instead of replaying it.
        """
        while True:
            try:
                handle = open(path, "rb")
            except OSError:
                await asyncio.sleep(0.2)
                continue
            handle.seek(offset)
            if at_end:
                handle.seek(0, os.SEEK_END)
            return handle

    async def resync_viewer(self):
        """Configure the page again and hand it a decodable keyframe.

        A `hello` tears the page's decoder down (`app.js` `configureVideo` sets
        `needKey`), so after a codec change the viewer is unsynced by definition.
        Replaying the cached GOP from its keyframe resynchronises it now instead
        of leaving it to the encoder's next IDR (~60 s on the AA stream).
        """
        if self.viewer is not None:
            self.viewer.clear_video()
        self.send_hello()
        if self.viewer is not None:
            await self.replay(self.viewer)

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
        assembler = FrameAssembler()
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
                assembler = FrameAssembler()
                if self.description is not None:
                    self.codec_stale = True
                print("stream: video reopened %s" % path, flush=True)

            if self.codec_stale:
                sps, pps = self._segment_codec()
                if usable_parameter_sets(sps, pps):
                    self.codec_stale = False
                    if sps != self.sps or pps != self.pps:
                        self.apply_codec(sps, pps)
                        print(
                            "stream: codec changed, replaying %d cached frame(s)"
                            % (len(self.gop),),
                            flush=True,
                        )
                        await self.resync_viewer()

            if self.description is None and self.refresh_codec():
                self.send_hello()

            try:
                size = os.path.getsize(path)
            except OSError:
                await asyncio.sleep(0.2)
                continue

            # A segment rollover truncates the file before the manifest poll
            # sees the count. Wait for the reopen instead of replaying bytes at
            # a stale offset.
            if size > self.video_offset:
                chunk = f.read(min(size - self.video_offset, VIDEO_READ_CAP))
                self.video_offset += len(chunk)
                buf += chunk
                nals, buf = split_nals(buf)

                for nal in nals:
                    for key, frame in assembler.push(nal):
                        await self.flush_frame(frame, key)

                frame = assembler.flush()
                if frame is not None:
                    # Emit the frame completed by this read; a following VCL
                    # starts a new one. One-frame latency keeps slices together.
                    await self.flush_frame(frame[1], frame[0])

            await asyncio.sleep(POLL_INTERVAL)

    async def flush_frame(self, frame, key):
        sample = avcc_sample(frame)
        if not sample:
            return
        message = struct.pack(">BQ", 1 if key else 3, self.clock.next_video()) + sample
        async with self.lock:
            self.gop.add(message, key)
            if self.viewer is not None:
                self.viewer.push_video(message, key)

    async def audio_loop(self):
        while self.session is None:
            await asyncio.sleep(SESSION_POLL_INTERVAL)

        seen_epoch = self.stream_epoch["audio-media"]
        path = self.audio_path()
        try:
            self.audio_offset = max(AUDIO_HEADER, os.path.getsize(path))
        except OSError:
            self.audio_offset = AUDIO_HEADER
        f = await self.open_when_ready(path, self.audio_offset, at_end=True)
        self.audio_offset = max(AUDIO_HEADER, os.fstat(f.fileno()).st_size)
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
                chunk = f.read(min(size - self.audio_offset, AUDIO_READ_CAP))
                self.audio_offset += len(chunk)
                chunk = remainder + chunk
                usable = len(chunk) // 4 * 4
                remainder = chunk[usable:]
                chunk = chunk[:usable]

                for i in range(0, len(chunk), AUDIO_CHUNK):
                    pcm = chunk[i:i + AUDIO_CHUNK]
                    if not pcm:
                        continue
                    header = struct.pack(">BQ", 2, self.clock.next_audio(len(pcm)))
                    if self.viewer is not None:
                        self.viewer.push_audio(header + pcm)

            await asyncio.sleep(POLL_INTERVAL)

    async def replay(self, viewer):
        """Replay the cached GOP so a viewer can decode from a keyframe.

        Bounded by `GOP_MAX_FRAMES`; an empty cache leaves the viewer waiting
        for the next live keyframe (`GopBuffer`).
        """
        async with self.lock:
            for key, message in self.gop.messages():
                viewer.push_video(message, key)

    async def handle(self, ws):
        peer = getattr(ws, "remote_address", "?")
        print("stream: client connected %s" % (peer,), flush=True)

        # Replace the previous viewer before installing the new one: while the
        # old socket closes (an await), the tail loops must not push video into a
        # viewer that has not received `hello` yet.
        previous = self.viewer
        if previous is not None:
            print("stream: replacing the previous viewer", flush=True)
            previous.stop()
            try:
                await previous.ws.close(code=REPLACED_CODE, reason="replaced")
            except Exception:
                pass

        viewer = Viewer(ws)
        self.viewer = viewer
        task = asyncio.create_task(viewer.run())

        viewer.push_json(self.hello())
        await self.replay(viewer)

        try:
            async for message in ws:
                if not isinstance(message, str):
                    continue
                try:
                    data = json.loads(message)
                except ValueError:
                    continue
                command = data.get("type")
                if command == "keyframe":
                    print("stream: keyframe request", flush=True)
                    viewer.clear_video()
                    viewer.push_json(self.hello())
                    await self.replay(viewer)
                    continue
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
                    # The browser shows a live picture but no input effect
                    # otherwise; say so instead of failing silently.
                    viewer.push_json(
                        {"type": "status", "text": "input unavailable: %s" % error.strerror}
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        finally:
            viewer.stop()
            task.cancel()
            if self.viewer is viewer:
                self.viewer = None
            print("stream: client disconnected %s" % (peer,), flush=True)


def serve_http(web_dir: str, port: int, ws_port: int = DEFAULT_WS_PORT):
    """Serve `web_dir` on loopback, plus `config.json` with the WebSocket port.

    The page has to learn the WS port from the HTTP side, otherwise
    `--ws-port` (and `AURIGA_WS_PORT`) would be lies: `app.js` fetches this
    file before it connects.
    """
    config = json.dumps({"wsPort": ws_port}).encode()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=web_dir, **kwargs)

        def do_GET(self):
            if self.path.split("?", 1)[0] == "/config.json":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(config)))
                self.end_headers()
                self.wfile.write(config)
                return
            super().do_GET()

        def log_message(self, *_args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    print(
        "http: http://127.0.0.1:%d (web dir %s, ws port %d)"
        % (httpd.server_address[1], web_dir, ws_port),
        flush=True,
    )
    return httpd
