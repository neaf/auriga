# Stream protocol

`stream/auriga_stream.py` is the CLI; `stream/server.py` follows the head unit's
current capture session and serves it to a browser over a local WebSocket:
H.264 in AVCC framing, PCM s16le stereo, and a JSON control channel. It also
serves the static client from `stream/web`.

## Endpoints and process model

| Endpoint | Address | Purpose |
| --- | --- | --- |
| HTTP | `127.0.0.1:8080` | static files from `stream/web` (`ThreadingHTTPServer`, daemon thread, request logging off) |
| WebSocket | `127.0.0.1:8081` | `hello`, video/audio frames, `reset`, client input |

Both bind loopback only and have no authentication (`stream/server.py:374`,
`stream/auriga_stream.py:45`). Nothing else may be exposed.

One asyncio loop runs `session_loop`, `video_loop`, `audio_loop`, the WebSocket
server and one task per connected client. `session_loop` polls the session
pointer every 50 ms and bumps a per-stream epoch; the tail loops reopen their
file when their epoch moves (`stream/server.py:111-149,184-199,288-297`).
`self.lock` (`asyncio.Lock`) serializes GOP bookkeeping, broadcasts and the
new-client `hello` + GOP send. The HTTP server is a separate daemon thread.

| Argument | Default | Note |
| --- | --- | --- |
| `--capture-dir` | `$AURIGA_CAPTURE_DIR`, else `<repo>/captures-mac` | directory that holds `current` and the `session-*` directories |
| `--fifo` | `/tmp/auriga-in` | must match `autoapp`'s stdin |
| `--http-port` | `8080` | |
| `--ws-port` | `8081` | the page hardcodes 8081, so this flag is unusable without editing `app.js` |
| `--web` | `stream/web` | static root |

## Capture inputs

The head unit writes one directory per AA session and publishes a `current`
pointer; the on-disk contract is in `docs/Android Auto head unit.md`. The server
follows the pointer instead of watching file sizes.

| Input | Format | Read position |
| --- | --- | --- |
| `current` | relative symlink to `session-<id>` | polled every 50 ms (`stream/lib/session.py:123-135,167-214`; `stream/server.py:111-116`) |
| `video.h264` | Annex-B H.264, 4-byte start codes (see `docs/Android Auto head unit.md`) | at startup: last type-5 NAL within the last 8 MiB, else offset 0 (`stream/lib/h264.py:79-109`; `stream/server.py:172-176`). After a session or segment change: offset 0 |
| `audio-media.wav` | 44-byte PCM WAV header, 48 kHz, 2 ch, 16-bit | at startup: end of file (`max(44, size)`); after a change: byte 44 (`stream/server.py:278-284`) |
| input FIFO | text lines `tap|down|move|up X Y` | written per client event (`stream/server.py:351-360`) |

Only `audio-media.wav` is streamed. `audio-guidance.wav` and `audio-system.wav`
are written by the head unit and read by nothing.

Tail loops poll file size every 8 ms. Video bytes are split on
`00 00 01`/`00 00 00 01`; SPS/PPS/AUD (types 7/8/9) are held in `pending` and
prepended to the next VCL NAL; one VCL NAL produces one message, so a frame is
flushed when the following NAL arrives (one-frame latency). Audio bytes are
aligned to 4 bytes (one stereo s16 sample) and split into 7680-byte chunks;
`AUDIO_CHUNK = 7680` is 40 ms at 48 kHz/2 ch/16-bit
(`stream/server.py:24-25,313-318`).

### Session and segment changes

`current` names the session to read; `manifest.json` in that directory carries
one segment count per stream. Both are replaced by an atomic rename on the head
unit, so a poll never sees a half-written pointer or manifest.

| Event | Detection | Reaction |
| --- | --- | --- |
| new session | `current` resolves to a different name than the previous poll | broadcast `{"type":"reset"}`, then a fresh `hello`; reopen both files at offset 0/44; clear the GOP; re-extract SPS/PPS (`stream/server.py:130-140`) |
| segment rollover | a stream's manifest count advanced | reopen that one file at offset 0; no `reset`; the new segment's SPS/PPS travel in-band with its first frame, so the avcC description is kept (`stream/server.py:142-149,186-199,290-297`) |
| pointer absent | `readlink` fails | nothing; the loops keep reading the last known session |
| file shorter than the offset | only used to avoid a negative read | wait for the epoch change; no session inference from file size (`stream/server.py:210-213`) |

A session change and a rollover are the only reasons the server reopens a file.
A file that is truncated without a manifest update leaves the reader idle until
the next poll, never decoding bytes at a stale offset. A new session's files
appear when the AA channels open, which can be seconds after the pointer moves;
the tail loops wait for the file instead of failing
(`stream/server.py:153-166`).

### Startup and late clients

Video seeks to the last IDR before the first read, so a fresh server replays the
tail of the current session before any new data arrives. Audio starts at the
current end of file. A client that connects later gets `hello`, then every
cached message since the last keyframe (`self.gop`), then joins the broadcast
set (`stream/server.py:322-335`). The cache is capped at `max_gop = 100000`
messages and then cleared, which is unreachable at the measured ~1800-frame GOP.

## Wire protocol

Server to client, text (JSON):

| Message | Fields | Meaning |
| --- | --- | --- |
| `hello` | `type`, `width`, `height`, `fps`, `codec`, `description` | decoder configuration; sent on connect, after a `reset`, and when SPS/PPS first appear |
| `reset` | `type` | the capture session changed; drop the decoder and the audio anchor |

`width`, `height` and `fps` are constants (1280, 720, 30), not derived from the
SPS or `openauto.ini`. `codec` is `avc1.<profile><compat><level>` from the SPS
(e.g. `avc1.42801f`); `description` is base64 avcC, `null` until SPS/PPS exist.

Server to client, binary. Header is 9 bytes, `struct.pack(">BQ", type, ts_us)`:

| Bytes | Type | Meaning |
| ---: | --- | --- |
| 0 | u8 | message type |
| 1..8 | u64 big-endian | timestamp in microseconds |
| 9.. | payload | AVCC video sample or PCM bytes |

| Type | Payload |
| ---: | --- |
| 1 | H.264 keyframe, AVCC |
| 3 | H.264 delta, AVCC |
| 2 | PCM s16le, 48 kHz, 2 ch, 7680 B max per message |

An AVCC sample is the concatenation of `u32 big-endian length + NAL` for every
NAL in the access unit. The avcC `description` is
`01 <SPS[1..3]> FF E1 <u16 len> <SPS> 01 <u16 len> <PPS>`: `FF` declares 4-byte
NAL lengths and `E1` declares one SPS (`stream/lib/h264.py:67-76`).

Client to server, text (JSON):

| Message | Fields | Meaning |
| --- | --- | --- |
| `tap`, `down`, `move`, `up` | `type`, `x`, `y` integers | validated, then written to the FIFO as `"<cmd> <x> <y>\n"` |

Unknown types and non-integer coordinates are dropped. Each event opens a fresh
`O_WRONLY|O_NONBLOCK` FIFO fd and closes it.

## Timestamps

`ts_us` is `time.monotonic() - t0` for the server process, sampled when the bytes
are read (`stream/server.py:64-65`). It is not the AA presentation time and it
restarts at 0 for every server run. A poll that returns a backlog assigns
near-identical timestamps to chunks that each span 40 ms.

## Browser client

`stream/web/index.html` + `stream/web/app.js`.

| Behaviour | Detail |
| --- | --- |
| WebSocket URL | `ws://<location.hostname>:8081`, hardcoded (`app.js:28-29`) |
| Reconnect | every 2 s after close or error; `hello` reconfigures the decoder (`app.js:27-48,65-97`) |
| Video | `VideoDecoder` configured with `codec`, avcC `description`, `codedWidth`, `codedHeight`, `optimizeForLatency`; frames drawn to the canvas |
| Canvas | fixed `width=1280 height=720` in `index.html:32`; CSS stretches it to the window |
| Decode queue | delta frames are dropped while `decodeQueueSize > 200`; keyframes are always decoded (`app.js:106-118`) |
| Audio | muted by default; the first unmute click creates/resumes an `AudioContext` at 48 kHz, `latencyHint: "interactive"` (`app.js:130-140,237-256`) |
| Audio scheduling | first chunk anchors at `currentTime + 0.15`; later chunks play at `anchor + (ts - firstTs)`; a chunk more than 0.2 s late is dropped; a jump more than 2 s ahead re-anchors (`app.js:142-175`) |
| Gesture | press then release within 8 px sends one `tap`; movement past 8 px sends `down` at the press point, `move` at most every 50 ms, `up` at release (`app.js:192-235`) |
| Cancel | `pointercancel` sends `up` at the press point, not the last move point (`app.js:230-235`) |
| Stats | frame counter and audio on/off once per second; the counter is not reset by `reset` |

WebCodecs requires a secure context. `http://localhost` and `http://127.0.0.1`
qualify; a page served over HTTPS cannot open `ws://` (mixed content), so the
browser client is limited to plain localhost HTTP (`app.js:29`; vendor
constraint).

## Quirks

### A late client gets video without audio

Symptom: a new browser tab shows a moving picture with silence for up to a
minute.
Cause: video starts at the last IDR (up to 8 MiB / ~80 s back) while audio starts
at EOF.
Workaround: wait for the next keyframe, or restart the server after a fresh AA
session.
Location: `stream/server.py:172-176,278-284`.

### One stalled client freezes every view

Symptom: the picture freezes for all clients when one tab is backgrounded or
stops reading.
Cause: `flush_frame` holds `self.lock` and awaits `ws.send` sequentially per
client; a full TCP window blocks the video and audio loops.
Workaround: keep one tab; close backgrounded tabs. The page opens one socket per
tab, and the server broadcasts to all of them.
Location: `stream/server.py:82-92,258-272,322-335`.

### Joining mid-GOP decodes a broken picture

Symptom: a new tab shows smeared or blocky video until the next IDR (~60 s).
Cause: the cached GOP is pushed as one burst; the page drops deltas once
`decodeQueueSize > 200` and there is no keyframe request.
Workaround: reload after the next IDR.
Location: `stream/server.py:322-335`, `stream/web/app.js:109`.

### Audio timestamps cluster and overlap

Symptom: several PCM chunks start at the same instant after a read backlog.
Cause: read-time timestamps sampled per chunk in one loop iteration.
Workaround: none in the client; reload to re-anchor.
Location: `stream/server.py:313-318`, `stream/web/app.js:154`.

### Restarting the server silences audio

Symptom: audio stays silent after a server restart while the page remains open;
video recovers via `hello`.
Cause: `t0` restarts at 0, so every new chunk is older than
`currentTime - 0.2` and is dropped; the anchor is only reset by unmute or
`reset`.
Workaround: reload the page, or unmute again.
Location: `stream/web/app.js:149-155`.

### Re-anchoring keeps the stale `when`

Symptom: after a jump larger than 2 s, one chunk plays late over the following
audio.
Cause: the jump branch resets `firstAudioTs` and `audioBaseTime` but keeps the
`when` computed before the jump for the current chunk.
Workaround: reload.
Location: `stream/web/app.js:154-160`.

### Lost input is silent

Symptom: taps do nothing and the page looks alive.
Cause: a FIFO write failure (`ENXIO` with no reader, `ENOENT` after cleanup) is
printed in the server log only.
Workaround: check the server log; keep `autoapp` running and the FIFO writer
attached.
Location: `stream/server.py:351-360`.

### The page ignores `--ws-port`

Symptom: changing `--ws-port` leaves the page unable to connect.
Cause: `app.js:29` hardcodes `ws://<host>:8081`.
Workaround: keep the default ports, or edit `app.js`.
Location: `stream/web/app.js:29`.

### Input frames are unlimited

Symptom: any local page can push a multi-gigabyte text frame or flood input.
Cause: `max_size=None` on the WebSocket server and no rate limiting.
Workaround: loopback binding is the only boundary; do not expose the port.
Location: `stream/server.py:336-360`, `stream/auriga_stream.py:45`.

## Consumer contract

A local process can consume the WebSocket instead of the browser: read `hello`,
decode AVCC with the base64 avcC, treat type 1/3 as video and type 2 as PCM, and
reconfigure on `hello`/`reset`. Timestamps are a server-relative clock, useful
only for ordering. The protocol is unauthenticated and loopback-only; fronting it
with HTTPS breaks the delivered page (mixed content) and is not a supported
deployment.
