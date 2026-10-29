# Audit: seams

Scope: the contracts between aspects — threading/locking, buffer ownership, data formats, duplicated logic, hidden shared state. Input: the `## Interfaces` sections of all seven sibling reports, then the boundary files they name.

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| .rearch/audit/openauto-integration.md (Interfaces) | 141 | yes (whole file) |
| .rearch/audit/stream.md (Interfaces) | 121 | yes |
| .rearch/audit/runtime-orchestration.md (Interfaces) | 116 | yes |
| .rearch/audit/dongle-hardware.md (Interfaces) | 132 | yes |
| .rearch/audit/minimal-capture.md (Interfaces) | 131 | yes |
| .rearch/audit/phone-app-design.md (Interfaces) | 83 | yes |
| .rearch/audit/build-and-tooling.md (Interfaces) | 114 | yes |
| openauto/src/autoapp/Projection/AurigaVideoOutput.cpp | 85 | yes |
| openauto/src/autoapp/Projection/AurigaAudioOutput.cpp | 182 | yes |
| openauto/src/autoapp/Projection/AurigaInputDevice.cpp | 236 | yes |
| openauto/src/autoapp/Service/MediaSink/VideoMediaSinkService.cpp | 249 | yes |
| openauto/src/autoapp/Service/MediaSink/AudioMediaSinkService.cpp | 232 | yes |
| openauto/src/autoapp/Service/ServiceFactory.cpp | 270 | yes |
| openauto/src/autoapp/App.cpp | 272 | yes |
| openauto/src/autoapp/autoapp.cpp | 314 | yes |
| openauto/include/f1x/openauto/autoapp/Projection/AurigaVideoOutput.hpp | 47 | yes |
| openauto/include/f1x/openauto/autoapp/Projection/AurigaAudioOutput.hpp | 60 | yes |
| openauto/include/f1x/openauto/autoapp/Projection/AurigaInputDevice.hpp | 62 | yes |
| stream/auriga_stream.py | 423 | yes |
| stream/web/app.js | 258 | yes |
| scripts/mac-headunit-start.sh | 91 | yes |
| scripts/mac-headunit-stop.sh | 24 | yes |
| openauto-config/run-mac.sh | 36 | yes |
| openauto-config/openauto.ini | 29 | yes |
| patches/openauto-capture.patch | 1101 | yes (3 chunks) |
| patches/openauto-auriga-usb-filter.patch | 42 | yes |
| patches/aasdk-usb-filter.patch | 101 | yes |

Boundary total 4114 lines. Verification reads outside the list (~600 lines): `AndroidAutoEntity.cpp`, `AndroidAutoEntityFactory.cpp`, `InputSourceService.cpp`, `VideoService.cpp`, `MediaAudioService.cpp`, `Pinger.cpp`, `patches/openauto-macos.patch`, `aasdk-upstream/src/USB/USBHub.cpp`, `aasdk-upstream/src/Channel/MediaSink/{Video,Audio}/*.cpp`, `aap_protobuf/.../InputReport.proto`, `stream/web/index.html`, `stream/README.md`, `AGENTS.md:104-135`, byte inspection of `captures-mac/video.h264`, `captures-mac/audio-media.wav`, `logs/stream-mac-*.log`.

## Functional behavior
- F1: The only channel between the head-unit process and the streamer is the capture directory: five files, appended by the sinks, tailed by size polling. No socket, no shared memory, no acknowledgement in either direction. Evidence: `ServiceFactory.cpp:86-89,166-167,227-229`, `auriga_stream.py:188-191,212-244,303-328`. Status: active.
- F2: Every AA entity builds a fresh service list, so all sinks and the input device are new objects per session; "new session truncates" is a side effect of `open()` with `std::ios::trunc`, not an explicit session event. Evidence: `AndroidAutoEntityFactory.cpp:65` (`serviceFactory_.create`), `ServiceFactory.cpp:108-128`, `AurigaVideoOutput.cpp:39`, `AurigaAudioOutput.cpp:70`, `AurigaInputDevice.cpp:50`. Status: active.
- F3: The system contains a runtime loop: AA media out → file → stream server → browser → FIFO → autoapp stdin → AA input channel. Evidence: `VideoMediaSinkService.cpp:177`, `auriga_stream.py:373-378`, `run-mac.sh:36`, `AurigaInputDevice.cpp:122-154,200-214`, `InputSourceService.cpp:180-202`. Status: active.
- F4: The input device lifetime is gated on the phone's `KeyBindingRequest`, so `input.jsonl` truncates at a different instant than `video.h264`/`audio-*.wav` (channel open). Evidence: `InputSourceService.cpp:121-123`, `AurigaInputDevice.cpp:44-50` vs `AurigaVideoOutput.cpp:39`, `AurigaAudioOutput.cpp:70`. Status: active.
- F5: File I/O is inside the AA flow-control path: `max_unacked=1`, and the ACK is sent after `write()` returns, so a slow disk stalls the phone's video/audio send. Evidence: `VideoMediaSinkService.cpp:117,177-187`, `AudioMediaSinkService.cpp:174,209-218`. Status: active.
- F6: Codec config and media share one callback path: `onMediaIndication` (MEDIA_MESSAGE_CODEC_CONFIG) is forwarded into `onMediaWithTimestampIndication`, so the config blob is written into the media file. Evidence: `aasdk-upstream/src/Channel/MediaSink/Video/VideoMediaSinkService.cpp:121-122`, `VideoMediaSinkService.cpp:190-193`, `AudioMediaSinkService.cpp:222-226`; measured head of `captures-mac/video.h264`: NAL 7 at 0, NAL 8 at 21, NAL 5 at 29, first slice at 3645. Status: active.
- F7: The streamer signals a session change on video truncation only: `{"type":"reset"}` then `hello`. Audio truncation resets its own offset silently. Evidence: `auriga_stream.py:218-238` vs `316-324`; `logs/stream-mac-20261029-074101.log:13-16` (two audio resets, two video resets). Status: active.
- F8: On start, the streamer replays from the last IDR of the *previous* run's file before any new data exists: three consecutive starts read `video_offset=19706264`. Evidence: `auriga_stream.py:135-136`, `logs/stream-mac-20261029-073946.log:2`, `-074029.log:2`, `-074101.log:2`. Status: active.

## External facts and quirks
- X1: `video.h264` is Annex-B with the codec-config SPS/PPS written by the same `write()` path as frames; measured layout `SPS@0, PPS@21, IDR@29, slice@3645`. Consequence: the stream's NAL splitter happens to tolerate the config write because types 7/8 go to `pending` and are prepended to the next VCL (`auriga_stream.py:251-267`). Source: measurement + code.
- X2: "Capture mode" has two definitions: `App.cpp:32` (`getenv != nullptr`) and `ServiceFactory.cpp:67` (`!= nullptr && *value != '\0'`), plus a cached static in the second. They disagree for `AURIGA_CAPTURE_DIR=""`. Source: code.
- X3: The head unit advertises a 1000 ms ping interval, 3000 ms timeout, 5 tracked pings (`AndroidAutoEntity.cpp:187-191`) but pings every 5000 ms with one outstanding request and gives up after 5 unanswered (`AndroidAutoEntityFactory.cpp:65`, `Pinger.cpp:22-30,42-52`). Source: code.
- X4: The sink's `strand_` is the same object handed to the aasdk channel (`VideoService.cpp:28-33`, `MediaAudioService.cpp:26-33`), so channel callbacks, ACK sends and sink writes all serialize on one strand; the sinks' `std::mutex` (`AurigaVideoOutput.cpp:58`, `AurigaAudioOutput.cpp:90`) guards against nothing except `stop()` re-entry from the same strand. Source: code.
- X5: `AurigaVideoOutput::write` flushes every access unit (`AurigaVideoOutput.cpp:67`); `AurigaAudioOutput::write` never flushes and only forces a flush through `seekp(0)` in the 1 s header rewrite (`AurigaAudioOutput.cpp:97-107,145-166`). The streamer's audio tail therefore lags by one stream buffer plus up to 1 s. Source: code.
- X6: WAV sizes are 32-bit; `audio-media.wav` is at 405,577,772 B and `video.h264` at 390,431,049 B in the current run, so the media WAV wraps at ~6.2 h and the 4 GiB RIFF fields become wrong. Evidence: `ls -l captures-mac/`, `AurigaAudioOutput.cpp:150,163`. Source: measurement + code.
- X7: The streamer's audio timestamps are read-time, not content time; a batch of PCM read in one poll gets near-identical timestamps, and `app.js` schedules by that timestamp. Evidence: `auriga_stream.py:334-339`, `app.js:154,171-174`. Source: code.
- X8: `find_last_idr` only searches the last 8 MiB; if the file already has >8 MiB since the last IDR the streamer falls back to offset 0. Observed as `video_offset=0, sps=None` on an empty file (`logs/stream-mac-20261028-182229.log:2`), which produces `hello` with `description: null` and clients that refuse to configure (`app.js:71-74`). Source: code + log.
- X9: The FIFO write path needs a live reader: `run-mac.sh:26` parks `sleep 86400 > "$FIFO"` as writer; after 24 h it expires, `autoapp` stdin hits EOF and the reader loop exits (`AurigaInputDevice.cpp:138-142`). Source: code.
- X10: `/tmp/entityexit` is a file-based side channel between the video sink and the Qt UI: written at `VideoMediaSinkService.cpp:220-227`, consumed at `MainWindow.cpp:1754-1759` (offscreen GUI in capture mode). Source: code.

## Doc and code inconsistencies
- D1: `AGENTS.md:115` and `stream/README.md:78` say PCM arrives in "20 ms chunks"; `AUDIO_CHUNK = 7680` is 40 ms at 48 kHz/2 ch/16 bit and the code sends `chunk[i:i+7680]`, i.e. whatever was read. `auriga_stream.py:26,334-339`.
- D2: `AGENTS.md:116` and `stream/README.md:79` say the server sends text `reset`; the wire message is `{"type":"reset"}`. `auriga_stream.py:222`. A consumer following the doc breaks.
- D3: `stream/README.md:69` "the stream starts at the most recent H.264 IDR and then follows live" holds for video only; audio starts at the current EOF (`audio_offset = max(44, size)`), so a fresh client gets video with no audio. `auriga_stream.py:136-140`, `logs/stream-mac-20261029-074101.log:2` (`audio_offset=35201068`).
- D4: `AGENTS.md:107-108` says a new AA session truncates the files "and the server sends a `reset` message"; the code sends no message for audio truncation, and `input.jsonl` truncation is never observed by the streamer at all. `auriga_stream.py:316-324`, `AurigaInputDevice.cpp:50`.
- D5: `AGENTS.md:122-123` offers the capture files as an equivalent offline artifact; `audio-media.wav` in a killed run has a header that lags the file (measured Δ ~279 KB in build report X5), so the WAV is not equivalent without a repair step. `AurigaAudioOutput.cpp:168-177`.
- D6: `AGENTS.md:104-105` says "the most recent H.264 IDR and the following deltas, so a late client can start decoding immediately"; `app.js:109` drops deltas once the decode queue exceeds 200, so a mid-GOP join decodes a broken picture. `auriga_stream.py:347-356`.
- D7: `AGENTS.md:112` and `stream/README.md:76` give the wire format as `type:u8 | timestamp_us:u64 BE | payload`; the header is actually `struct.pack(">BQ", ...)` = 9 bytes, and `app.js:101` requires `byteLength >= 9`, consistent — but `RUNBOOK.md:239` documents the same field without byte order. `auriga_stream.py:289,338`.
- D8: `stream/README.md:1-6` still frames the Pi as the head unit and the WebSocket client as a remote UI; the code and `mac-headunit-start.sh:9,58-62` treat Mac-local as the primary deployment. No protocol difference exists between modes.

## Assumptions to revalidate
- A1: AA delivers whole Annex-B access units, one per `write()`, and `MEDIA_MESSAGE_CODEC_CONFIG` is Annex-B too. Baked into the sink (`AurigaVideoOutput.cpp:65-67`) and the splitter (`auriga_stream.py:32-55`). If a partial AU ever arrives, `video.h264` has no frame boundary marker and the stream emits a corrupt frame.
- A2: The WAV header is exactly 44 bytes and contains only `fmt `/`data`. Baked into `AUDIO_HEADER = 44` (`auriga_stream.py:25`) and the initial audio offset `:138`. Any extra chunk shifts all PCM by N bytes; playback becomes noise with no error.
- A3: One VCL NAL per frame. Baked into `auriga_stream.py:246-282` (each VCL NAL flushes a frame). Multi-slice frames would be sent as separate chunks and never reassembled.
- A4: File size only grows within a session and shrinks only on truncation. Baked into `auriga_stream.py:218,240,316,326`. Any other writer (a second server, a copy, `truncate`) is misread as a session change or a stall.
- A5: One writer per capture file and one reader of stdin. Nothing enforces it: `ServiceFactory.cpp:86-89` derives paths from `captureDir()`, and `AurigaInputDevice` reads the process-wide stdin (`AurigaInputDevice.cpp:127`) with no ownership check.
- A6: Coordinate space is 1280x720 in four places that must agree: `openauto.ini:8` → `ServiceFactory.cpp:149-152` (touchscreen config) → `auriga_stream.py:172-173` (`hello`) → `index.html:32` (+ `app.js:179-180` mapping). Changing `Video.Resolution` breaks the phone's touch mapping and the browser canvas silently.
- A7: Sink `open`/`stop`/`write` are serialized by one strand (`VideoService.cpp:28-33`). Baked into the sinks' designs. If a service is ever constructed with a different strand than its channel, the file and the truncation state race.
- A8: `input.jsonl` `ts` (epoch µs, `AurigaInputDevice.cpp:225-229`), the AA `InputReport.timestamp` (µs in a field the proto calls nanoseconds, `InputSourceService.cpp:177-183` vs `InputReport.proto:12`) and the stream wire timestamp (monotonic µs, `auriga_stream.py:153-154`) are three unrelated clocks, none of which can be aligned.

## Bugs
- B1 [high]: The FIFO path is resolved twice. `run-mac.sh:22` honours `AURIGA_INPUT_FIFO` for `autoapp` stdin, `mac-headunit-start.sh:61` hardcodes `--fifo /tmp/auriga-in` for the server. Scenario: `AURIGA_INPUT_FIFO=/tmp/x mac-headunit-start.sh` → the server writes `/tmp/auriga-in` (ENXIO, log only) and every tap is lost with the UI looking alive.
- B2 [medium]: The codec-config payload is appended to the media files. `VideoMediaSinkService.cpp:190-193` and `AudioMediaSinkService.cpp:222-226` route the config callback into the timestamp callback, and both sinks write unconditionally (`AurigaVideoOutput.cpp:65-67`, `AurigaAudioOutput.cpp:97-99`). Video survives by luck (Annex-B, filtered into `pending`); the PCM file is only safe because the PCM config payload is empty today. Scenario: any non-empty audio config, or a video config without start codes, corrupts the file the streamer parses.
- B3 [medium]: Session boundaries are unsynchronized across the three sinks and only one of them is signalled. Video truncates at video channel open, audio at audio channel open, `input.jsonl` at `KeyBindingRequest`; the streamer resets video and rebroadcasts `hello`, and resets audio without telling anyone. Scenario: reconnect → clients keep the old audio anchor while PCM restarts from byte 44, so a burst of new-session audio is played at the old position.
- B4 [medium]: Startup replays the previous run's tail. `find_last_idr` seeks into the existing file (`auriga_stream.py:135-136`) before the new session truncates it, so a client sees up to 8 MiB of old frames and taps on a picture the phone is not showing. Evidence: three consecutive `stream-mac-*.log:2` lines with `video_offset=19706264`; the reset only arrives at `:14`.
- B5 [medium]: PCM chunk timestamps are read-time and cluster. `auriga_stream.py:338` computes `self.timestamp()` inside the per-chunk loop, so a backlog read yields timestamps microseconds apart for chunks that represent 40 ms each; `app.js:154` schedules by timestamp, so they all start at the same instant. Scenario: any stall (head-unit write burst, 9 sockets) → overlapping playback and permanent audio offset.
- B6 [medium]: The advertised ping contract contradicts the implementation: `interval_ms=1000, timeout_ms=3000, tracked_ping_count=5` (`AndroidAutoEntity.cpp:187-191`) vs a 5000 ms timer with one outstanding ping and a 5-miss give-up (`AndroidAutoEntityFactory.cpp:65`, `Pinger.cpp:26-52`). Scenario: the phone's watchdog counts 5 × 1000 ms without a ping and can drop the session while the head unit believes it is pinging.
- B7 [low]: `AURIGA_CAPTURE_DIR=""` splits the two capture-mode definitions. `App.cpp:32` treats it as capture mode (acceptor on port 0, no enumerator, no TCP accept) while `ServiceFactory.cpp:67` treats it as normal mode (Qt video, RtAudio, real screen geometry, no capture files). Scenario: exported empty variable → a headless process with the GUI backends and no stream data.
- B8 [low]: Two readers can share one stdin. Each entity creates its own `AurigaInputDevice` and `start()` spawns a thread on `STDIN_FILENO` (`AurigaInputDevice.cpp:58,127`); the old entity's `stop()` runs as a queued strand task (`InputSourceService.cpp:43-48`). Scenario: fast reconnect where the new entity receives `KeyBindingRequest` before the old service's stop task runs → FIFO lines split between two readers, taps interleaved or lost.
- B9 [low]: `AurigaInputDevice::eventHandler_` is set/cleared under `mutex_` (`AurigaInputDevice.cpp:70-71`) but read without it in `sendTouch` (`:203-214`). Scenario: stop during a command → race on a raw pointer.
- B10 [low]: The streamer writes the FIFO with no delivery signal and no reader check; failure is a server-side print (`auriga_stream.py:373-381`). Combined with B1, taps can disappear with no signal in the browser or the head-unit log.
- B11 [low]: One stalled WebSocket stalls the capture-side loop for everyone: `flush_frame` holds `self.lock` across `broadcast`, which awaits `ws.send` per client, and `handle` holds the same lock while sending hello plus the whole cached GOP. `auriga_stream.py:156-166,290-299,347-356`. Scenario: a backgrounded tab (9 sockets are open today) → video and reset detection freeze for all clients.

## Dead code, leftovers, stale comments
- L1: `auriga_stream.py:28` `VIDEO_FRAME_US` defined and never used.
- L2: `auriga_stream.py:125` `max_gop = 100000` with a comment describing a keyframe fallback; the branch at `:295-298` cannot trigger at ~1800-frame GOPs.
- L3: `AurigaAudioOutput::start`/`suspend` (`AurigaAudioOutput.cpp:109-111,126-128`) and `AurigaVideoOutput::init` (`:50-53`) are empty; the AA start/stop/suspend events never reach the sinks, which is why truncation had to be attached to `open()`.
- L4: `App::acceptor_` is bound to `0.0.0.0:<ephemeral>` in capture mode and never accepted (`App.cpp:42-43,185-188`) — a listening socket with no consumer.
- L5: `ServiceFactory::createWifiProjectionService` is unreachable; only a commented reference at `ServiceFactory.cpp:124` (`:262-266`).
- L6: `input.jsonl` is produced by `AurigaInputDevice.cpp:216-231` and read by nothing in the repo (only `captures/*-input.jsonl` fixtures); it truncates per session and is currently 0 bytes.
- L7: `audio-guidance.wav` and `audio-system.wav` are 44-byte stubs in the live run (`ls -l captures-mac/`), written by `ServiceFactory.cpp:192,218` and read by nobody.
- L8: `capture/` re-implements the same five-file contract with different framing (codec config written into the WAV/PCM stream, Annex-B unverified) — a second, incompatible producer of the same interface (`capture/src/AudioCapture.cpp:205-208`).

## Improvement areas
- I1: One session identity across the seam. Mechanism: mint a session id per AA entity and use it in the filename (`video-<id>.h264`) or as a first line in a sidecar, so the streamer reacts to a new file instead of inferring a reset from `size < offset` (`auriga_stream.py:218`) and so capture history survives (B3, B4).
- I2: Resolve every path once. Mechanism: `openauto-config/run-mac.sh` already knows capture dir and FIFO; pass both to the stream server as arguments derived from the same variables instead of re-deriving them in `mac-headunit-start.sh:11,61` (B1).
- I3: Publish geometry instead of hardcoding it. Mechanism: `hello` carries `width/height` from a constant (`auriga_stream.py:172-173`) while the authority is the SPS/`openauto.ini`; parse the SPS VUI or read the ini, and size the canvas from `hello` (`index.html:32`) (A6).
- I4: Separate codec config from media at the sink. Mechanism: cache the `onMediaIndication` payload per channel and prepend it once at open, instead of forwarding it into the media writer (`VideoMediaSinkService.cpp:190-193`) (B2).
- I5: Take file I/O out of the AA flow-control path. Mechanism: `max_unacked=1` plus ACK-after-write (`VideoMediaSinkService.cpp:117,177-187`) makes disk latency phone-visible; buffer in memory and ACK immediately.
- I6: Carry the AA timestamp. Mechanism: `write(timestamp, buffer)` already receives it and both sinks drop it (`AurigaVideoOutput.cpp:55-56`, `AurigaAudioOutput.cpp:87-88`); writing it beside the payload removes the fabricated clock in `auriga_stream.py:153-154` and the A/V offset (B5).
- I7: Per-client queues and no awaits under the state lock. Mechanism: `flush_frame` should only append to per-client queues; a send task per client drains them with drop-oldest for deltas (`auriga_stream.py:156-166,290-299`) (B11).
- I8: One capture-mode switch, checked once. Mechanism: read `AURIGA_CAPTURE_DIR` into one value at startup and pass it to `App` and `ServiceFactory` instead of two independent `getenv` reads with different empty-string semantics (`App.cpp:32` vs `ServiceFactory.cpp:67`) (B7).
- I9: Make the sink interface express "session started/stopped" instead of overloading `open()`. Mechanism: the empty `start()`/`suspend()` (`AurigaAudioOutput.cpp:109,126`) are exactly the hooks that would let truncation, reset and WAV finalization be explicit (L3, B3).

## Interfaces
- Exposes (the seam under audit, end to end):
  - `<capture-dir>/video.h264` — Annex-B, 4-byte start codes, codec-config SPS/PPS first, then one access unit per `write()` with a flush each (`AurigaVideoOutput.cpp:65-67`); file layout measured SPS@0, PPS@21, IDR@29.
  - `<capture-dir>/audio-media.wav` 48000/2/16, `audio-guidance.wav` 16000/1/16, `audio-system.wav` 16000/1/16, 44-byte header rewritten each ~1 s of data (`AurigaAudioOutput.cpp:101-106,145-166`).
  - `<capture-dir>/input.jsonl` — `{"ts":epoch_µs,"cmd","x","y"}` per line, flushed per line, truncated at `KeyBindingRequest` (`AurigaInputDevice.cpp:50,216-231`).
  - FIFO `/tmp/auriga-in` — `tap|down|move|up X Y`, `quit`; consumed as `autoapp` stdin (`run-mac.sh:36`), written by the stream server per event (`auriga_stream.py:372-378`).
  - WS/HTTP `127.0.0.1:8081`/`:8080` — `hello` JSON (width/height/fps/codec, base64 avcC), `{"type":"reset"}`, binary `>BQ` header + AVCC sample or PCM, client JSON `{type,x,y}` (`auriga_stream.py:168-180,289,338,417`).
  - `/tmp/{auriga-mac-autoapp,auriga-mac-stream,auriga-mac-caffeinate,auriga-fifo-writer}.pid`, `logs/openauto-mac-*.log`, `logs/stream-mac-*.log` (`mac-headunit-start.sh:41-42,62-63,75`).
  - `/tmp/entityexit` (video sink → Qt UI) and `/tmp/night_mode_enabled`, `/tmp/android_device` (external → OpenAuto); hidden shared state via `/tmp` (`VideoMediaSinkService.cpp:220-227`, `SensorService.cpp:45`, `autoapp.cpp:267`).
- Consumes:
  - The streamer consumes the two media files and the FIFO path as strings only; it has no reference to `autoapp` and no way to know whether a session is live (`auriga_stream.py:117-121`).
  - `autoapp` consumes the FIFO as stdin and the capture dir from the environment; it never reads anything from `stream/`.
  - The browser consumes `hello`/binary frames and assumes a `Hello`-driven decoder lifecycle; it hard-codes `ws://<host>:8081` (`app.js:29`), so `--ws-port` and HTTPS fronting break it.
- Threading:
  - `autoapp`: main thread runs Qt `exec()` (`autoapp.cpp:308`); 4 threads run `libusb_handle_events_timeout_completed` (`autoapp.cpp:46-61`); 4 threads run `ioService.run()` (`:63-73`).
  - One strand per service and per entity. The aasdk channel is constructed with the service's own `strand_`, so channel receive, sink write, ACK send and `stop()` are serialized (`VideoService.cpp:28-33`, `MediaAudioService.cpp:26-33`, `VideoMediaSinkService.cpp:43-50`). The per-file `std::mutex` in both sinks is therefore uncontended.
  - `AurigaInputDevice` adds one raw `std::thread` per entity doing `poll`/`read` on stdin, then `eventHandler_->onTouchEvent` → `strand_.dispatch`; `tap` sleeps 80 ms inside that thread (`AurigaInputDevice.cpp:58,122-154,168-174`); `stop()` joins it from a strand task (`InputSourceService.cpp:43-48`).
  - `AurigaAudioInput` paces silence with a `deadline_timer` on the io_service (`patches/openauto-capture.patch:327-350`), not a thread.
  - `AurigaStream`: one asyncio loop running `video_loop`, `audio_loop`, the WS server and one task per client, plus one `ThreadingHTTPServer` daemon thread for HTTP (`auriga_stream.py:395-397,414-419`). A single `asyncio.Lock` covers GOP bookkeeping, broadcast and new-client send (`:123,290,347`).
  - Cross-process: no locks, no sockets for data; ordering is carried only by file append order and by the FIFO's line atomicity.

## Open questions for the user
- Q1: Should the seam between the head unit and the UI stay a set of files (simple, no protocol, loses sessions) or become a socket/session-id protocol produced directly from the aasdk callbacks?
- Q2: Is one session per capture run acceptable (files overwritten, one reset), or must sessions be addressable and retained?
- Q3: Must navigation/system audio reach the browser, or is media-only PCM the contract?
- Q4: Are multiple simultaneous browser clients a requirement? Today 9 sockets are open against one viewer, and one stalled socket blocks the capture-side loop.
- Q5: Is the capture/WAV header allowed to change format (RF64, per-session names, sidecar timestamps), or must `video.h264` + 44-byte WAV stay byte-compatible for an existing consumer?

## Result
The inter-aspect contract is one directory of append-only files plus one FIFO, with session identity, geometry, capture mode, the FIFO path and the codec config each defined two to four times. The top three defects: the FIFO path is resolved independently in `run-mac.sh:22` and `mac-headunit-start.sh:61` (taps lost silently); the codec-config callback is written into the media files (`VideoMediaSinkService.cpp:190-193`); session boundaries are unsynchronized and only video truncation is signalled (`auriga_stream.py:218-238` vs `316-324`). Threading inside `autoapp` is sound (one strand per service, shared with its channel); the sinks' mutexes are redundant, and the asyncio lock is held across socket sends.
