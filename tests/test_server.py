"""Server-side behaviour: one viewer, bounded queue, replay, content clock.

The tail loops and the WebSocket handler are driven with a fake socket, so the
whole path runs on the asyncio loop without a browser or a `websockets` server.
"""

import asyncio
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path

from stream.server import REPLACED_CODE, Streamer, Viewer

START = b"\x00\x00\x00\x01"
SPS = bytes([0x67, 0x42, 0x80, 0x1F, 0xDA, 0x01, 0x40, 0x16, 0xE8, 0x06, 0x05, 0xA8])
PPS = bytes([0x68, 0xCE, 0x06, 0xE2])
IDR = bytes([0x65, 0x88, 0x84, 0x00, 0x21])
DELTA = bytes([0x41, 0x9A, 0x22])


class FakeWebSocket:
    """Just enough of the `websockets` connection for `Streamer.handle`."""

    def __init__(self):
        self.sent = []
        self.closed = None
        self.incoming = asyncio.Queue()

    async def send(self, message):
        self.sent.append(message)

    async def close(self, code=1000, reason=""):
        self.closed = (code, reason)
        self.incoming.put_nowait(None)

    def feed(self, message):
        self.incoming.put_nowait(message)

    def __aiter__(self):
        return self._iterate()

    async def _iterate(self):
        while True:
            message = await self.incoming.get()
            if message is None:
                return
            yield message


class CaptureDir:
    """Temporary capture directory holding one published session."""

    def __init__(self, manifest=None, video=b""):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.directory = self.root / "session-20261029-080506"
        self.directory.mkdir()
        payload = {"session": "20261029-080506", "video": 0, "audio-media": 0}
        payload.update(manifest or {})
        (self.directory / "manifest.json").write_text(json.dumps(payload))
        if video:
            (self.directory / "video.h264").write_bytes(video)
        link = self.root / "current"
        os.symlink(self.directory.name, link)
        self.audio = self.directory / "audio-media.wav"

    def close(self):
        self._tmp.cleanup()


async def settle():
    """Let the handler, the send task and the tail loops run."""
    for _ in range(6):
        await asyncio.sleep(0)


def wait_until(predicate, timeout=2.0):
    async def poll():
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if predicate():
                return True
            await asyncio.sleep(0.01)
        return False

    return poll()


class ViewerQueueTest(unittest.TestCase):
    def make(self, maxsize=4):
        viewer = Viewer(None, maxsize=maxsize)
        viewer.push_json({"type": "hello"})
        viewer.push_video(b"key", True)
        return viewer

    def kinds(self, viewer):
        return [kind for kind, _ in viewer.messages]

    def test_audio_is_dropped_before_video(self):
        viewer = self.make()
        viewer.push_audio(b"a1")
        viewer.push_audio(b"a2")
        viewer.push_audio(b"a3")
        self.assertEqual(self.kinds(viewer), ["json", "video", "audio", "audio"])
        self.assertEqual(viewer.dropped, 1)
        self.assertTrue(viewer.synced)

    def test_dropping_a_frame_waits_for_the_next_keyframe(self):
        viewer = Viewer(None, maxsize=2)
        viewer.push_json({"type": "hello"})
        viewer.push_video(b"key", True)
        self.assertTrue(viewer.synced)
        viewer.push_video(b"delta", False)  # overflows: drops the keyframe
        self.assertFalse(viewer.synced)
        viewer.push_video(b"delta2", False)
        self.assertEqual(
            [message for kind, message in viewer.messages if kind == "video"], []
        )
        viewer.push_video(b"key2", True)
        self.assertTrue(viewer.synced)

    def test_deltas_without_a_keyframe_are_not_queued(self):
        viewer = Viewer(None)
        viewer.push_video(b"delta", False)
        self.assertEqual(list(viewer.messages), [])

    def test_a_keyframe_drops_the_older_queued_video(self):
        viewer = Viewer(None)
        viewer.push_json({"type": "hello"})
        viewer.push_video(b"key", True)
        viewer.push_video(b"delta", False)
        viewer.push_video(b"key2", True)
        self.assertEqual(
            [message for kind, message in viewer.messages if kind == "video"], [b"key2"]
        )

    def test_reset_stream_drops_everything_queued(self):
        viewer = self.make()
        viewer.push_audio(b"a1")
        viewer.reset_stream()
        self.assertEqual(list(viewer.messages), [])
        self.assertFalse(viewer.synced)

    def test_stop_closes_the_queue(self):
        viewer = self.make()
        viewer.stop()
        viewer.push_json({"type": "hello"})
        self.assertEqual(list(viewer.messages), [])


class StreamerTest(unittest.IsolatedAsyncioTestCase):
    def make_streamer(self, manifest=None, video=b""):
        capture = CaptureDir(manifest=manifest, video=video)
        self.addCleanup(capture.close)
        return capture, Streamer(capture.root, "/nonexistent/auriga-in")

    async def attach(self, streamer):
        ws = FakeWebSocket()
        task = asyncio.create_task(streamer.handle(ws))
        self.track(task)
        await settle()
        return ws, task

    def track(self, task):
        self._tasks = getattr(self, "_tasks", [])
        self._tasks.append(task)

    async def asyncTearDown(self):
        for task in getattr(self, "_tasks", []):
            task.cancel()
            try:
                await task
            except BaseException:
                pass
        self._tasks = []

    async def adopt(self, streamer):
        event = streamer.follower.poll()
        self.assertIsNotNone(event)
        await streamer.adopt(event)

    async def test_hello_uses_the_manifest_geometry(self):
        _capture, streamer = self.make_streamer(
            manifest={"width": 1920, "height": 1080, "fps": 25}
        )
        await self.adopt(streamer)
        ws, _task = await self.attach(streamer)
        hello = json.loads(ws.sent[0])
        self.assertEqual(hello["type"], "hello")
        self.assertEqual((hello["width"], hello["height"], hello["fps"]), (1920, 1080, 25))

    async def test_hello_falls_back_to_1280x720_at_30_fps(self):
        _capture, streamer = self.make_streamer()
        await self.adopt(streamer)
        ws, _task = await self.attach(streamer)
        hello = json.loads(ws.sent[0])
        self.assertEqual((hello["width"], hello["height"], hello["fps"]), (1280, 720, 30))

    async def test_a_second_viewer_replaces_the_first(self):
        _capture, streamer = self.make_streamer()
        await self.adopt(streamer)
        first, _first_task = await self.attach(streamer)
        second, _second_task = await self.attach(streamer)
        self.assertEqual(first.closed, (REPLACED_CODE, "replaced"))
        self.assertIs(streamer.viewer.ws, second)
        self.assertEqual(json.loads(second.sent[0])["type"], "hello")

    async def test_video_frames_carry_content_clock_timestamps(self):
        video = (START + SPS + START + PPS + START + IDR
                 + START + DELTA + START + bytes([0x41, 0x9A, 0x23]))
        _capture, streamer = self.make_streamer(video=video)
        await self.adopt(streamer)
        ws, _task = await self.attach(streamer)
        loop = asyncio.create_task(streamer.video_loop())
        self._tasks.append(loop)
        self.assertTrue(await wait_until(lambda: len(ws.sent) >= 3))

        messages = [message for message in ws.sent if not isinstance(message, str)]
        types = [message[0] for message in messages]
        stamps = [struct.unpack(">Q", message[1:9])[0] for message in messages]
        self.assertEqual(types, [1, 3])
        self.assertEqual(stamps, [0, 33_333])
        self.assertEqual(messages[0][9:], struct.pack(">I", len(IDR)) + IDR)

    async def test_keyframe_request_replays_the_cached_gop(self):
        _capture, streamer = self.make_streamer()
        await self.adopt(streamer)
        await streamer.flush_frame([IDR], True)
        await streamer.flush_frame([DELTA], False)
        ws, _task = await self.attach(streamer)
        before = len(ws.sent)

        ws.feed(json.dumps({"type": "keyframe"}))
        self.assertTrue(await wait_until(lambda: len(ws.sent) >= before + 3))

        replay = ws.sent[before:]
        self.assertEqual(json.loads(replay[0])["type"], "hello")
        self.assertEqual([message[0] for message in replay[1:]], [1, 3])

    async def test_keyframe_request_without_a_cached_gop_sends_only_hello(self):
        _capture, streamer = self.make_streamer()
        await self.adopt(streamer)
        ws, _task = await self.attach(streamer)
        before = len(ws.sent)
        ws.feed(json.dumps({"type": "keyframe"}))
        self.assertTrue(await wait_until(lambda: len(ws.sent) > before))
        self.assertEqual(len(ws.sent[before:]), 1)
        self.assertEqual(json.loads(ws.sent[before])["type"], "hello")

    async def test_failed_input_reports_a_status(self):
        _capture, streamer = self.make_streamer()
        await self.adopt(streamer)
        ws, _task = await self.attach(streamer)
        ws.feed(json.dumps({"type": "tap", "x": 1, "y": 2}))
        self.assertTrue(
            await wait_until(
                lambda: any(
                    isinstance(message, str) and json.loads(message).get("type") == "status"
                    for message in ws.sent
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
