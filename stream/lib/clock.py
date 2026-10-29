"""Content clock for the Auriga stream.

Timestamps derive from stream position, not wall time: video from the frame
index, audio from the sample index. A read backlog therefore cannot cluster
timestamps, and audio stays aligned with video (NFR-02). The wire meaning of
`ts_us` is in `docs/Stream protocol.md`.
"""

MICROS = 1_000_000
DEFAULT_FPS = 30
DEFAULT_SAMPLE_RATE = 48_000
CHANNELS = 2
BYTES_PER_SAMPLE = 2
FRAME_BYTES = CHANNELS * BYTES_PER_SAMPLE  # one stereo s16 sample


def video_timestamp(frame_index: int, fps: int = DEFAULT_FPS) -> int:
    """Microseconds for `frame_index`, floored to an integer.

    `fps` may be fractional; the head unit publishes it in `manifest.json`.
    """
    return int(frame_index * MICROS // fps)


def audio_timestamp(sample_index: int, sample_rate: int = DEFAULT_SAMPLE_RATE) -> int:
    """Microseconds for `sample_index` (one stereo s16 frame), floored."""
    return int(sample_index * MICROS // sample_rate)


class ContentClock:
    """Monotonic stream clock advanced by emitted frames and PCM bytes."""

    def __init__(
        self,
        fps: int = DEFAULT_FPS,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        frame_bytes: int = FRAME_BYTES,
    ):
        self.fps = fps
        self.sample_rate = sample_rate
        self.frame_bytes = frame_bytes
        self.reset()

    def reset(self) -> None:
        """Restart at zero; a new capture session starts a new timeline."""
        self.video_frames = 0
        self.audio_samples = 0

    def next_video(self) -> int:
        timestamp = video_timestamp(self.video_frames, self.fps)
        self.video_frames += 1
        return timestamp

    def next_audio(self, byte_count: int) -> int:
        """Timestamp of the first sample in a `byte_count` PCM chunk.

        Callers align chunks to whole stereo samples, so a partial trailing
        sample is not expected here.
        """
        timestamp = audio_timestamp(self.audio_samples, self.sample_rate)
        self.audio_samples += byte_count // self.frame_bytes
        return timestamp
