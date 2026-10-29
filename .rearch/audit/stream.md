# Audit: stream

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| README.md | 389 | yes |
| AGENTS.md | 162 | yes |
| RUNBOOK.md | 306 | yes |
| stream/README.md | 99 | yes |
| stream/auriga_stream.py | 423 | yes |
| stream/web/app.js | 258 | yes |
| stream/web/index.html | 36 | yes |
| captures/README.md | 33 | yes |
| captures/2026-10-28-macos-input.jsonl | 1 | yes |
| captures/2026-10-28-macos-session2-input.jsonl | 4 | yes |
| captures/2026-10-28-session2-input.jsonl | 1 | yes |

Cross-checked (read, not assigned): `patches/openauto-capture.patch` (video/audio/input sinks, ServiceFactory), `openauto/src/autoapp/Projection/Auriga{VideoOutput,AudioOutput,InputDevice}.cpp`, `openauto-config/{run.sh,run-mac.sh,openauto.ini}`, `scripts/{mac-headunit-start.sh,mac-headunit-stop.sh,pi-start.sh,pi-stop.sh,mac-start.sh,aa-tap.sh}`, `logs/stream-mac-*.log`, `captures/` and `captures-mac/` file headers, live process/socket state.

## Functional behavior
- F1: HTTP server on `127.0.0.1:8080` serves static files from `stream/web` via `ThreadingHTTPServer` in a daemon thread; request logging disabled. `stream/auriga_stream.py:387-398`, `stream/auriga_stream.py:411`. Status: active.
- F2: WebSocket on `127.0.0.1:8081`, no auth, `max_size=None`; on connect the client first gets one JSON `hello` `{type,width,height,fps,codec,description}` where `description` is base64 avcC built from SPS/PPS in the capture file. `stream/auriga_stream.py:78-86,168-180,343-356,417`. Status: active.
- F3: Video tail: read `video.h264` Annex-B, split NALs on `00 00 01` (4-byte start code handled), emit one VCL NAL per frame as `type:u8=1|3 | ts_us:u64 BE | AVCC sample (4-byte length prefix per NAL)`. `stream/auriga_stream.py:32-55,246-299`. Status: active.
- F4: Startup seeks to the last type-5 NAL within the last 8 MiB of the capture file; if none, offset 0. `stream/auriga_stream.py:89-113,135-136`. Status: active.
- F5: Late clients get the cached GOP (messages since the last keyframe) inserted into `self.gop` before being added to the broadcast set. `stream/auriga_stream.py:124,285-299,347-356`. Status: active.
- F6: Audio tail: skip the 44-byte WAV header, forward raw PCM in messages `type 2 | ts_us | payload` capped at 7680 bytes. `stream/auriga_stream.py:25-26,301-341`. Status: active.
- F7: Only `audio-media.wav` is streamed. Guidance/system WAVs (mono 16 kHz) are written by the sink but never read by the server or handled by the client. `stream/auriga_stream.py:403-404`, `stream/web/app.js:119-121`, `openauto/src/autoapp/Service/ServiceFactory.cpp` (`makeAudioOutput("guidance"/"system", 1, 16, 16000)`). Status: dead for the UI path.
- F8: Session truncation: if the file size drops below the read offset, the server closes/reopens at 0, re-extracts SPS/PPS, clears the GOP, broadcasts `{"type":"reset"}` then `hello`. `stream/auriga_stream.py:218-238`. Status: active (observed twice in `logs/stream-mac-20261029-074101.log`).
- F9: Client input: WS JSON `{type:"tap"|"down"|"move"|"up", x, y}` is validated and written as `"<cmd> <x> <y>\n"` to the FIFO with a fresh `O_WRONLY|O_NONBLOCK` fd per event. `stream/auriga_stream.py:357-381`. Status: active.
- F10: Browser: WebCodecs `VideoDecoder` configured from the avcC description, frames drawn to a 1280x720 canvas; WebAudio `AudioContext` created only on unmute; audio scheduled by message timestamp. `stream/web/app.js:65-97,130-175,237-253`. Status: active.
- F11: Audio is muted by default; first unmute click creates/resumes the AudioContext. `stream/web/app.js:13,237-256`, `stream/web/index.html:30`. Status: active.
- F12: Gesture semantics: >8 px movement sends `down` at the press point, throttled `move`s at 50 ms, `up` at release; otherwise a single `tap`. `stream/web/app.js:192-235`. Status: active.
- F13: Client reconnects to the WS every 2 s on close/error and reconfigures the decoder on `hello`. `stream/web/app.js:27-48,65-97`. Status: active.

## External facts and quirks
- X1: The captured AA stream is 1280x720 H.264 Baseline level 3.1, 4-byte Annex-B start codes, one slice per frame, SPS once, PPS once, IDR every ~1800 frames (2 IDRs in 3057 frames). Verified with ffprobe + NAL scan of `captures/2026-10-28-macos-session2-video.h264`; matches `stream/README.md:93-94` and `stream/auriga_stream.py:130`. Source: capture.
- X2: Measured bitrate of that capture is ~100 kB/s (12.27 MB / 122 s), so the 8 MiB IDR window (`stream/auriga_stream.py:29`) spans ~80 s of video versus a ~60 s GOP. Margin is thin; a busier screen (Maps at speed) can push the last IDR out of the window and fall back to offset 0, i.e. replay the whole file. Source: capture + code.
- X3: The WAV sink rewrites the 44-byte header every second of audio and stores sizes in 32-bit RIFF fields. `openauto/src/autoapp/Projection/AurigaAudioOutput.cpp:101-105,168-190`. Above ~4 GiB of audio (~6.2 h at 192 kB/s) the header wraps and the file stops being a valid WAV. Source: code.
- X4: The live capture files are already large and growing: `captures-mac/video.h264` 271 MB and `captures-mac/audio-media.wav` 345 MB at the time of the audit, from a single ~30 min session. Source: filesystem, matches `RUNBOOK.md:292`.
- X5: Session truncation is unconditional: `std::ios::trunc` in video, audio and input sinks. Prior-session data is unrecoverable, and the streamer sees the file shrink to 0 before the 44-byte header is rewritten, which is why "audio truncated, resetting" is logged twice per session. `openauto/src/autoapp/Projection/AurigaVideoOutput.cpp:39`, `AurigaAudioOutput.cpp:70`, `AurigaInputDevice.cpp:50`; `logs/stream-mac-20261029-074101.log`. Source: code + log.
- X6: WebCodecs needs a secure context; `localhost` qualifies, `ws://` from an HTTPS page does not (mixed content). `stream/web/app.js:29`, `AGENTS.md:119-121`. Source: vendor doc + code.
- X7: Live state shows 9 concurrent WS clients from one Brave renderer process (`lsof -iTCP:8081`: ports 60152…60169 ESTABLISHED, 9 server sockets) after 9 `client connected` lines with no disconnects in `logs/stream-mac-20261029-074101.log`. The page opens one socket per tab/window and the server broadcasts to all of them. Source: capture (live system state).
- X8: Runtime is Python 3.14.8 with `websockets` 17.3 (`.venv`); the single-argument `serve(handler)` form at `stream/auriga_stream.py:417` is valid there. Source: code + installed package.
- X9: `/tmp/auriga-in` is a real FIFO used as `autoapp` stdin; a `sleep 86400 > FIFO` writer keeps it open so `read()` never returns EOF. `openauto-config/run-mac.sh:22-27`, `openauto-config/run.sh:17-22`. Source: code.
- X10: `tap` sleeps 80 ms inside the single stdin reader thread, so taps are serialized; `down/move/up` are not delayed. `openauto/src/autoapp/Projection/AurigaInputDevice.cpp:167-176`. Source: code.

## Doc and code inconsistencies
- D1: `AGENTS.md:115` and `stream/README.md:78` state PCM arrives in "20 ms chunks"; code caps at 7680 bytes = 40 ms at 48 kHz stereo s16 and emits whatever was read, so message length is variable and may be far below 20 ms. `stream/auriga_stream.py:26,330-339`.
- D2: `stream/README.md:79` says the server sends text `reset`; the wire message is JSON `{"type":"reset"}`. `stream/auriga_stream.py:222`. A consumer following the doc literally breaks.
- D3: `RUNBOOK.md:239` writes `type:u8 | timestamp_us:u64 | payload` without byte order; `AGENTS.md:113` says `u64 BE`. Code is big-endian. `stream/auriga_stream.py:289,338`.
- D4: `stream/README.md:1` calls this the "live Mac client for the Pi head unit" and `README.md:365-366` calls `stream/` the "Pi WebSocket server"; both run on the Mac head unit too, which `README.md:53-69` and `AGENTS.md:11-34` describe as the primary path.
- D5: `AGENTS.md:98-99` promises a late client can "start decoding immediately" from the cached GOP. A busy GOP is ~1800 frames pushed in one burst; `stream/web/app.js:109` then drops every delta while `decodeQueueSize > 200`, so the client decodes a broken picture until the next IDR (up to ~60 s).
- D6: `AGENTS.md:43` lists `quit` as a FIFO command with no semantics. It sets `running_=false`, which only ends the input reader thread; `autoapp` keeps running and touch input is dead until restart. `openauto/src/autoapp/Projection/AurigaInputDevice.cpp:124,138-141,190-193`.
- D7: `captures/README.md:7-15` lists only the Pi-era artifacts; the `2026-10-28-macos-*` files cited by `RUNBOOK.md:270` (including the three assigned `*-input.jsonl` files) are not in the table.
- D8: `stream/README.md:45-53` documents a manual run, but neither it nor `AGENTS.md` documents `--http-port/--ws-port/--web`; the client hardcodes port 8081, so the port flags are unusable without editing `stream/web/app.js:29`.
- D9: `stream/README.md:69` says "the stream starts at the most recent H.264 IDR and then follows live"; that is true for video only. Audio starts at the current end of file, so a fresh client gets up to a minute of video with no audio. `stream/auriga_stream.py:136-140`.
- D10: `AGENTS.md:110-112` describes `hello` once, as a connect-time message; the server also re-sends it mid-stream on SPS discovery and after each reset, and clients must reconfigure. `stream/auriga_stream.py:210,236`.

## Assumptions to revalidate
- A1: The last IDR is always within 8 MiB (`stream/auriga_stream.py:29`). Depends on encoder bitrate and OpenAuto's ~60 s GOP with no bitrate cap; if false, a restart replays the entire capture at line speed.
- A2: The WAV header is exactly 44 bytes and contains no extra chunks (`stream/auriga_stream.py:25,138`). Any change to the sink's header format silently shifts all PCM by N bytes (audible garbage, no error).
- A3: One slice and one VCL NAL per frame. Frame grouping in `stream/auriga_stream.py:246-281` treats every VCL NAL as a frame; multi-slice frames would be sent as separate chunks and never assembled.
- A4: Timestamps mean "time the server read the bytes" (`stream/auriga_stream.py:153-154`). Any consumer wanting AA presentation times, A/V sync, or latency measurement is misled; the sinks discard the AA timestamp (`AurigaVideoOutput.cpp:55-56`).
- A5: Geometry is 1280x720 and 30 fps (`stream/auriga_stream.py:27,170-174`). `openauto.ini` `Video.Resolution=2` currently maps to 1280x720; any other value makes `hello` lie and breaks tap coordinate mapping.
- A6: Client, server and browser share a host and ports 8080/8081 (`stream/web/app.js:28-29`). HTTPS fronting, a reverse proxy, or `--ws-port` all break the page.
- A7: Exactly one `autoapp` and one stream server own a capture directory (`AGENTS.md:124`); nothing enforces it beyond pgrep checks in the start scripts.

## Bugs
- B1 [high]: Late-client GOP replay is decoded-losing by construction. The server pushes the whole GOP (~1800 frames, ~7 MB) inside one burst; `app.js` discards deltas once 200 chunks are queued and has no way to request a keyframe. `stream/auriga_stream.py:347-356`, `stream/web/app.js:109`. Scenario: open a second tab mid-GOP -> picture smeared/blocks for up to ~60 s until the next IDR.
- B2 [medium-high]: One slow or stalled client blocks every client and the capture pipeline. `flush_frame` holds `self.lock` while `broadcast` awaits `ws.send` sequentially for each client, and the new-client GOP send happens under the same lock. `stream/auriga_stream.py:156-166,290-299,347-356`. Scenario: a backgrounded tab whose TCP window fills -> video loop stalls -> all views freeze; with 9 live sockets (X7) the stall is more likely.
- B3 [medium]: WebAudio re-anchor keeps the stale `when`. After the jump branch, `when` is not recomputed, so that chunk is still scheduled at the old future time while later chunks start at `now + 0.15`. `stream/web/app.js:154-174`. Scenario: stream hiccup > 2 s -> one chunk plays ~2 s late over the following audio (echo/overlap).
- B4 [medium]: Backward timestamp jumps are never recovered. `firstAudioTs` is only reset on unmute or `reset`; a server restart resets `t0` to 0, so every new chunk yields `when < currentTime - 0.2` and is dropped forever. `stream/web/app.js:149-155`, `stream/auriga_stream.py:122,153-154`. Scenario: restart `auriga_stream.py` while the page stays open -> audio silent until reload; video recovers via the re-sent `hello`.
- B5 [medium]: Audio timestamps are read-time, so batched chunks get near-identical timestamps although their content spans 20-40 ms each. `stream/auriga_stream.py:334-339` with `stream/web/app.js:154`. Scenario: any read backlog (GC pause, file copy, 9 clients) -> several chunks scheduled at the same instant, overlapping playback.
- B6 [medium]: Video truncation detection compares size against a byte offset only once per 8 ms. If a new session truncates and regrows past the old offset between two polls, the reset is missed and the reader continues at a stale offset in the new file. `stream/auriga_stream.py:218,240-244`. Scenario: session restart early in a session (small offsets) -> garbage/H.264 errors until the next IDR or restart.
- B7 [low]: Audio truncation resets only `audio_offset` and never notifies clients; the (documented) reset is emitted by the video loop. `stream/auriga_stream.py:316-324` versus `stream/auriga_stream.py:222`. Scenario: audio-only truncation -> client keeps the dead stream's clock and mixes old/new PCM.
- B8 [low]: `hello` geometry and fps are constants, not derived from the SPS/AA configuration. `stream/auriga_stream.py:27,168-180`. Scenario: `Video.Resolution` changed -> client configures a wrong coded size; canvas and tap mapping stay at 1280x720.
- B9 [low]: Audio/video sync is structurally offset: video is painted on arrival while audio is scheduled `+150 ms`. `stream/web/app.js:79-83,151`. Scenario: any spoken content in a video clip is 150 ms+ behind the picture, with no mechanism to correct.
- B10 [low]: Input loss is silent. FIFO write failures (ENXIO when `autoapp` is down) are only printed server-side; the browser shows no error. `stream/auriga_stream.py:373-381`. Scenario: taps during an AA reconnect do nothing and look like a UI freeze.
- B11 [low]: `pointercancel` sends `up` at the press point, not the last move point. `stream/web/app.js:230-235`. Scenario: scroll/gesture cancellation mid-drag -> AA receives a jumpy release.
- B12 [low]: WS has no message size limit (`max_size=None`) and no rate limiting on input. `stream/auriga_stream.py:417,357-381`. Scenario: any local page can push a multi-GB text frame and OOM the server.
- B13 [low]: Canvas aspect can distort. Fixed 1280x720 canvas is stretched by `width:100%; flex:1`; `object-fit: contain` has no reliable effect on canvas raster content in Chrome. `stream/web/index.html:20-21,32`. Scenario: non-16:9 window -> squashed UI; tap coordinates still correct (they use the rect).
- B14 [low]: PCM is chunked at arbitrary byte offsets, so messages can be a few bytes (sub-millisecond) and each gets its own `AudioBufferSourceNode`. `stream/auriga_stream.py:330-339`, `stream/web/app.js:162-174`. Scenario: high-frequency source scheduling churn; occasional click-sized buffers.

## Dead code, leftovers, stale comments
- L1: `stream/auriga_stream.py:28` `VIDEO_FRAME_US` defined and never used.
- L2: `stream/auriga_stream.py:125` `max_gop = 100000` with a comment about waiting for the next keyframe; at ~1800-frame GOPs the branch at `:295-298` is unreachable, so the stated safety net does not exist.
- L3: `stream/auriga_stream.py:141-151` startup print of SPS/PPS/offsets is the only diagnostics; no periodic stats (drops, queue depth, bytes).
- L4: `stream/web/app.js:60` resets `firstAudioTs` on `reset` but never resets `videoFrames`; the stats line keeps counting across sessions.
- L5: `stream/auriga_stream.py:58` `extract_sps_pps(limit=512*1024)` is only ever called with the default; the parameter is unused flexibility.
- L6: `stream/__pycache__/` and `scripts/__pycache__/` are present in the working tree (gitignored).
- L7: `stream/web/index.html:34` no favicon; every page load produces a 404 that `log_message` hides (`stream/auriga_stream.py:392-393`).
- L8: `scripts/mac-headunit-stop.sh:24` leaves `/tmp/auriga-in` behind, unlike `scripts/pi-stop.sh:19`; a later `echo 'tap ...' > /tmp/auriga-in` then hits a FIFO with no reader (`ENXIO`) and `scripts/aa-tap.sh` fails silently under `ssh`.
- L9: Stale doc framing: `stream/README.md:1-6` still presents the Pi prototype as the primary use; the Mac head-unit mode (`stream/README.md:8-10`) has no protocol differences documented.

## Improvement areas
- I1: Decouple broadcast from capture. Per-client `asyncio.Queue` with drop-oldest for deltas and a bounded send task; then `flush_frame` never awaits a socket and `self.lock` shrinks to GOP bookkeeping. Fixes B2.
- I2: Make the cached GOP replay streaming-friendly: cap the replay to the last N frames after the keyframe, or send the keyframe plus latest frames and let the client request a fresh IDR. Fixes B1 with the same protocol addition.
- I3: Add a client→server control message (`{"type":"keyframe"}`/`{"type":"stats"}`) so the browser can resync after dropped deltas instead of waiting for the encoder's 60 s IDR.
- I4: Replace fabricated timestamps: carry the AA timestamp from the sinks (video `write(timestamp, buffer)` already receives it and discards it, `openauto/src/autoapp/Projection/AurigaVideoOutput.cpp:55-56`; same for audio) and expose one stream clock. Removes B5 and the A/V offset in B9.
- I5: Stream guidance and system audio too (extra `type` values, or a mixed track server-side). Today navigation prompts are captured but invisible to the browser (F7).
- I6: Stream restart should not silently break audio: handle backward jumps by re-anchoring (`when < 0` -> reset anchor) in `stream/web/app.js:149-155`. Fixes B4 with no protocol change.
- I7: Derive `width`/`height`/`fps` from the SPS VUI instead of constants, and apply `hello` geometry to the canvas.
- I8: Serve WS on the same origin/port as HTTP (or emit the WS URL from the server), so HTTPS fronting and `--ws-port` work. Removes the hardcoded 8081 (`stream/web/app.js:29`) and the mixed-content trap (X6).
- I9: Per-session capture files or an explicit session id in the protocol, so a reset never destroys the prior capture and the streamer's truncation heuristic (`size < offset`) disappears (X5, B6).
- I10: Bound capture growth: rotate video, and switch WAV to RF64/64-bit sizes or per-session files before the 4 GiB wrap (X3, `RUNBOOK.md:292`).
- I11: Enforce one page/one socket: close the previous socket in `connect()` and stop broadcasting to abandoned clients; 9 live sockets is 9x the send work per frame (X7).
- I12: Make truncation detection size-independent (e.g. compare first bytes / inode / mtime, or rely on a header the sink writes at open), removing the 8 ms race (B6).

## Interfaces
- Exposes: HTTP `http://127.0.0.1:8080` (static `stream/web`); WebSocket `ws://127.0.0.1:8081` — server→client JSON `hello` / `{"type":"reset"}`, binary `type:u8 | timestamp_us:u64 BE | payload` with type 1 = key, 3 = delta (AVCC), 2 = PCM s16le 48 kHz stereo; client→server JSON `{type:"tap"|"down"|"move"|"up", x, y}`. `stream/auriga_stream.py:168-180,289,338,364-381`.
- Consumes: `<capture-dir>/video.h264` (Annex-B, 4-byte start codes, SPS/PPS at head) and `<capture-dir>/audio-media.wav` (44-byte header, 48 kHz/16/2) written by the patched OpenAuto sinks; truncation on new AA session; FIFO `/tmp/auriga-in` = `autoapp` stdin (`openauto-config/run-mac.sh:22-27`, `openauto-config/run.sh:17-22`).
- Consumes (runtime): `websockets` 17.3 in `.venv` (Python 3.14.8); `logs/stream-*.log` for diagnostics; ports 8080/8081 free.
- Threading: one asyncio event loop running `video_loop`, `audio_loop`, the WS server and one task per client; an `asyncio.Lock` serializes GOP bookkeeping, broadcast and the new-client `hello`+GOP send (`stream/auriga_stream.py:123,290,347`). The HTTP server is a separate daemon thread (`ThreadingHTTPServer`, one thread per request). FIFO writes use a fresh fd per event from the WS task; `autoapp` reads the same FIFO on its own stdin thread.

## Open questions for the user
- Q1: Must navigation/system audio be audible in the browser (separate stream or server-side mix), or is media-only acceptable?
- Q2: Is the Pi remote-UI path still a supported target, or is macOS the only mode that must keep working?
- Q3: Are multiple simultaneous browser clients a requirement, or is one viewer per session the rule?
- Q4: Is per-session capture retention required (video/audio kept after a reset), or is truncation-on-session acceptable?
- Q5: May the stream protocol change (new message types, keyframe requests, AA timestamps), or must the current framing stay byte-compatible for an existing consumer?
- Q6: Should the page keep working behind an HTTPS proxy, or is plain `localhost` HTTP the only supported deployment?
