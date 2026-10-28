# `stream/` — live Mac client for the Pi head unit

This is the first remote-UI prototype. The AA host stays on the Pi (OpenAuto
capture build); the Pi tails the live capture files and serves them over
WebSocket. Brave/Chrome on the Mac decodes with WebCodecs/WebAudio and sends
touches back.

## Architecture

```
phone --BT/WiFi--> AutoLink dongle --USB AOA--> Pi OpenAuto capture
                                                   |
                                     video.h264 / audio-media.wav
                                                   |
                                      auriga_stream.py (tail + WS)
                                                   |
                              SSH tunnel 8080/8081
                                                   |
                                   Brave (WebCodecs + WebAudio)
                                                   |
                                      tap JSON -> /tmp/auriga-in
```

The dongle is a relay at the AA layer (the phone sees the head unit's
`display_name`), so the Pi remains the head unit. The Mac is only the
display/input client.

## Run

The normal way is the launch scripts:

```bash
# Pi
~/auriga/scripts/pi-start.sh
# Mac
./scripts/mac-start.sh
```

Or manually, on the Pi (while the OpenAuto capture is running):

```bash
cd ~/auriga/stream
python3 auriga_stream.py
```

It listens on `127.0.0.1:8080` (HTTP) and `127.0.0.1:8081` (WebSocket) only.
From the Mac, tunnel both ports:

```bash
ssh -N -L 8080:127.0.0.1:8080 -L 8081:127.0.0.1:8081 pi@auriga-pi.local
```

Open `http://localhost:8080` in Brave (or Chrome). `localhost` is a secure
context, which WebCodecs requires.

- Audio starts **muted**; click the small 🔇 button to create/resume the
  AudioContext.
- Click/tap the canvas to send a tap. Drag sends down/move/up.
- The stream starts at the most recent H.264 IDR and then follows live.

## Protocol

- Server → client text `hello`:
  `{type, width, height, fps, codec, description}` where `description` is
  base64 avcC (SPS/PPS) and `codec` is e.g. `avc1.42801f`.
- Server → client binary: `type:u8 | timestamp_us:u64 BE | payload`
  - type 1 = H.264 key frame (AVCC), type 3 = H.264 delta (AVCC),
  - type 2 = PCM s16le 48 kHz stereo (20 ms chunks).
- Server text `reset` when the capture file is truncated by a new AA session.
- Client → server text: `{type:"tap"|"down"|"move"|"up", x, y}` in 1280x720
  space; the server writes `tap X Y` etc. to `/tmp/auriga-in`.

## Limitations

- The file sinks do not preserve AA timestamps; video/audio sync is
  best-effort (audio is anchored to its own first chunk).
- The stream starts at the last IDR in the file, not necessarily live; it
  catches up as frames are sent.
- A new AA session truncates `video.h264`/`audio-media.wav`; the server detects
  it and sends `reset`, but the previous capture is lost.
- The H.264 parser assumes one slice per frame (the current AA stream meets
  this).
- No H.264 transcode; the Pi only copies/frames. WebCodecs does the decode on
  the Mac.
- This prototype depends on the OpenAuto capture app; the long-term headless
  emulator should feed the same protocol directly from aasdk callbacks with AA
  timestamps and per-session files.
