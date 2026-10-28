# Captures

Local artifacts from the first working full-OpenAuto projection run
(2026-10-28). Large media is intentionally **not committed** to git; these
files stay in the working tree for analysis.

| File | What |
| --- | --- |
| `2026-10-28-session2-video.h264` | 1280x720 H.264 Annex-B, session 2 |
| `2026-10-28-session2-audio-media.wav` | 48 kHz/16-bit stereo media audio (Spotify) |
| `2026-10-28-session2-input.jsonl` | injected taps |
| `frame-30.png` | AA “check your phone” screen |
| `frame-300.png`, `frame-600.png`, `frame-900.png` | Maps + Spotify UI |
| `frame-after-tap.png` | after a tap, welcome screen (phone picked up) |
| `2026-10-28-session2-aftertap.*` | snapshot/remux after the tap |

The live capture files on the Pi are in `~/auriga/captures-openauto/`:
`video.h264`, `audio-media.wav`, `audio-guidance.wav`, `audio-system.wav`,
`input.jsonl`. The `stream/` server tails those files.

Extract a frame:

```bash
ffmpeg -v error -i 2026-10-28-session2-video.h264 \
  -vf "select=eq(n\,600)" -frames:v 1 -y frame.png
```

Validate audio (the WAV header is updated once per second while recording):

```bash
ffmpeg -hide_banner -i 2026-10-28-session2-audio-media.wav \
  -af volumedetect -f null -
```
