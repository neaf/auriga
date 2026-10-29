# Audit: final module — stream server + libs

Scope: `stream/auriga_stream.py`, `stream/server.py`, `stream/lib/{h264,clock,session}.py`,
`tests/test_{h264,clock,session,server}.py`, `docs/Stream protocol.md`, checked against
`.rearch/requirements.md` (STR block, NFR-02/03/05, FR-RUN-06).
Test state: `.venv/bin/python -m unittest discover -s tests` → 94 tests OK
(30 h264 / 13 clock / 38 session / 13 server). System `python3` (3.9) errors 6 Viewer tests.

## Coverage
| File | Lines | Read fully |
| --- | --- | --- |
| stream/auriga_stream.py | 51 | yes |
| stream/server.py | 499 | yes |
| stream/lib/h264.py | 218 | yes |
| stream/lib/clock.py | 62 | yes |
| stream/lib/session.py | 214 | yes |
| tests/test_h264.py | 218 | yes |
| tests/test_clock.py | 83 | yes |
| tests/test_session.py | 341 | yes |
| tests/test_server.py | 269 | yes |
| docs/Stream protocol.md | 268 | yes |

Also read for verification only: `patches/openauto-capture.patch` (rotation/retention/atomic
manifest), `openauto/src/autoapp/Projection/AurigaSession.cpp` (applied state),
`stream/web/app.js:9,42,57` (WS port and reconnect claim), `scripts/auriga.sh:15,31,124-127`.

## Functional behavior
- F1 (FR-STR-01) HTTP static server on 127.0.0.1:8080, `ThreadingHTTPServer`, daemon thread,
  request logging suppressed. Evidence: `stream/server.py:488-499`; `stream/auriga_stream.py:38`.
  Status: active.
- F2 (FR-STR-02) One JSON `hello` per connection with `{type,width,height,fps,codec,description}`,
  `description` = base64 avcC from the segment's SPS/PPS, `codec` = `avc1.<sps[1..3]>`.
  Evidence: `stream/server.py:181-212,436`. Status: active.
- F3 (FR-STR-03) Annex-B tail → one AVCC message per VCL access unit, header `>BQ` (type, ts_us),
  type 1 = key, 3 = delta. Evidence: `stream/lib/h264.py:15-41,118-178`;
  `stream/server.py:335-345,349-357`. Status: active.
- F4 (FR-STR-04) Startup video offset = last type-5 NAL within the last 8 MiB, else 0.
  Evidence: `stream/lib/h264.py:11,85-115`; `stream/server.py:298-300`. Status: active, tested
  (`tests/test_h264.py:195-214`).
- F5 (FR-STR-05) GOP cache (last keyframe + following frames, bound 2400) replayed to a joining
  viewer after `hello`. Evidence: `stream/lib/h264.py:181-217`; `stream/server.py:354-357,408-416,437`.
  Status: active. `GopBuffer.add`'s bool result is never read (L6).
- F6 (FR-STR-06) Audio tail from byte 44 of `audio-media.wav`, 4-byte aligned, 7680-byte chunks,
  type 2; guidance/system never streamed. Evidence: `stream/server.py:47-48,52,359-406`.
  Status: active (start position caveat B6).
- F7 (FR-STR-07 as implemented) A new `current` target drops the queue, sends `reset` then `hello`,
  clears the GOP, re-extracts SPS/PPS, restarts the content clock; both tails reopen at 0/44.
  Evidence: `stream/server.py:229-264` + `stream/lib/session.py:183-214`. Status: active.
  Requirement text/evidence are stale (D1, D2).
- F8 (FR-STR-08) Client `tap|down|move|up` → `"<cmd> <x> <y>\n"` to the FIFO via a fresh
  `O_WRONLY|O_NONBLOCK` fd per event; failure → `status` text message.
  Evidence: `stream/server.py:454-475`. Status: active (tested `tests/test_server.py:253-265`).
- F9 (FR-STR-14) Exactly one viewer: newest connection wins, previous closed with 4001.
  Evidence: `stream/server.py:54,418-435`; tested `tests/test_server.py:202-209`. Status: active.
- F10 (FR-STR-13 / NFR-05, HU side) In-place rotation at `SEGMENT_LIMIT = 4 GiB − 16 MiB`,
  `KEEP_SESSIONS = 5`, manifest segment count bumped on rotate; `current` is never pruned.
  Evidence: `patches/openauto-capture.patch:259-261,1717-1730,1520-1561`;
  applied at `openauto/src/autoapp/Projection/AurigaVideoOutput.cpp:150`,
  `AurigaSession.cpp:235`. Status: active (requirements say "not satisfied" — D3).
- F11 (NFR-02, stream half) Poll 8 ms, flush per access unit, socket decoupled through a bounded
  queue. Evidence: `stream/server.py:50,53,64-153,347,406`. Status: active.
- F12 (NFR-03, FR-RUN-06) Loopback-only binds, no auth, no host override flag.
  Evidence: `stream/server.py:496`; `stream/auriga_stream.py:45`. Status: active.
- F13 (FR-STR-09..12) Browser decode/input/reconnect behavior: in `stream/web/app.js`, not in this
  file set. Doc claims spot-checked true (`app.js:9,42,57`). Status: unclear from this aspect.
- F14 (content clock) `ts_us` = frame_index·1e6/fps and sample_index·1e6/48000, restarted per
  session by constructing a new `ContentClock`. Evidence: `stream/lib/clock.py:17-62`;
  `stream/server.py:242,353,402`. Status: active.

FR/NFR mapping result: 11 of 13 kept STR requirements map to live code (FR-STR-09..12 are the
browser client, outside this file set). 2 map in behavior but not in wording/evidence:
FR-STR-07 (mechanism changed from size-truncation to symlink+manifest), FR-STR-13 (implemented in
C++/patch, Python mirror unused). NFR-02, NFR-03 map; NFR-05 maps (contradicts its stated status).

## External facts and quirks
- X1 WebCodecs needs a secure context; `localhost`/`127.0.0.1` qualify, `ws://` from an HTTPS page
  does not. Consequence: plain localhost HTTP only. Source: vendor doc, restated
  `docs/Stream protocol.md:190-193`; `app.js:42`. Unverified by capture.
- X2 A configured avcC `description` makes browsers ignore in-band SPS/PPS. The rollover design
  assumes the opposite (doc:74). Source: unverified vendor behavior.
- X3 Rotation is an in-place truncate+reopen of the same file path; the only signal is the manifest
  segment count. `patches/openauto-capture.patch:1717-1730`; `stream/server.py:306-317`.
  Consequence: a lost manifest update silently stalls the tail (D5).
- X4 4 GiB WAV RIFF limit is unreachable now (rotation at 4 GiB−16 MiB). Source: code
  (`patches/openauto-capture.patch:259`).
- X5 `max_size=None` on the WS server: an unbounded text frame is accepted; loopback is the only
  boundary. `stream/auriga_stream.py:45`; documented `docs/Stream protocol.md:252-257`.
- X6 Video and audio have independent start positions (last IDR vs. audio offset) while both
  timestamps start at 0 → `ts_us` does not express the A/V offset. `stream/server.py:296-300,365-369`.
- X7 HTTP handler is `SimpleHTTPRequestHandler`: directory listing and any file under `stream/web`
  are served. `stream/server.py:488-494`.

## Doc and code inconsistencies
- D1 `requirements.md:67,74,76,79,83,87,93,96` cite `stream/auriga_stream.py` at lines up to 417;
  that file is a 51-line CLI (`stream/auriga_stream.py:14-51`). The implementation lives in
  `stream/server.py` and `stream/lib/*`. 19 stale line references in FR-STR-01..08, NFR-02/03.
- D2 `requirements.md:91-93` (FR-STR-07) says session truncation is detected by `size < offset`
  and the server "closes/reopens at 0"; code never infers from size (`stream/server.py:331`) —
  it uses the `current` symlink and manifest counts (`stream/lib/session.py:183-214`).
- D3 `requirements.md:244-246` (NFR-05) status "kept (target), not satisfied"; rotation and
  bounded retention are implemented and applied (`AurigaVideoOutput.cpp:150`,
  `AurigaSession.cpp:235`, `SEGMENT_LIMIT`/`KEEP_SESSIONS` at patch:259-261).
- D4 `docs/Stream protocol.md:50` "audio at startup: end of file (max(44, size))" — true only if
  `audio-media.wav` exists at the first poll; otherwise `stream/server.py:366-368` sets 44 and the
  entire file is streamed once it appears (B6).
- D5 `docs/Stream protocol.md:79-80` "truncated without a manifest update leaves the reader idle
  until the next poll" — it stays idle until the next *epoch* change, i.e. forever, with no log.
  Code: `stream/server.py:331-347`.
- D6 `docs/Stream protocol.md:26` "The tail loops never send" — `video_loop` pushes `hello`
  (`stream/server.py:319-320`) and both loops mutate the viewer queue; only socket writes are
  confined to `Viewer.run`.
- D7 `docs/Stream protocol.md:167-170` "the clock restarts at 0 ... so A/V stay aligned" then
  admits the offset. Two clocks restarted at the same instant over differently-positioned content
  cannot be aligned; `ts_us` is a per-stream counter, not a shared timeline (X6).
- D8 Doc inconsistency: `docs/Stream protocol.md:219` "one GOP (~60 s)" vs `:99` "2400 frames
  (~80 s)" vs `GOP_MAX_FRAMES = 2400` (`stream/lib/h264.py:12`).
- D9 Doc line refs: `docs/Stream protocol.md:16` cites `stream/server.py:495` for the bind; it is
  496. Streamer ranges are off by one (`:29` 348-356 vs code 349-357; `:47` 221-226 vs 222-227;
  `:73` 237-263 vs 238-264; `:87` 417-435 vs 418-435), while Viewer ranges (`:94-96`) are exact.
- D10 `stream/README.md:19` describes "auriga_stream.py (tail + WS)"; the tail and WS are in
  `stream/server.py` (doc:3 says so correctly). Stale duplicate summary.
- D11 `stream/auriga_stream.py:32` hardcodes `--fifo` default `/tmp/auriga-in` and ignores
  `AURIGA_INPUT_FIFO`, while `--capture-dir` honours `AURIGA_CAPTURE_DIR`
  (`stream/auriga_stream.py:23-26`). `AGENTS.md` documents `/tmp/auriga-in` (`$AURIGA_INPUT_FIFO`);
  `scripts/auriga.sh:125-126` passes both explicitly, so only direct CLI use diverges.
- D12 `docs/Stream protocol.md:143` "type 2 ... 7680 B max per message" is true, but a chunk can be
  shorter at read boundaries (any multiple of 4): `stream/server.py:398-404`.

## Assumptions to revalidate
- A1 `current` and `manifest.json` are published atomically (temp + rename / symlink swap).
  Baked in at `stream/lib/session.py:183-214`. Verified in `AurigaSession.cpp` (patch:180-190,
  1504-1516). If false, a poll can read a torn manifest and fall back to 1280x720/30.
- A2 Rotation is in-place truncation of the same path (X3), so the manifest count is the only
  rollover signal. If the head unit ever writes `video-1.h264`, the tail breaks silently.
- A3 The stream is one slice per VCL (CON-HU-01). Baked into `FrameAssembler`
  (`stream/lib/h264.py:118-154`): two slices produce two messages with different timestamps.
- A4 A session's SPS/PPS do not change between segments. Baked in at `stream/server.py:319`
  (refresh only when `description is None`). If false → B3.
- A5 WebCodecs ignores in-band parameter sets when `description` is set (X2). The rollover design
  (`docs/Stream protocol.md:74`) depends on it.
- A6 Manifest geometry equals the decoded AA geometry. Tests assert 1920x1080/60 support
  (`tests/test_session.py:148-155`) while CON-HU-01 fixes the captured stream at 1280x720/30;
  which one the head unit actually publishes at runtime is unverified.
- A7 Test suite requires Python ≥3.10 (`asyncio.Event()` in `Viewer.__init__`,
  `stream/server.py:76`); system 3.9 errors 6 tests, `.venv` 3.14 passes.
- A8 The FIFO always has a reader (`sleep 86400 > FIFO`). If not, every input event produces a
  `status` message; `ENXIO` is expected, not exceptional (`stream/server.py:462-475`).

## Bugs
- B1 [medium] Stale avcC after a segment rollover whose SPS/PPS changed. `stream/server.py:306-317`
  reopens the file but `refresh_codec` only runs when `description is None` (`:319`), and in-band
  SPS/PPS are ignored once `codec`+`description` are set (X2). Scenario: encoder reconfigures
  mid-session → every subsequent frame decodes with the old profile/geometry until a new session.
- B2 [medium] `refresh_codec` can raise `IndexError` on a truncated parameter set:
  `sps[1],sps[2],sps[3]` (`stream/server.py:192`) and `build_avcc` (`stream/lib/h264.py:70-77`).
  `split_nals` can hand back a 1–3 byte SPS from a partially flushed file. Scenario: capture file
  with `00 00 01 67 00 00 01 ...` → exception inside `adopt` → `session_loop` task dies
  (`stream/auriga_stream.py:41`, task reference dropped, no done-callback) → sessions stop being
  followed with no log line.
- B3 [low] Video/audio can be queued for a new viewer before its `hello`. `stream/server.py:423`
  installs `self.viewer = viewer`, then `await previous.ws.close(...)` (`:432`) yields; the tail
  loops push into the new queue, `hello` only lands at `:436`. Audio reorder is harmless (client
  schedules by ts); a keyframe in that window reaches the page unconfigured (decode error → the
  page asks for a keyframe, so it recovers).
- B4 [low] Lost wakeup in `Viewer.run`: `stream/server.py:144-152`. A push between the drain loop
  exiting and `self.ready.clear()` is not observed; the message waits for the next push. Self-heals
  at 8 ms cadence, but the final message before quiescence can sit until disconnect.
- B5 [low] `Viewer(maxsize=0)` → `push` → `_make_room` → `self.messages.popleft()` on an empty
  deque → `IndexError` (`stream/server.py:102-103,138`). Not reachable with the production default.
- B6 [low] Audio start offset is wrong when the WAV appears after the first poll:
  `stream/server.py:365-369` sets 44 on `OSError`, then `open_when_ready` seeks to 44 (`:369`)
  instead of EOF. Scenario: server starts before the AA audio channel opens → the whole file is
  replayed from the head, so audio runs seconds behind video (doc:50 claims EOF).
- B7 [low] Unbounded synchronous reads on the event loop: `stream/server.py:332,391` read
  `size - offset` with no cap; `find_last_idr` reads 8 MiB (`stream/lib/h264.py:99-101`). Scenario:
  a stalled tail (B1/D5) then a burst → one multi-hundred-MB read blocks sends and audio pacing.

## Dead code, leftovers, stale comments
- L1 `stream/lib/session.py:30-36` `mint_session_id`, `session_name` — no production caller;
  session ids are minted by the head unit (`AurigaSession.cpp:71-150`).
- L2 `stream/lib/session.py:47-60` `plan_retention` — no caller; the real retention is
  `AurigaSessionManager::prune`. Diverges: C++ maps `keep=0` to 1 and skips `current`
  (patch:1541-1543), Python deletes everything except `current` (session.py:57-59).
- L3 `stream/lib/session.py:20` `SESSION_TIME_FORMAT` — only used by L1.
- L4 `stream/lib/h264.py:166-170` `FrameAssembler.reset` — test-only (`tests/test_h264.py:150-156`);
  `video_loop` builds a new assembler instead (`stream/server.py:316`).
- L5 `stream/lib/clock.py:44-47` `ContentClock.reset` — only called from `__init__` (`:42`);
  session change constructs a new clock (`stream/server.py:242`).
- L6 `stream/lib/h264.py:196-207` `GopBuffer.add` returns a bool nobody reads
  (`stream/server.py:355`).
- L7 `stream/server.py:77,134` `Viewer.dropped` counted, never reported outside tests.
- L8 `stream/server.py:138` `_make_room`'s final `popleft()` is unreachable for `maxsize >= 1`
  (every message kind is json/audio/video) and raises for `maxsize == 0` (B5).
- L9 `stream/server.py:20-45` duplicated `if __package__` import block — the same 13-name import
  list twice.
- L10 `stream/server.py:478-479` bare `except Exception: pass` hides handler defects.
- L11 `stream/server.py:328-330` comment describes a rollover guard that is only implicit
  (`size > offset`); no explicit "waiting for epoch" state exists.
- L12 `docs/Stream protocol.md:228-234` "Audio timestamps cluster and overlap" — historical cause
  ("before the content clock"); no such path remains.
- L13 `stream/server.py:166-173` two fallback constants (`DEFAULT_WIDTH/HEIGHT` from session.py and
  `DEFAULT_FPS` in server.py) for the same manifest defaults; `DEFAULT_FPS` is also defined in
  `stream/lib/session.py:26` and `stream/lib/clock.py:10`.
- L14 `stream/server.py:419` `getattr(ws, "remote_address", "?")` — the fallback exists only for
  the test fake; production always has the attribute.

## Improvement areas
- I1 Merge `video_loop` and `audio_loop` into one tail parameterised by
  (path, offset policy, decoder); ~110 near-identical lines (`stream/server.py:290-406`).
- I2 Replace 16 `print()` calls (14 in `stream/server.py`, 2 in `auriga_stream.py`) with `logging`;
  FIFO errors, queue drops and epoch stalls are currently invisible in `logs/stream-mac-*.log`.
- I3 Latency cap: `VIEWER_QUEUE = 240` (`stream/server.py:53`) allows ~8 s of backlog; content
  timestamps mean a viewer that lags never catches up. Drop to the newest keyframe once depth
  exceeds ~30 messages instead of 240.
- I4 Cap per-poll read size and move `find_last_idr` to a thread (`asyncio.to_thread`), so loop
  scheduling does not depend on capture-file bursts (B7).
- I5 `try/finally: f.close()` in both tail loops (test run emits `ResourceWarning: unclosed file`),
  and hold task references plus `add_done_callback` logging in `stream/auriga_stream.py:41-43` so a
  dead loop is loud (B2).
- I6 Coverage gaps: nothing tests session change (`reset`+`hello` order), rollover reopen, the
  audio loop, `open_when_ready`, `_make_room`'s json fallback, or `serve_http`.
  `tests/test_server.py:92-265` covers Viewer state, `handle`, `flush_frame`, `hello` only.
- I7 Two independent desync mechanisms exist (server `Viewer.synced`, browser `needKey`); the
  browser also asks for `keyframe` on gaps (`app.js:161-196`). Pick one owner.
- I8 Restrict the HTTP handler to GET of the three known files; `SimpleHTTPRequestHandler` serves
  directory listings (X7).
- I9 Emit an explicit `status` (or log line) when a tail is idle because the file is shorter than
  the offset (D5); right now the failure is silent.

## Interfaces
- Exposes (imported by `tests/`; consumable by any local consumer over the wire):
  - `stream.server`: `Streamer` (`handle`, `session_loop`, `video_loop`, `audio_loop`, `adopt`,
    `flush_frame`, `replay`, `hello`, `send_hello`, `send_json`, `refresh_codec`, `video_path`,
    `audio_path`), `Viewer` (`push_json/push_audio/push_video/push/clear_video/reset_stream/stop/run`),
    `serve_http`, constants `AUDIO_HEADER`, `AUDIO_CHUNK`, `DEFAULT_FPS`, `POLL_INTERVAL`,
    `SESSION_POLL_INTERVAL`, `TRAILED_STREAMS`, `VIEWER_QUEUE`, `REPLACED_CODE`, `stream_path`.
  - `stream.lib.h264`: `split_nals`, `sps_pps_from_bytes`, `extract_sps_pps`, `build_avcc`,
    `avcc_sample`, `find_last_idr`, `FrameAssembler`, `GopBuffer`, `LAST_IDR_WINDOW`,
    `GOP_MAX_FRAMES`.
  - `stream.lib.clock`: `ContentClock`, `video_timestamp`, `audio_timestamp`, `MICROS`.
  - `stream.lib.session`: `SessionFollower`, `SessionEvent`, `Manifest`, `parse_manifest`,
    `read_current`, `read_manifest`, `plan_retention`, `mint_session_id`, `session_name`,
    `is_session_name`, `session_id_from_name`, `DEFAULT_WIDTH/HEIGHT/FPS`, `STREAMS`,
    `SESSION_PREFIX`, `SESSION_TIME_FORMAT`, `CURRENT_NAME`, `MANIFEST_NAME`.
  - CLI: `auriga_stream.py --capture-dir --fifo --http-port --ws-port --web`.
- Consumes: `<capture-dir>/current` symlink, `<capture-dir>/session-*/manifest.json`
  (`{session,width,height,fps,video,audio-media,audio-guidance,audio-system}`),
  `video.h264` (Annex-B, SPS/PPS at each segment head), `audio-media.wav` (44-byte header),
  the input FIFO (written by `autoapp`'s stdin reader), and the `websockets` package.
- Threading: one asyncio loop runs `session_loop`, `video_loop`, `audio_loop`, the WS server and one
  `Viewer.run` send task per connection; `serve_http` runs `ThreadingHTTPServer.serve_forever` on a
  daemon thread (`stream/server.py:496-498`). `Streamer.lock` (asyncio) guards GOP bookkeeping only
  and is never held across a socket send. File reads/seeks and `os.path.getsize` run synchronously
  on the loop thread (B7).

## Open questions for the user
- Q1 Keep `--ws-port` (page hardcodes 8081) or delete the flag?
- Q2 Retention lives in C++ (`prune`); delete `plan_retention`/`mint_session_id` from
  `stream/lib/session.py` or make one side authoritative?
- Q3 Can the AA encoder change SPS/profile mid-session (decides whether B1 is real)?
- Q4 Is the one-slice-per-VCL assumption guaranteed by config, or must `FrameAssembler` become
  slice-aware (A3)?
- Q5 Is `stream/README.md` still maintained, or should it yield to `docs/Stream protocol.md` (D10)?

## Result
14 functional behaviors mapped (11 kept STR + NFR-02/03/05); 2 requirement entries stale
(FR-STR-07 mechanism, FR-STR-13 evidence), 1 requirement status contradicted (NFR-05).
19 stale line references in `requirements.md` point at a 51-line file. 12 doc/code inconsistencies,
8 assumptions, 7 bugs (2 medium: stale avcC at rollover, unguarded `refresh_codec` killing
`session_loop`), 14 leftovers, 9 improvement areas. 94/94 tests pass; session change, rollover
reopen and the audio tail are untested.
