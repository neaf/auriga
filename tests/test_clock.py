import unittest

from stream.lib.clock import (
    ContentClock,
    audio_timestamp,
    video_timestamp,
)


class VideoTimestampTest(unittest.TestCase):
    def test_frame_zero(self):
        self.assertEqual(video_timestamp(0), 0)

    def test_30_fps(self):
        self.assertEqual(video_timestamp(1), 33333)
        self.assertEqual(video_timestamp(30), 1_000_000)
        self.assertEqual(video_timestamp(1800), 60_000_000)

    def test_other_fps(self):
        self.assertEqual(video_timestamp(1, fps=25), 40_000)

    def test_fractional_fps(self):
        # The head unit publishes fps in `manifest.json`; it may be fractional.
        self.assertEqual(video_timestamp(0, fps=29.97), 0)
        self.assertEqual(video_timestamp(30, fps=29.97), 1_001_001)


class AudioTimestampTest(unittest.TestCase):
    def test_sample_zero(self):
        self.assertEqual(audio_timestamp(0), 0)

    def test_48_khz(self):
        self.assertEqual(audio_timestamp(1), 20)
        self.assertEqual(audio_timestamp(48000), 1_000_000)

    def test_other_rate(self):
        self.assertEqual(audio_timestamp(16000, sample_rate=16_000), 1_000_000)


class ContentClockTest(unittest.TestCase):
    def test_video_advances_one_frame_per_call(self):
        clock = ContentClock()
        self.assertEqual([clock.next_video() for _ in range(3)], [0, 33333, 66666])
        self.assertEqual(clock.video_frames, 3)

    def test_audio_advances_by_whole_stereo_samples(self):
        clock = ContentClock()
        self.assertEqual(clock.next_audio(7680), 0)
        self.assertEqual(clock.audio_samples, 1920)
        self.assertEqual(clock.next_audio(7680), 40_000)
        self.assertEqual(clock.audio_samples, 3840)

    def test_video_and_audio_share_one_timeline(self):
        clock = ContentClock()
        self.assertEqual(clock.next_video(), 0)
        self.assertEqual(clock.next_audio(7680), 0)
        self.assertEqual(clock.next_video(), 33333)

    def test_reset_restarts_both_counters(self):
        clock = ContentClock()
        clock.next_video()
        clock.next_audio(7680)
        clock.reset()
        self.assertEqual(clock.video_frames, 0)
        self.assertEqual(clock.audio_samples, 0)
        self.assertEqual(clock.next_video(), 0)
        self.assertEqual(clock.next_audio(7680), 0)

    def test_fractional_fps_is_accepted(self):
        clock = ContentClock(fps=29.97)
        self.assertEqual(clock.next_video(), 0)
        self.assertEqual(clock.next_video(), 33366)

    def test_a_read_backlog_keeps_timestamps_apart(self):
        # Two chunks read in one poll must not share a timestamp: the offset is
        # derived from the sample index, not from the read time (NFR-02).
        clock = ContentClock()
        timestamps = [clock.next_audio(7680) for _ in range(3)]
        self.assertEqual(timestamps, [0, 40_000, 80_000])


if __name__ == "__main__":
    unittest.main()
