# Audit: browser client (final, against requirements.md)

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| stream/web/app.js | 355 | yes |
| stream/web/index.html | 38 | yes |
| docs/Stream protocol.md | 268 | yes |
| docs/Android Auto head unit.md | 404 | yes |

Total assigned: 1065 lines. Cross-checked (read, not assigned): `stream/server.py` (499), `stream/auriga_stream.py` (51), `tests/test_server.py` (269), `captures-mac/` listing.

FR map for the browser part of STR: FR-STR-09 ✓ (F1–F3), FR-STR-10 ✓ (F4), FR-STR-11 ✓ (F5), FR-STR-12 ✓ with defect B4 (F6), FR-STR-14 ✓ (F7). All five have code. No kept browser FR is unimplemented. Four active client behaviors have no FR (F8–F11).

## Functional behavior
- F1: Decode H.264 with WebCodecs `VideoDecoder` configured from `codec` + base64 avcC `description`, `optimizeForLatency`, coded size from `hello`. Evidence: `stream/web/app.js:115-148`. Status: active. Maps to FR-STR-09.
- F2: Draw every decoded `VideoFrame` to the canvas and close it; the canvas is resized from `hello` and from `frame.displayWidth/Height` when they differ. Evidence: `stream/web/app.js:100-106,150-159`; default 1280x720 in `stream/web/index.html:34`. Status: active. Maps to FR-STR-09, but the FR's literal "1280x720 canvas" is only the default (D4).
- F3: Play PCM type-2 payloads as s16le stereo via WebAudio, scheduled at `anchor + (ts - firstTs)` from the message timestamp. Evidence: `stream/web/app.js:231-268`. Status: active. Maps to FR-STR-09.
- F4: Audio muted at load; the first unmute click constructs the `AudioContext` (48 kHz, `latencyHint:"interactive"`) and resumes it; mute suspends it. Evidence: `stream/web/app.js:21,219-229,334-353`. Status: active. Maps to FR-STR-10.
- F5: Pointer gesture → `tap` when travel ≤8 px, else `down` at the press point, `move` throttled to 50 ms, `up` at release; `pointercancel` sends `up` at the last move point. Evidence: `stream/web/app.js:285-332`. Status: active. Maps to FR-STR-11.
- F6: Reconnect 2 s after a close (unless close code `4001`), reset decoder/GOP/gap state, reconfigure on `hello`, redraw after `reset`. Evidence: `stream/web/app.js:38-98`. Status: active. Maps to FR-STR-12; error-only reconnect is missing (B4).
- F7: Single viewer client side: only one socket per page (`connect` closes the previous), `4001` latches `replaced` and stops retrying. Evidence: `stream/web/app.js:10,51-55,71-80`; server side `stream/server.py:424-436`. Status: active. Maps to FR-STR-14. The latch is permanent (B5).
- F8: Resync: drop deltas until a keyframe, request `{"type":"keyframe"}` on a >250 ms content gap, on decoder error, and after a decode-queue overflow decision. Evidence: `stream/web/app.js:163-196`; server replay `stream/server.py:448-452`. Status: active, no FR.
- F9: Show server `status.text` in the status bar. Evidence: `stream/web/app.js:95-97`; server `stream/server.py:474`. Status: active, no FR.
- F10: Per-second stats line `frames · dropped · audio on|off`. Evidence: `stream/web/app.js:211-216`. Status: active, no FR.
- F11: Canvas geometry is overridden by the decoded frame, not just `hello`. Evidence: `stream/web/app.js:151-155`. Status: active, no FR.

## External facts and quirks
- X1: WebCodecs needs a secure context; the page hardcodes `ws://${location.hostname}:8081`, so an HTTPS front breaks both decode and socket. Code: `stream/web/app.js:42`; documented `docs/Stream protocol.md:190-193`. Source: vendor doc, verified (CON-STR-01).
- X2: `AudioContext` must be created inside a user gesture; the code only constructs it under `setMuted(false)` from the click handler, so muted startup never hits the autoplay block. Code: `stream/web/app.js:219-229,352`. Source: vendor doc + code.
- X3: Reconnect uses `setTimeout(connect, 2000)`; Chromium throttles timers in hidden tabs to ≥1 min, so a backgrounded page can take a minute to reattach after a server restart. Code: `stream/web/app.js:57`. Source: vendor doc, unverified locally.
- X4: One `AudioBuffer` + `BufferSource` per 40 ms chunk (~25/s) on the main thread; allocation and GC pressure scales with playback. Code: `stream/web/app.js:255-267`. Source: code.
- X5: `location.hostname` is empty for `file://`, guarded to `"localhost"`. Code: `stream/web/app.js:41`. Source: code.
- X6: macOS can move an `AudioContext` to `"interrupted"`; the code re-`resume()`s per chunk and still drops chunks while suspended. Code: `stream/web/app.js:233`. Source: code.

## Doc and code inconsistencies
- D1: `docs/Stream protocol.md:180` says reconnect "every 2 s after close or error"; `stream/web/app.js:59` only sets status on `onerror`, reconnect is scheduled solely from `onclose` at `app.js:57`.
- D2: `docs/Stream protocol.md:108-110` says a decode-queue overflow "drops deltas without asking, which the next gap then detects"; in `stream/web/app.js:192-195` the overflow sets `needKey`, and `app.js:185-186` returns before the gap check at `app.js:187`, so no gap is ever detected and no keyframe is requested.
- D3: `docs/Stream protocol.md:182` says `aspect-ratio` keeps the picture undistorted; `stream/web/index.html:22` sets `height:100%` with `max-width:100%`, which clamps width without recomputing height, so the inline `aspectRatio` (`app.js:105`) cannot prevent vertical stretching in a window narrower than the stage height × 16:9.
- D4: `requirements.md:97-100` (FR-STR-09) says the client "draws to a 1280x720 canvas"; the code sizes the canvas from `hello`/manifest and then from the decoded frame (`app.js:100-106,150-155`); 1280x720 exists only as `index.html:34` default and as the server fallback.
- D5: `docs/Android Auto head unit.md:400` verifies with `captures-mac/video.h264`; the current contract is `captures-mac/current/video.h264` (`:116-126`). The flat file that exists is legacy (L4).
- D6: `docs/Stream protocol.md:16` cites `stream/server.py:495` for the loopback HTTP bind; the bind is `stream/server.py:496` (`serve_http` starts at 488).
- D7: `docs/Stream protocol.md:188` says stats shows "audio state"; `stream/web/app.js:214-215` prints `on` whenever an `AudioContext` object exists, including muted/suspended.

## Assumptions to revalidate
- A1: Brave on this Mac can create an H.264 `VideoDecoder` and decode the AA Baseline stream. Baked in at `stream/web/app.js:128-143`, no fallback path (no MSE, no server transcode). If false, the page shows only a status line and no picture.
- A2: A `hello` always follows a `keyframe` request and a first SPS/PPS appearance. `requestKeyframe` tears the decoder down and waits (`app.js:163-171`); the server does send both (`server.py:319-320,451`), but nothing on the client retries if that hello is lost, and `keyframePending` then blocks further requests until a new socket.
- A3: Manifest geometry = decoded frame size = AA input coordinate space. The gesture code scales to `canvas.width/height` (`app.js:270-278`), the head unit maps FIFO coordinates in `configuredVideoGeometry()` (`docs/Android Auto head unit.md:149-154,224`). Divergence puts taps in the wrong place with no client-side check.
- A4: The server's audio content clock advances at real time, so the fixed `currentTime + 0.15` anchor needs no drift correction (`app.js:242,251`). Each re-anchor adds a 0.15 s audio shift; nothing aligns audio to video.
- A5: `captures-mac/current` exists at runtime. In the repo it does not: `captures-mac/` holds flat legacy `video.h264` (5.2 MB), 44-byte `audio-*.wav`, empty `input.jsonl` (L4). A `start` now would show "connected, waiting for stream…" until a new session appears.
- A6: `4001` always means another browser tab. `app.js:51-55` latches `replaced` forever on that code, so any other cause of a 4001 close leaves the page permanently dead.

## Bugs
- B1 [medium]: Decode-queue overflow disables resync instead of triggering it. `stream/web/app.js:192-195` sets `needKey` and returns; the gap check at `app.js:187` is unreachable while `needKey` is true (`app.js:185-186`), so no `keyframe` request is sent and the page waits for the encoder IDR (~60 s). Scenario: late client / slow decode → `decodeQueueSize > 2400` once → picture freezes until the next IDR, even though the server can replay its GOP on demand.
- B2 [low]: `tap` is sent at the release point, not the press point. `stream/web/app.js:313-321`: scenario press at (100,100), release at (107,107) → tap at (107,107), up to 8 px off the user's target; the doc row `Stream protocol.md:186` implies the press point.
- B3 [low]: No button/primary filtering on pointer events. `stream/web/app.js:285-292`: right-click or a secondary finger starts `dragging`, so a context-click emits a `tap` (and `pointercancel`/`pointerup` emit `up`) into AA.
- B4 [low]: `onerror` never schedules a reconnect. `stream/web/app.js:59`: FR-STR-12 and `Stream protocol.md:180` promise close-or-error; only the close path retries (`app.js:57`). A browser that fires `error` without `close` leaves the page dead.
- B5 [low]: `replaced` is a one-way latch. `stream/web/app.js:51-55`: after another tab takes the stream and closes, the first tab stays "another tab took over this stream" with no retry and no reload prompt; recovery requires the user to reload.
- B6 [low]: Stats misreport audio state. `stream/web/app.js:214-215`: muted playback still prints `audio on`, because the test is `audioCtx` presence, not `muted`/`state`.
- B7 [low]: Canvas distortion in narrow windows. `stream/web/index.html:22` + `stream/web/app.js:105`: window narrower than stage height × 16:9 → picture stretched vertically although the doc says it is not (D3).
- B8 [low]: Unmute replays pre-mute scheduled buffers. `stream/web/app.js:340-348`: `suspend()` freezes the clock but leaves queued sources; on `resume()` they fire together, so unmute after muting during playback plays a short overlapping cluster.

## Dead code, leftovers, stale comments
- L1: `stream/web/app.js:101-102`, `canvas.width || 1280` / `canvas.height || 720` fallbacks are unreachable; a canvas always has numeric width/height.
- L2: `stream/web/app.js:295`, the `!dragStart` guard cannot be true while `dragging` is true (`dragStart` is set at `app.js:287` and cleared only with `dragging`).
- L3: `stream/web/app.js:323`, `lastPoint = point` in `pointerup` is written and cleared two lines later, never read.
- L4: `captures-mac/` contains the pre-per-session flat layout (`video.h264`, `audio-{media,guidance,system}.wav`, `input.jsonl`, no `current`), dated after the per-session rework; it is what `docs/Android Auto head unit.md:400` still points at.
- L5: `stream/web/app.js:59`, the `onerror` handler only rewrites the status text; no state changes (see B4).
- L6: `docs/Stream protocol.md:36,245-250` still documents `--ws-port` as an unusable flag rather than removing the flag or deriving the port; `stream/auriga_stream.py:34` keeps the option.

## Improvement areas
- I1: Resync rule: request a keyframe immediately on queue overflow and cap the pending-chunk queue by time (e.g. 120 chunks ≈ 4 s), not 2400 (`app.js:12,192-195`). Mechanism: today the cap is 80 s of video, so the "protection" turns into a long freeze with no resync.
- I2: Audio: replace per-chunk `AudioBuffer` construction with an `AudioWorklet`/ring buffer and a bounded jitter buffer (`app.js:255-267`). Removes ~25 allocations/s, GC hiccups and the 0.15 s jump per re-anchor.
- I3: Single geometry source: send the AA input geometry explicitly (or read it from the manifest) and size both the canvas and the pointer mapping from it, instead of inferring from the decoded frame (`app.js:150-155,270-278`).
- I4: `touch-action: none; user-select: none` on `#screen`, and `event.button === 0 && event.isPrimary` filtering before starting a drag (`index.html:22`, `app.js:285`). Prevents scroll/pinch `pointercancel` storms and stray right-click taps.
- I5: Request a keyframe and re-anchor audio on `visibilitychange` → visible and on `pageshow`. Mechanism: background throttling leaves the WS backlog and the decoder stale; the page currently relies on a 250 ms content gap to notice.
- I6: Derive the WS port instead of hardcoding it: serve a small `config.json` from the HTTP server, or use `location.port`/same-origin proxying. Removes the `--ws-port` footgun and one documented quirk.
- I7: The client has zero automated coverage; `tests/` covers the server only, and `app.js` is untestable as written because DOM lookups and `connect()` run at module load. Split pure functions (`handleBinary`, `playAudio` scheduling math, gesture state) behind an injected clock/socket.
- I8: Count queue-cap drops in `droppedFrames` and report `muted`/`suspended` in stats (`app.js:188,214-215`); today the visible counter hides the failure mode of B1.

## Interfaces
- Exposes: `http://127.0.0.1:8080` static `stream/web/{index.html,app.js}` (no other asset, no API); WS client traffic `{type:"tap"|"down"|"move"|"up",x,y}` and `{type:"keyframe"}` on `ws://<host>:8081`. No exported JS symbols, no globals beyond top-level `const`/`let` in one classic script.
- Consumes: server text `hello {type,width,height,fps,codec,description}`, `reset`, `status {text}`; binary `u8 type | u64 BE ts_us | payload` with types 1/3 = AVCC video, 2 = PCM s16le 48 kHz stereo (`stream/web/app.js:173-209`). Depends on the server re-sending `hello` on keyframe request and on first SPS/PPS (`stream/server.py:319-320,451`), and on close code 4001 for the viewer rule (`stream/server.py:432`).
- Threading: one JS main thread. `WebSocket.onmessage` runs `handleBinary` synchronously; `VideoDecoder` output/error callbacks are separate agent tasks calling `draw`; WebAudio runs on its own real-time thread with scheduling done on the main thread; pointer events are dispatched on the main thread and the 50 ms move throttle is timestamp-based, not a timer. The 2 s reconnect is the only timer (`app.js:57`).

## Open questions for the user
- Q1: Should the canvas keep following the stream geometry (current code, FR-STR-09 says 1280x720), or be fixed at 1280x720 with letterboxing?
- Q2: Is permanent death after a `4001` takeover (B5) acceptable, or should the page keep a "reconnect" button so it can reclaim the stream?
- Q3: Should unmute also request a keyframe and re-anchor audio, accepting a one-frame stall for A/V alignment?
- Q4: Is `captures-mac/` allowed to be wiped as part of the rearchitecture (L4/A5), or does the flat legacy capture still have value?
