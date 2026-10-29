import json
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from stream.lib.session import (
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    Manifest,
    SessionFollower,
    is_session_name,
    mint_session_id,
    parse_manifest,
    plan_retention,
    read_current,
    read_manifest,
    session_id_from_name,
    session_name,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


class SessionNameTest(unittest.TestCase):
    def test_mint_from_a_fixed_clock(self):
        self.assertEqual(mint_session_id(datetime(2026, 10, 29, 8, 5, 6)), "20261029-080506")

    def test_name_round_trip(self):
        name = session_name("20261029-080506")
        self.assertEqual(name, "session-20261029-080506")
        self.assertTrue(is_session_name(name))
        self.assertEqual(session_id_from_name(name), "20261029-080506")

    def test_non_session_entries(self):
        for name in ("current", "session-", "video.h264", "manifest.json"):
            self.assertFalse(is_session_name(name), name)
            self.assertIsNone(session_id_from_name(name))

    def test_prefix_is_enough_to_count_as_a_session(self):
        self.assertTrue(is_session_name("session-20261029-080506.bak"))


class PlanRetentionTest(unittest.TestCase):
    def test_keeps_the_newest_sessions(self):
        names = ["session-20261029-080501", "session-20261029-080502",
                 "session-20261029-080503", "session-20261029-080504"]
        self.assertEqual(
            plan_retention(names, keep=2),
            ["session-20261029-080501", "session-20261029-080502"],
        )

    def test_ignores_non_session_entries(self):
        names = ["current", "video.h264", "session-20261029-080501"]
        self.assertEqual(plan_retention(names, keep=1), [])

    def test_current_survives_the_cap(self):
        names = ["session-20261029-080501", "session-20261029-080502",
                 "session-20261029-080503"]
        self.assertEqual(
            plan_retention(names, keep=1, current="session-20261029-080501"),
            ["session-20261029-080502"],
        )

    def test_zero_keep_removes_every_old_session(self):
        names = ["session-20261029-080501", "session-20261029-080502"]
        self.assertEqual(plan_retention(names, keep=0), names)

    def test_order_is_oldest_first(self):
        names = ["session-20261029-080503", "session-20261029-080501",
                 "session-20261029-080502"]
        self.assertEqual(
            plan_retention(names, keep=1),
            ["session-20261029-080501", "session-20261029-080502"],
        )


class ParseManifestTest(unittest.TestCase):
    def test_full_manifest(self):
        manifest = parse_manifest((FIXTURES / "manifest.json").read_text())
        self.assertEqual(
            manifest,
            Manifest(
                session="20261029-080506",
                width=1280,
                height=720,
                fps=30.0,
                segments={
                    "video": 2,
                    "audio-media": 3,
                    "audio-guidance": 1,
                    "audio-system": 1,
                },
            ),
        )
        self.assertEqual(manifest.segment_count("video"), 2)
        self.assertEqual(manifest.segment_count("audio-system"), 1)
        self.assertEqual(manifest.segment_count("input"), 0)

    def test_missing_geometry_uses_defaults(self):
        manifest = parse_manifest((FIXTURES / "manifest-no-geometry.json").read_text())
        self.assertEqual(manifest.width, DEFAULT_WIDTH)
        self.assertEqual(manifest.height, DEFAULT_HEIGHT)
        self.assertEqual(manifest.fps, DEFAULT_FPS)
        self.assertEqual(manifest.segment_count("video"), 1)

    def test_invalid_json(self):
        self.assertIsNone(parse_manifest((FIXTURES / "manifest-invalid.json").read_text()))

    def test_non_object_json(self):
        self.assertIsNone(parse_manifest(json.dumps([1, 2])))

    def test_bad_field_types_fall_back_to_defaults(self):
        manifest = parse_manifest('{"width": "wide", "height": null, "fps": "fast"}')
        self.assertEqual(manifest.width, DEFAULT_WIDTH)
        self.assertEqual(manifest.height, DEFAULT_HEIGHT)
        self.assertEqual(manifest.fps, DEFAULT_FPS)

    def test_non_positive_geometry_falls_back_to_defaults(self):
        manifest = parse_manifest('{"width": 0, "height": -2, "fps": 0}')
        self.assertEqual(manifest.width, DEFAULT_WIDTH)
        self.assertEqual(manifest.height, DEFAULT_HEIGHT)
        self.assertEqual(manifest.fps, DEFAULT_FPS)

    def test_segment_counts_are_non_negative_integers(self):
        manifest = parse_manifest('{"video": -3, "audio-media": "2", "audio-system": true}')
        self.assertEqual(manifest.segment_count("video"), 0)
        self.assertEqual(manifest.segment_count("audio-media"), 2)
        self.assertEqual(manifest.segment_count("audio-system"), 0)

    def test_missing_session(self):
        self.assertEqual(parse_manifest("{}").session, "")

    def test_head_unit_field_order(self):
        # Byte-for-byte shape of the document AurigaSessionManager writes.
        manifest = parse_manifest(
            '{"session":"20261029-090405","audio-guidance":0,"audio-media":0,'
            '"audio-system":0,"video":1}\n'
        )
        self.assertEqual(manifest.session, "20261029-090405")
        self.assertEqual(manifest.segment_count("video"), 1)
        self.assertEqual(manifest.segment_count("audio-media"), 0)
        self.assertEqual(manifest.width, DEFAULT_WIDTH)


class CaptureDir:
    """Temporary capture directory with the on-disk session layout."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def close(self):
        self._tmp.cleanup()

    def session(self, session_id, counts=None):
        directory = self.root / session_name(session_id)
        directory.mkdir()
        self.manifest(session_id, counts or {})
        return directory

    def manifest(self, session_id, counts, directory=None):
        target = directory or self.root / session_name(session_id)
        payload = {"session": session_id}
        payload.update(counts)
        temp = target / "manifest.json.tmp"
        temp.write_text(json.dumps(payload))
        os.replace(temp, target / "manifest.json")

    def current(self, name):
        link = self.root / "current"
        temp = self.root / "current.tmp"
        if temp.is_symlink() or temp.exists():
            temp.unlink()
        os.symlink(name, temp)
        os.replace(temp, link)


class ReadCurrentTest(unittest.TestCase):
    def setUp(self):
        self.capture = CaptureDir()

    def tearDown(self):
        self.capture.close()

    def test_missing_pointer(self):
        self.assertIsNone(read_current(self.capture.root))

    def test_relative_pointer(self):
        self.capture.session("20261029-080506")
        self.capture.current("session-20261029-080506")
        self.assertEqual(read_current(self.capture.root), "session-20261029-080506")

    def test_absolute_pointer(self):
        directory = self.capture.session("20261029-080506")
        self.capture.current(str(directory))
        self.assertEqual(read_current(self.capture.root), "session-20261029-080506")

    def test_pointer_to_something_else(self):
        self.capture.current("session-20261029-080506")
        self.capture.current("video.h264")
        self.assertIsNone(read_current(self.capture.root))

    def test_pointer_is_a_plain_file(self):
        (self.capture.root / "current").write_text("session-20261029-080506")
        self.assertIsNone(read_current(self.capture.root))

    def test_read_manifest_of_a_missing_directory(self):
        self.assertIsNone(read_manifest(self.capture.root / "session-20261029-080506"))


class SessionFollowerTest(unittest.TestCase):
    def setUp(self):
        self.capture = CaptureDir()
        self.follower = SessionFollower(self.capture.root)

    def tearDown(self):
        self.capture.close()

    def test_no_session(self):
        self.assertIsNone(self.follower.poll())

    def test_first_poll_adopts_without_a_reset(self):
        self.capture.session("20261029-080506", {"video": 1, "audio-media": 1})
        self.capture.current("session-20261029-080506")
        event = self.follower.poll()
        self.assertEqual(event.name, "session-20261029-080506")
        self.assertEqual(event.directory, str(self.capture.root / "session-20261029-080506"))
        self.assertFalse(event.changed)
        self.assertEqual(event.streams, ("video", "audio-media", "audio-guidance", "audio-system"))
        self.assertEqual(event.manifest.segment_count("video"), 1)

    def test_unchanged_pointer_reports_nothing(self):
        self.capture.session("20261029-080506", {"video": 1})
        self.capture.current("session-20261029-080506")
        self.assertIsNotNone(self.follower.poll())
        self.assertIsNone(self.follower.poll())

    def test_video_rollover_reopens_only_video(self):
        self.capture.session("20261029-080506")
        self.capture.current("session-20261029-080506")
        self.follower.poll()
        self.capture.manifest("20261029-080506", {"video": 1})
        event = self.follower.poll()
        self.assertIsNotNone(event)
        self.assertFalse(event.changed)
        self.assertEqual(event.streams, ("video",))
        self.assertEqual(event.manifest.segment_count("video"), 1)

    def test_two_rollovers_keep_manifest_order(self):
        self.capture.session("20261029-080506")
        self.capture.current("session-20261029-080506")
        self.follower.poll()
        self.capture.manifest("20261029-080506", {"audio-media": 2, "video": 1})
        event = self.follower.poll()
        self.assertEqual(event.streams, ("video", "audio-media"))

    def test_pointer_change_starts_a_new_session(self):
        self.capture.session("20261029-080506", {"video": 2})
        self.capture.current("session-20261029-080506")
        self.follower.poll()
        self.capture.session("20261029-080512", {"video": 0})
        self.capture.current("session-20261029-080512")
        event = self.follower.poll()
        self.assertTrue(event.changed)
        self.assertEqual(event.name, "session-20261029-080512")
        self.assertEqual(event.streams, ("video", "audio-media", "audio-guidance", "audio-system"))
        self.assertEqual(event.manifest.segment_count("video"), 0)

    def test_pointer_rollback_is_a_change(self):
        self.capture.session("20261029-080506")
        self.capture.session("20261029-080512")
        self.capture.current("session-20261029-080506")
        self.follower.poll()
        self.capture.current("session-20261029-080512")
        self.assertTrue(self.follower.poll().changed)

    def test_missing_manifest_uses_defaults_and_the_directory_id(self):
        directory = self.capture.root / "session-20261029-080506"
        directory.mkdir()
        self.capture.current("session-20261029-080506")
        event = self.follower.poll()
        self.assertEqual(event.manifest, Manifest(session="20261029-080506"))
        self.assertEqual(event.manifest.width, DEFAULT_WIDTH)
        self.assertEqual(event.manifest.height, DEFAULT_HEIGHT)
        self.assertEqual(event.manifest.fps, DEFAULT_FPS)

    def test_manifest_appearing_later_is_a_rollover(self):
        directory = self.capture.root / "session-20261029-080506"
        directory.mkdir()
        self.capture.current("session-20261029-080506")
        self.follower.poll()
        self.capture.manifest("20261029-080506", {"video": 1}, directory=directory)
        event = self.follower.poll()
        self.assertFalse(event.changed)
        self.assertEqual(event.streams, ("video",))

    def test_invalid_manifest_uses_defaults(self):
        directory = self.capture.root / "session-20261029-080506"
        directory.mkdir()
        (directory / "manifest.json").write_text("{")
        self.capture.current("session-20261029-080506")
        event = self.follower.poll()
        self.assertEqual(event.manifest.session, "20261029-080506")
        self.assertEqual(event.manifest.segment_count("video"), 0)

    def test_session_appearing_after_start_is_adopted(self):
        self.assertIsNone(self.follower.poll())
        self.capture.session("20261029-080506", {"video": 1})
        self.capture.current("session-20261029-080506")
        event = self.follower.poll()
        self.assertFalse(event.changed)
        self.assertEqual(event.name, "session-20261029-080506")

    def test_pointer_disappearing_is_not_a_session_change(self):
        self.capture.session("20261029-080506")
        self.capture.current("session-20261029-080506")
        self.follower.poll()
        (self.capture.root / "current").unlink()
        self.assertIsNone(self.follower.poll())


if __name__ == "__main__":
    unittest.main()
