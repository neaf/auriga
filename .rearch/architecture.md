# Architecture

Target design for the Auriga head unit + capture rig, designed from
`.rearch/requirements.md` alone. macOS is the only supported host. The patched
OpenAuto/aasdk stack is kept as an external adapter built from `patches/`; it is
not replaced.

## Overview

```
phone ──BT/Wi-Fi──▶ AutoLink A512 dongle ──USB AOA──▶ autoapp (OpenAuto, patched)
                                                        │  AURIGA_CAPTURE_DIR
                                                        ▼
                                              <capture-dir>/current → session-<id>/
                                              │   video.h264            (segmented)
                                              │   audio-media.wav
                                              │   audio-guidance.wav
                                              │   audio-system.wav
                                              │   input.jsonl
                                              │   manifest.json
                                              ▼
                                         auriga_stream.py (asyncio)
                                         HTTP 127.0.0.1:8080 / WS 8081
                                                        │
                                              Brave (WebCodecs + WebAudio)
                                                        │  tap|down|move|up X Y
                                                        ▼
                                                  /tmp/auriga-in ──▶ autoapp stdin
```

The seam between the head unit and the UI stays a directory of files plus one
FIFO. What changes is that a session has identity: the head unit mints a session
id, writes per-session files, and publishes a `current` pointer and a
`manifest.json`; the stream server follows the pointer instead of inferring a
session change from `size < offset`.

## Modules (one responsibility each)

| Module | Location | Responsibility |
| --- | --- | --- |
| headunit adapter | `openauto/` + `aasdk-upstream/` via `patches/` | External adapter for the dongle + AA protocol: AOA switch, TLS, AA channels, sensor/BT/identity, capture sinks. Not owned; `patches/` is the source of truth. |
| capture sink | inside headunit adapter (`Auriga*` files) | Write media to per-session files: session id + `current`/manifest, codec-config separation, size-bounded segment rotation, retention prune, buffered write, WAV finalize. |
| stream server | `stream/auriga_stream.py`, `stream/server.py`, `stream/lib/` | Tail the current session, convert Annex-B→AVCC and WAV→PCM, emit the wire protocol, single viewer with a bounded queue, HTTP static, FIFO write. |
| stream libs (pure) | `stream/lib/h264.py`, `stream/lib/session.py`, `stream/lib/clock.py` | Pure, hardware-free logic: NAL split / SPS-PPS / avcC; session naming, manifest parse, retention; content clock. |
| browser client | `stream/web/app.js`, `stream/web/index.html` | WebCodecs decode, WebAudio scheduling, canvas draw, touch gestures, reconnect. |
| runtime orchestration | `scripts/auriga.sh`, `openauto-config/run.sh` | Start/stop/status, single-instance lock, readiness poll, single source for capture-dir + FIFO paths. |
| build tooling | `scripts/build.sh`, `patches/` | Apply patches + build aasdk + autoapp from clean clones; `patches/` is the complete source of truth. |
| diagnostics | `tools/aoa_probe.py`, `tools/aoa_read.py` | Standalone dongle AOA switch/read tools (not part of start/stop). |

## Data flow

1. autoapp AOA-switches the dongle (`2717:ff40` → `18d1:2d00`) and runs the AA
   protocol. Only the dongle is ever switched; a phone in MTP+ADB is left alone.
2. When a video channel opens, the capture sink mints a session id, creates
   `<capture-dir>/session-<id>/`, atomically repoints `<capture-dir>/current` at
   it, and writes `manifest.json` (session id, width/height/fps, per-stream
   segment counts).
3. Video/media/guidance/system sinks and the input device write into the same
   session dir, so all four truncate at the same instant (fixes the
   unsynchronized-boundary bug). Codec config is written once as the SPS/PPS
   head of the video segment, never mixed into PCM.
4. The stream server resolves `current`, tails `video.h264` and
   `audio-media.wav` (guidance/system are file-only), and emits AVCC/PCM frames.
   On `current` change it broadcasts `{"type":"reset"}` then a fresh `hello`
   with geometry taken from `manifest.json`. On a segment-count change it
   reopens that stream's file without a reset.
5. Browser decodes/draws/plays; touch gestures become `tap|down|move|up X Y`
   JSON → WS → FIFO → autoapp stdin → AA input channel + `input.jsonl`.

## Threading and real-time model

- **autoapp.** Qt main thread; 4 `io_service.run()` threads; 1 libusb event
  thread. Each service owns a `boost::asio::strand` shared with its channel, so
  channel receive, sink write, ACK send and stop are serialized on one strand.
  The sink's per-file `std::mutex` is removed once writes move off the channel
  strand (see below). `AurigaInputDevice` keeps one raw reader thread doing
  `poll`/`read` on stdin; `AurigaAudioInput` and the sensor use
  `deadline_timer`s on the io_service, no threads.
- **Real-time boundary (NFR-01).** The AA media callback (on the channel strand)
  must not touch disk. New flow: the callback copies the buffer into a bounded
  in-memory queue and returns immediately; the media ACK is sent on the strand
  right after the copy, not after the write. A dedicated writer thread (one per
  sink, or one shared) drains the queue to the segment file and performs
  rotation/retention/header rewrite. High-water mark: if the queue is full, the
  oldest frame is dropped and counted, never block the strand.
- **Stream server.** One asyncio loop: `video_loop`, `audio_loop`, the WS server,
  one send task per viewer (at most one), and a `ThreadingHTTPServer` daemon
  thread for static files. The tail loops only append to the viewer's bounded
  `asyncio.Queue`; they never `await` a socket and never hold a lock across a
  send. Deltas drop-oldest when the queue is full. `self.lock` shrinks to GOP
  bookkeeping only.
- **Clock.** The stream server keeps one content clock: video timestamp =
  `frame_index * 1_000_000 / fps`, audio timestamp = `sample_index * 1_000_000 /
  48000`. Read-time `time.monotonic()` is removed, so A/V stay aligned and a
  read backlog no longer clusters timestamps.

## Interfaces

- **Capture dir contract.** `<capture-dir>/current` (symlink to
  `session-<id>`), `session-<id>/{video.h264, audio-media.wav,
  audio-guidance.wav, audio-system.wav, input.jsonl, manifest.json}`. Video is
  Annex-B, 4-byte start codes, SPS/PPS at the head of each segment. Media WAV is
  48 kHz/2ch/16-bit, guidance/system 16 kHz/1ch/16-bit, 44-byte header rewritten
  ~1 s. `manifest.json` = `{session, width, height, fps, video, audio-media,
  audio-guidance, audio-system}` where the last four are per-stream segment
  counts.
- **FIFO.** `/tmp/auriga-in` (or `AURIGA_INPUT_FIFO`), line protocol
  `tap|down|move|up X Y` + `quit`; `quit` stops only the input reader. The path
  is resolved once and passed identically to autoapp stdin and the stream
  server.
- **Wire protocol (unchanged framing, tightened semantics).** `hello`
  `{type,width,height,fps,codec,description}` with base64 avcC; `{"type":"reset"}`;
  binary `type:u8 | ts_us:u64 BE | payload` with `1`=keyframe, `3`=delta (AVCC),
  `2`=PCM s16le; client JSON `{type:"tap"|"down"|"move"|"up", x, y}` plus a new
  `{"type":"keyframe"}` request. HTTP/WS bind `127.0.0.1` only.
- **Env.** `AURIGA_CAPTURE_DIR` (opt-in capture mode, read once), `AURIGA_INPUT_FIFO`,
  `AURIGA_DIR`, `AURIGA_PYTHON`. `QT_QPA_PLATFORM=offscreen`.
- **Start/stop.** `scripts/auriga.sh {start|stop|status}`. One instance per
  capture dir, enforced by a lock file + pid check, not `pgrep` heuristics.

## Error handling

- Session change: `current` pointer changes → reset + `hello` + cleared GOP.
- Segment rollover: manifest count changes → reopen that file at 0, video
  re-extracts SPS/PPS from the new segment head; no reset.
- FIFO write failure (ENXIO/ENOENT): server logs and, when a viewer is
  connected, surfaces a status text; never raises.
- Stalled/absent viewer: bounded queue drops deltas; the capture loop never
  blocks.
- Graceful shutdown: autoapp installs SIGTERM/SIGINT → `App::stop()` → sink
  `stop()` finalizes WAV headers and closes segments; `auriga.sh stop` signals
  then verifies pids are gone.
- USB rejection: `onUSBHubError` re-arms `waitForDevice()` instead of idling
  silently (FR-HU-11 quit-and-wait path only; the all-device probe stays removed).

## External-system adapters (one topic doc each)

- `docs/AutoLink A512 dongle.md` — USB IDs, `videoInfo`/`btapp.db` layout,
  CarPlay latch, re-enumeration, recovery. Adapter: headunit (USB/AOA side).
- `docs/Android Auto head unit.md` — OpenAuto/aasdk patches, AA 1.7/TLS/service
  set, capture contract, identity, reconnect. Adapter: headunit (AA side).
- `docs/Stream protocol.md` — wire protocol, session/manifest, WebCodecs/WebAudio
  quirks (secure context, muted autoplay, decoder queue). Adapter: stream server
  + browser client.
- `docs/Build.md` — Boost 1.85, CMake 4.4 policy, taglib/absl/protobuf,
  patch order, one-command rebuild.

## FR → module traceability

| Requirement | Module | Phase |
| --- | --- | --- |
| FR-HU-01..09, 11 | headunit adapter | P5 (identity in P5) |
| FR-HU-10 (rename) | headunit adapter | P5 |
| FR-STR-01..06, 08..12 | stream server / browser | P4 |
| FR-STR-07 (reset) | stream server (mechanism → `current`) | P3/P4 |
| FR-STR-13 (per-session) | capture sink + stream libs | P3 |
| FR-STR-14 (one viewer) | stream server | P4 |
| FR-RUN-01..04, 06 | runtime orchestration | P6 |
| FR-DGL-01..06 | docs (dongle topic) | P1 |
| FR-BLD-01..07 | build tooling | P7 |
| NFR-01 | capture sink | P5 |
| NFR-02 | capture sink + stream server | P4/P5 |
| NFR-03 | stream server + orchestration | P4/P6 |
| NFR-04 | orchestration (macOS only) | P6 |
| NFR-05 | capture sink + stream libs | P3 |
| NFR-07 | orchestration | P6 |
| NFR-08 | orchestration | P6 |
| CON-* | docs + adapters | P1 |

## Old → new file mapping

| Current | Target |
| --- | --- |
| `stream/auriga_stream.py` (423, monolith) | `stream/auriga_stream.py` (thin CLI) + `stream/server.py` + `stream/lib/{h264,session,clock}.py` |
| `stream/web/app.js`, `index.html` | same paths, reworked (single-viewer, keyframe request, manifest geometry) |
| `scripts/mac-headunit-start.sh` + `mac-headunit-stop.sh` | `scripts/auriga.sh {start\|stop\|status}` |
| `openauto-config/run-mac.sh` + `run.sh` | `openauto-config/run.sh` (macOS only) |
| `patches/openauto-capture.patch` (1101) | same patch, extended (session, buffered write, codec-config separation, SIGTERM) |
| (no file) | `patches/aasdk-version-absl.patch`, `patches/openauto-auriga-identity.patch` |
| (no file) | `scripts/build.sh` |
| `scripts/aoa_probe.py`, `scripts/aoa_read.py` | `tools/aoa_probe.py`, `tools/aoa_read.py` |
| `docs in README.md/RUNBOOK.md/MAC-PORT.md/…` | `docs/{AutoLink A512 dongle,Android Auto head unit,Stream protocol,Build,requirements,architecture}.md` |

## What gets deleted

- `capture/` (26 files) — dropped (Q7), no replacement.
- `PHONE-APP.md` — dropped (Q9).
- `openauto-plan.md`, `NEXT-SESSION.md`, `MAC-PORT.md`, `RUNBOOK.md`,
  `stream/README.md`, `captures/README.md`, `dongle-backup/README.md` — facts
  folded into the topic docs.
- `scripts/pi-start.sh`, `pi-stop.sh`, `mac-start.sh`, `mac-stop.sh`,
  `aa-tap.sh` — Pi fallback dropped (Q1); `auriga.sh` replaces start/stop.
- `captures/*-input.jsonl` (tracked) and `logs/run-baseline-*.log` — folded;
  `.gitignore` gains `*.jsonl`.
- `posttrip/` — byte-identical duplicates of `dongle-backup/videoInfo.car-trip`
  etc.; canonical copies stay in `dongle-backup/`.
- `.rearch/` and the `rearch-base` tag / `rearch/*` branches — Stage 6.
