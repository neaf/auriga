# `stream/` — live Mac client for the Pi head unit

This is the first remote-UI prototype. The AA host stays on the Pi (OpenAuto
capture build); the Pi tails the live capture files and serves them over
WebSocket. Brave/Chrome on the Mac decodes with WebCodecs/WebAudio and sends
touches back.

It is also the client for the native macOS head unit: `autoapp` runs on the Mac,
captures to `captures-mac/`, and the server runs on localhost. No tunnel or Pi is
involved in that mode.

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
# macOS head unit, dongle on the Mac (no Pi/tunnel)
./scripts/mac-headunit-start.sh

# Pi head unit + Mac remote UI
~/auriga/scripts/pi-start.sh   # on the Pi
./scripts/mac-start.sh         # tunnels 8080/8081
```

Or manually, on the host running OpenAuto:

```bash
cd stream
python3 auriga_stream.py --capture-dir /path/to/captures-mac --fifo /tmp/auriga-in
```

The server follows `<capture-dir>/current`, so it needs the capture directory,
not the two file paths. It listens on `127.0.0.1:8080` (HTTP) and
`127.0.0.1:8081` (WebSocket) only. Open `http://localhost:8080` in Brave (or
Chrome). `localhost` is a secure context, which WebCodecs requires.

From a remote Mac (Pi setup), tunnel both ports:

```bash
ssh -N -L 8080:127.0.0.1:8080 -L 8081:127.0.0.1:8081 pi@auriga-pi.local
```

- Audio starts **muted**; click the small 🔇 button to create/resume the
  AudioContext.
- Click/tap the canvas to send a tap. Drag sends down/move/up.
- The stream starts at the most recent H.264 IDR and then follows live.

## Protocol

- Server → client text `hello`:
  `{type, width, height, fps, codec, description}` where geometry comes from
  the session's `manifest.json` (1280x720/30 until the head unit publishes it),
  `description` is base64 avcC (SPS/PPS) and `codec` is e.g. `avc1.42801f`.
- Server → client binary: `type:u8 | timestamp_us:u64 BE | payload`
  - type 1 = H.264 key frame (AVCC), type 3 = H.264 delta (AVCC),
  - type 2 = PCM s16le 48 kHz stereo (40 ms chunks).
- `ts_us` is a per-session content clock: video from the frame index, audio from
  the sample index.
- Server text `reset` when `current` moves to a new session, and `status`
  (`{type:"status", text}`) for a server-side condition such as a failed FIFO
  write.
- Client → server text: `{type:"tap"|"down"|"move"|"up", x, y}` in 1280x720
  space; the server writes `tap X Y` etc. to `/tmp/auriga-in`.
- Client → server text `{type:"keyframe"}` asks the server to replay its cached
  GOP so the decoder resynchronises.
- One viewer per session: a second tab replaces the first, which is closed with
  WebSocket code `4001` and stops reconnecting.

## Limitations

- The file sinks do not preserve AA timestamps; video/audio sync is
  best-effort (audio is anchored to its own first chunk).
- New clients receive the cached GOP (the last keyframe plus following
  deltas), bounded to 2400 frames, so WebCodecs can start decoding. If the AA
  stream has no recent IDR, the server starts at file offset 0 and catches up;
  a GOP past the bound clears the cache and the page waits for the next IDR.
- A new AA session creates a new `session-<id>` directory; the server detects
  the `current` change, clears the GOP and sends `reset`. The previous session
  stays on disk (the five newest are kept).
- The H.264 parser assumes one slice per frame (the current AA stream meets
  this).
- No H.264 transcode; the Pi only copies/frames. WebCodecs does the decode on
  the Mac.
- This prototype depends on the OpenAuto capture app; the long-term headless
  emulator should feed the same protocol directly from aasdk callbacks with AA
  timestamps and per-session files.
