# Stream protocol

`stream/auriga_stream.py` is the CLI; `stream/server.py` follows the head unit's
current capture session and serves it to a browser over a local WebSocket:
H.264 in AVCC framing, PCM s16le stereo, and a JSON control channel. It also
serves the static client from `stream/web`. Exactly one browser viewer is served
at a time (`FR-STR-14`).

## Endpoints and process model

| Endpoint | Address | Purpose |
| --- | --- | --- |
| HTTP | `127.0.0.1:8080` | static files from `stream/web` (`ThreadingHTTPServer`, daemon thread, request logging off) plus `config.json` |
| WebSocket | `127.0.0.1:8081` | `hello`, video/audio frames, `reset`, `status`, client input and keyframe requests |

Both bind loopback only and have no authentication (`stream/server.py`
`serve_http`; `stream/auriga_stream.py`). Nothing else may be exposed.

One asyncio loop runs `session_loop`, `video_loop`, `audio_loop`, the WebSocket
server and the viewer's send task. `session_loop` polls the session pointer every
50 ms and bumps a per-stream epoch; the tail loops reopen their file when their
epoch moves (`stream/server.py` `session_loop`, `adopt`, `video_loop`,
`audio_loop`). The HTTP server is a separate daemon thread.

The tail loops never await a socket: they append to the viewer's bounded queue
and return (`stream/server.py` `Viewer`). `Viewer.run` is the only task that
awaits a socket, so a browser that stops reading costs queue depth, never capture
latency (`NFR-02`). `self.lock` covers GOP bookkeeping only and is never held
across a send.

| Argument | Default | Note |
| --- | --- | --- |
| `--capture-dir` | `$AURIGA_CAPTURE_DIR`, else `<repo>/captures-mac` | directory that holds `current` and the `session-*` directories |
| `--fifo` | `$AURIGA_INPUT_FIFO`, else `/tmp/auriga-in` | must match `autoapp`'s stdin |
| `--http-port` | `8080` | also served as `config.json` |
| `--ws-port` | `8081` | the page reads it from `config.json`; `scripts/auriga.sh` passes `AURIGA_HTTP_PORT`/`AURIGA_WS_PORT` |
| `--web` | `stream/web` | static root |

`GET /config.json` returns `{"wsPort": <port>}`. The page fetches it before
connecting, so the WS listener can move without editing `app.js`; without the
file (an older server) the page falls back to 8081.

## Capture inputs

The head unit writes one directory per AA session and publishes a `current`
pointer; the on-disk contract is in `docs/Android Auto head unit.md`. The server
follows the pointer instead of watching file sizes.

| Input | Format | Read position |
| --- | --- | --- |
| `current` | relative symlink to `session-<id>` | polled every 50 ms (`stream/lib/session.py` `read_current`, `SessionFollower`; `stream/server.py` `session_loop`) |
| `manifest.json` | `{session, width, height, fps, <stream>: count}` | polled with `current`; names the `hello` geometry and the segment counts (`stream/lib/session.py` `parse_manifest`, `read_manifest`; `stream/server.py` `adopt`) |
| `video.h264` | Annex-B H.264, 4-byte start codes, SPS/PPS at the head of each segment (see `docs/Android Auto head unit.md`) | at startup: last type-5 NAL within the last 8 MiB, else offset 0 (`stream/lib/h264.py` `find_last_idr`; `stream/server.py` `video_loop`). After a session or segment change: offset 0 |
| `audio-media.wav` | 44-byte PCM WAV header, 48 kHz, 2 ch, 16-bit | at startup: end of file, even when the file appears after the first poll (`stream/server.py` `open_when_ready` with `at_end`); after a change: byte 44 |
| input FIFO | text lines `tap|down|move|up X Y` | written per client event (`stream/server.py` `handle`) |

Only `audio-media.wav` is streamed. `audio-guidance.wav` and `audio-system.wav`
are written by the head unit and read by nothing.

Tail loops poll file size every 8 ms, reading at most 1 MiB of video or 256 KiB of
audio per poll so a backlog cannot stall the loop. Video bytes are split on
`00 00 01`/`00 00 00 01`; `FrameAssembler` holds SPS/PPS/AUD (types 7/8/9) back
and prepends them to the next VCL NAL, and one VCL NAL produces one message, so a
frame is flushed when the following NAL arrives or at the end of the read
(one-frame latency) (`stream/lib/h264.py` `FrameAssembler`;
`stream/server.py` `video_loop`). Audio bytes are aligned to 4 bytes (one stereo
s16 sample) and split into 7680-byte chunks, except a final, shorter chunk at a
read boundary; `AUDIO_CHUNK = 7680` is 40 ms at 48 kHz/2 ch/16-bit
(`stream/server.py` `audio_loop`).

### Session and segment changes

`current` names the session to read; `manifest.json` in that directory carries
the geometry and one segment count per stream. Both are replaced by an atomic
rename on the head unit, so a poll never sees a half-written pointer or manifest.

| Event | Detection | Reaction |
| --- | --- | --- |
| new session | `current` resolves to a different name than the previous poll | drop everything queued, send `{"type":"reset"}` then a fresh `hello`; reopen both files at offset 0/44; clear the GOP; re-extract SPS/PPS; restart the content clock (`stream/server.py` `adopt`, `video_loop`, `audio_loop`) |
| segment rollover | a stream's manifest count advanced | reopen that one file at offset 0; no `reset`. For video, re-read the new segment head: the avcC description is kept when SPS/PPS are unchanged, and a fresh `hello` is sent when they differ (`stream/server.py` `adopt` sets `codec_stale`, `video_loop` re-reads) |
| pointer absent | `readlink` fails | nothing; the loops keep reading the last known session |
| file shorter than the offset | only used to avoid a negative read | wait for the epoch change; no session inference from file size (`stream/server.py` `video_loop`) |

A session change and a rollover are the only reasons the server reopens a file.
A file that is truncated without a manifest update leaves the reader idle until
the epoch changes, never decoding bytes at a stale offset; there is no log line
for that state. A new session's files appear when the AA channels open, which can
be seconds after the pointer moves; the tail loops wait for the file instead of
failing (`stream/server.py` `open_when_ready`).

## Viewer, replay and resynchronisation

One viewer, the most recent WebSocket connection. A second connection replaces
the first: the old socket is closed with code `4001` (`REPLACED_CODE`), and only
then is the new viewer installed, so no video can be queued before its `hello`.
The page stops reconnecting on `4001`. Each viewer owns a bounded queue of 240
messages (`VIEWER_QUEUE`) drained by its own send task (`stream/server.py`
`Viewer`, `handle`).

| Queue rule | Effect |
| --- | --- |
| overflow drops audio first | a sound gap is cheaper than a broken video chain (`Viewer._make_room`) |
| overflow then drops the oldest video | the viewer is marked unsynced and its queued video is dropped; deltas are skipped until the next keyframe (`Viewer.push_video`, `clear_video`) |
| a keyframe clears queued video | frames older than a keyframe cannot be shown (`Viewer.push_video`) |

The GOP cache holds the last keyframe and the frames after it, bounded to 2400
frames (~80 s at 30 fps, `GOP_MAX_FRAMES`; `stream/lib/h264.py` `GopBuffer`). A
client that connects mid-GOP gets `hello` then the cached frames from the
keyframe, so it starts on a decodable picture instead of waiting for the next
encoder IDR. When the cache exceeds the bound it is cleared and viewers wait for
the next keyframe.

The client asks for the same replay with `{"type":"keyframe"}`; the server drops
queued video, re-sends `hello` and replays the cache (`stream/server.py`
`handle`). The page sends it on a content-timestamp gap, on a decoder error, and
when its decode queue exceeds its cap (`stream/web/app.js` `requestKeyframe`,
`handleBinary`). An empty cache means the next live keyframe is the resync
point.

## Wire protocol

Server to client, text (JSON):

| Message | Fields | Meaning |
| --- | --- | --- |
| `hello` | `type`, `width`, `height`, `fps`, `codec`, `description` | decoder configuration and canvas geometry; sent on connect, after a `reset`, after a keyframe request, when SPS/PPS first appear, and after a rollover whose SPS/PPS differ |
| `reset` | `type` | the capture session changed; drop the decoder, the video-gap state and the audio anchor |
| `status` | `type`, `text` | a server-side condition the page should show; today only an input-FIFO write failure |

`width`, `height` and `fps` come from the session's `manifest.json`, which the
head unit writes from `Video.Resolution` / `Video.FPS`
(`stream/server.py` `hello`; `docs/Android Auto head unit.md`). The parser falls
back to 1280/720/30 only when a manifest is absent or carries no geometry
(`stream/lib/session.py`). `fps` is rounded to an integer for the content clock
and reported as that integer.
`codec` is `avc1.<profile><compat><level>` from the SPS (e.g. `avc1.42801f`);
`description` is base64 avcC, `null` until SPS/PPS exist. A truncated parameter
set (a partially flushed segment head) is ignored until it is complete; it never
reaches `build_avcc`.

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
NAL in the access unit (`stream/lib/h264.py` `avcc_sample`). The avcC
`description` is `01 <SPS[1..3]> FF E1 <u16 len> <SPS> 01 <u16 len> <PPS>`: `FF`
declares 4-byte NAL lengths and `E1` declares one SPS (`stream/lib/h264.py`
`build_avcc`, which rejects a parameter set shorter than 4 bytes).

Client to server, text (JSON):

| Message | Fields | Meaning |
| --- | --- | --- |
| `tap`, `down`, `move`, `up` | `type`, `x`, `y` integers | validated, then written to the FIFO as `"<cmd> <x> <y>\n"` |
| `keyframe` | `type` | replay the cached GOP so the decoder resynchronises |

Unknown types and non-integer coordinates are dropped. Each input event opens a
fresh `O_WRONLY|O_NONBLOCK` FIFO fd and closes it; a failure is logged and
reported to the page as `status` (`stream/server.py` `handle`).

## Timestamps

`ts_us` comes from one content clock per session: video is
`frame_index * 1_000_000 / fps` and audio is
`sample_index * 1_000_000 / 48000` (`stream/lib/clock.py`;
`stream/server.py` `flush_frame`, `audio_loop`). It is not the AA presentation
time. Each stream's counter restarts at 0 when the session changes, so a read
backlog cannot cluster timestamps. Video and audio start at different file
positions, so `ts_us` is a per-stream counter, not a shared timeline: the offset
between them is whatever the capture files contain at connect time.

## Browser client

`stream/web/index.html` + `stream/web/app.js`.

| Behaviour | Detail |
| --- | --- |
| WebSocket URL | `ws://<location.hostname>:<wsPort>`, where `wsPort` comes from `config.json` (fallback 8081) (`app.js` `loadConfig`, `connect`) |
| Sockets | at most one per page: `connect()` closes the previous socket before opening a new one (`app.js`) |
| Reconnect | every 2 s after a close; a `4001` close means another tab took the stream, so the page stops reconnecting and says so (`app.js` `connect`) |
| Video | `VideoDecoder` configured with `codec`, avcC `description`, the `hello` geometry as coded size, `optimizeForLatency`; frames drawn to the canvas |
| Canvas | sized from `hello` (and from the decoded frame when they differ); the CSS keeps the intrinsic ratio inside the window and disables scrolling/zooming gestures (`app.js` `applyGeometry`; `index.html`) |
| Keyframes | deltas are dropped while no keyframe has arrived; a content gap over 250 ms, a decoder error, or a decode queue over 2400 chunks triggers a `keyframe` request (`app.js` `handleBinary`, `requestKeyframe`) |
| Audio | muted by default; the first unmute click creates/resumes an `AudioContext` at 48 kHz, `latencyHint: "interactive"`; muting suspends it and stops scheduled chunks (`app.js` `setMuted`) |
| Audio scheduling | first chunk anchors at `currentTime + 0.15`; later chunks play at `anchor + (ts - firstTs)`; a chunk more than 0.2 s late is dropped; a backward jump re-anchors; a jump more than 1 s ahead re-anchors and recomputes this chunk's start (`app.js` `playAudio`) |
| Gesture | primary pointer / left mouse button only; press then release within 8 px sends one `tap` at the press point; movement past 8 px sends `down` at the press point, `move` at most every 50 ms, `up` at release |
| Cancel | `pointercancel` sends `up` at the last move point (`app.js`) |
| Stats | decoded frames, dropped frames and the audio state (`off`, `suspended`, `running`) once per second; reset with `reset` |

WebCodecs requires a secure context. `http://localhost` and `http://127.0.0.1`
qualify; a page served over HTTPS cannot open `ws://` (mixed content), so the
browser client is limited to plain localhost HTTP (`app.js`; vendor constraint).

## Quirks

### A late client gets video without audio

Symptom: a new browser tab shows a moving picture with silence for up to a
minute.
Cause: video starts at the last IDR (up to 8 MiB / ~80 s back) while audio starts
at EOF.
Workaround: wait for the next keyframe, or restart the server after a fresh AA
session.
Location: `stream/server.py` `video_loop`, `audio_loop`.

### A keyframe request during a long GOP replays old video

Symptom: after a resync the picture runs ahead of real time while the replay
catches up.
Cause: the replay is the cached GOP from its keyframe; the client decodes it
faster than real time to reach the live edge.
Workaround: none needed; the page catches up on its own. A GOP longer than 2400
frames clears the cache instead and the page waits for the next encoder IDR.
Location: `stream/lib/h264.py` `GopBuffer`, `stream/server.py` `replay`.

### A dropped frame waits for the next keyframe

Symptom: the picture freezes for up to one GOP (~60 s) instead of showing
artifacts.
Cause: the bounded viewer queue drops the oldest video when the browser keeps
falling behind; the deltas that follow have no reference, so they are skipped
until the next keyframe. The same rule applies inside the capture file when the
head unit's writer queue overflows: it drops deltas until the next IDR.
Workaround: the page issues a `keyframe` request when its decode queue overflows
or the content clock shows a gap, which returns it to the cached GOP.
Location: `stream/server.py` `Viewer`, `stream/web/app.js` `handleBinary`.

### Lost input is silent

Symptom: taps do nothing and the page looks alive.
Cause: a FIFO write failure (`ENXIO` with no reader, `ENOENT` after cleanup) is a
server-side condition, not a page event.
Workaround: the page shows the server's `status` text; keep `autoapp` running and
the FIFO writer attached.
Location: `stream/server.py` `handle`.

### Input frames are unlimited

Symptom: any local page can push a multi-gigabyte text frame or flood input.
Cause: `max_size=None` on the WebSocket server and no rate limiting.
Workaround: loopback binding is the only boundary; do not expose the port.
Location: `stream/server.py` `handle`, `stream/auriga_stream.py`.

## Consumer contract

A local process can consume the WebSocket instead of the browser: read `hello`,
decode AVCC with the base64 avcC, treat type 1/3 as video and type 2 as PCM,
reconfigure on `hello`, discard state on `reset`, and send `{"type":"keyframe"}`
when frames were lost. Only one consumer is served; a second connection replaces
the first. Timestamps are a session-relative content clock, useful for A/V
alignment and gap detection. The protocol is unauthenticated and loopback-only;
fronting it with HTTPS breaks the delivered page (mixed content) and is not a
supported deployment.
