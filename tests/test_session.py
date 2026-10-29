import json
import unittest
from datetime import datetime
from pathlib import Path

from stream.lib.session import (
    DEFAULT_FPS,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    Manifest,
    is_session_name,
    mint_session_id,
    parse_manifest,
    plan_retention,
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


if __name__ == "__main__":
    unittest.main()
