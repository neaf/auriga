# Functional requirements

Consolidated from `.rearch/inventory.md`, `.rearch/baseline.md` and the seven
aspect audits plus `seams.md`. Duplicate behaviors merged across aspects. Every
requirement carries evidence (`file` plus symbol, or `file:line` where the line is
stable) and a status: `kept`, `open` (experimental/unclear), or `dropped`.

Baseline: manual checklist M1–M8 asserted passing by the user on 2026-10-29
(M8, the Pi fallback, is dropped; later phases use M1–M7).

## HU — head unit (patched OpenAuto / `autoapp`)

- FR-HU-01: AOA switch is restricted to the AutoLink dongle VID/PID
  `2717:ff40`; no other device is sent the AOA query chain.
  Evidence: `patches/aasdk-usb-filter.patch`,
  `openauto/src/autoapp/autoapp.cpp` (USBHub pair); audit/openauto-integration.md#F1.
  Status: kept.
- FR-HU-02: Capture mode is a single opt-in env `AURIGA_CAPTURE_DIR` that
  substitutes video/audio/mic/input file sinks and disables the TCP server.
  Evidence: `openauto/src/autoapp/Projection/AurigaSession.cpp`
  (`captureDirectory`, `captureModeEnabled`), `Service/ServiceFactory.cpp`,
  `App.cpp`; audit/openauto-integration.md#F2. Status: kept.
- FR-HU-03: Video sink appends raw Annex-B H.264 access units to
  `<capture-dir>/current/video.h264`, flushed per access unit.
  Evidence: `openauto/src/autoapp/Projection/AurigaVideoOutput.cpp`;
  audit/openauto-integration.md#F3. Status: kept.
- FR-HU-04: Three audio sinks write one WAV each — media 48 kHz/2ch/16-bit,
  guidance 16 kHz/1ch/16-bit, system 16 kHz/1ch/16-bit — header refreshed ~1 s.
  Evidence: `openauto/src/autoapp/Projection/AurigaAudioOutput.cpp`,
  `Service/ServiceFactory.cpp` (audio sink wiring);
  audit/openauto-integration.md#F4. Status: kept.
- FR-HU-05: Silent microphone source paces 20 ms zero buffers.
  Evidence: `openauto/src/autoapp/Projection/AurigaAudioInput.cpp`;
  audit/openauto-integration.md#F5. Status: kept.
- FR-HU-06: Touch input is read from stdin (the FIFO) as `tap|down|move|up X Y`
  plus `quit`, logged to `input.jsonl`, converted to AA input actions.
  Evidence: `openauto/src/autoapp/Projection/AurigaInputDevice.cpp`;
  audit/openauto-integration.md#F6. Status: kept (`quit` ends the reader; a later
  `KeyBindingRequest` restarts it).
- FR-HU-07: Input device starts only after the phone sends `KeyBindingRequest`;
  earlier touches are ignored.
  Evidence: `InputSourceService.cpp` (`onKeyBindingRequest` → `start`);
  audit/openauto-integration.md#F7. Status: kept.
- FR-HU-08: Sensor answers driving status `UNRESTRICTED`, night mode from
  `/tmp/night_mode_enabled`, GPS read guarded by `gps_open` success, 250 ms poll.
  Evidence: `SensorService.cpp`; `patches/openauto-auriga-gps-guard.patch`;
  audit/openauto-integration.md#F12. Status: kept.
- FR-HU-09: Bluetooth service (dummy device) answers pairing with
  `STATUS_SUCCESS`, PIN `123456`, advertises `BLUETOOTH_PAIRING_UNAVAILABLE`.
  Evidence: `BluetoothService.cpp`, `DummyBluetoothDevice.cpp`;
  audit/openauto-integration.md#F13. Status: kept (Q2: keep as-is; investigate
  the first-session reset later, no `WirelessProjectionEnabled` hardware test).
- FR-HU-10: AA identity is `Auriga` (display name, make, model) with driver
  `RIGHT`, from `patches/openauto-auriga-identity.patch`.
  Evidence: `AndroidAutoEntity.cpp` (identity block);
  audit/openauto-integration.md#F11. Status: kept (rename done).
- FR-HU-11: Reconnect after an entity error via `onAndroidAutoQuit ->
  waitForDevice`.
  Evidence: `App.cpp` (`onAndroidAutoQuit`, `waitForDevice`); audit/openauto-integration.md#F8.
  Status: kept (quit-and-wait path). The commented-out USB-hub-error retry path
  is dropped.
- FR-HU-12: A new AA entity opens its sinks with `std::ios::trunc` inside a fresh
  `session-<id>/` directory, so it never truncates a previous session's files.
  Evidence: `AurigaVideoOutput.cpp`, `AurigaAudioOutput.cpp`,
  `AurigaInputDevice.cpp`, `AurigaSession.cpp`; audit/openauto-integration.md#F14.
  Status: dropped (Q5: replaced by per-session retention, FR-STR-13).

## STR — stream server + browser client

- FR-STR-01: HTTP server on `127.0.0.1:8080` serves `stream/web` static files
  (`ThreadingHTTPServer`, daemon thread, request logging off).
  Evidence: `stream/server.py` (`serve_http`); audit/stream.md#F1. Status: kept.
- FR-STR-02: WebSocket on `127.0.0.1:8081`, no auth; connect gets one JSON
  `hello` `{type,width,height,fps,codec,description}` with base64 avcC from SPS/PPS.
  Evidence: `stream/server.py` (`Streamer.hello`, `handle`);
  `stream/lib/h264.py` (`extract_sps_pps`, `build_avcc`); audit/stream.md#F2.
  Status: kept.
- FR-STR-03: Video tail: read `video.h264` Annex-B, split NALs on 4-byte start
  codes, emit one VCL NAL per frame as `type:u8=1|3 | ts_us:u64 BE | AVCC`.
  Evidence: `stream/lib/h264.py` (`split_nals`, `FrameAssembler`),
  `stream/server.py` (`video_loop`, `flush_frame`); audit/stream.md#F3. Status: kept.
- FR-STR-04: Startup seeks to the last type-5 NAL in the last 8 MiB; else offset 0.
  Evidence: `stream/lib/h264.py` (`find_last_idr`); audit/stream.md#F4. Status: kept.
- FR-STR-05: A late client gets the cached GOP (messages since the last keyframe)
  replayed after `hello`; the cache is bounded to 2400 frames.
  Evidence: `stream/lib/h264.py` (`GopBuffer`), `stream/server.py` (`replay`);
  audit/stream.md#F5. Status: kept.
- FR-STR-06: Audio tail: skip the 44-byte WAV header, forward PCM as `type 2 |
  ts_us | payload` capped at 7680 bytes; only `audio-media.wav` is streamed.
  Evidence: `stream/server.py` (`audio_loop`); audit/stream.md#F6,F7.
  Status: kept (Q3: media-only contract; guidance/system WAVs are file-only).
- FR-STR-13: Capture files are per-session (head-unit-minted ids), rotate before
  4 GiB (same path restarts at 0, manifest count bumps), and keep five sessions.
  Evidence: `AurigaSession.hpp` (`SEGMENT_LIMIT`, `KEEP_SESSIONS`),
  `AurigaSession.cpp` (`prune`, `noteRotation`); Q5 decision.
  Status: kept.
- FR-STR-14: Exactly one browser viewer per session; a second client replaces the
  first (close code 4001).
  Evidence: `stream/server.py` (`handle`, `REPLACED_CODE`); Q4 decision.
  Status: kept.
- FR-STR-07: A new `current` target drops the queue, sends `{"type":"reset"}` then
  `hello`, clears the GOP, re-extracts SPS/PPS and restarts the content clock; a
  manifest segment-count change reopens one file and re-reads its SPS/PPS.
  Evidence: `stream/server.py` (`adopt`, `video_loop`),
  `stream/lib/session.py` (`SessionFollower`). Status: kept.
- FR-STR-08: Client input `{type:"tap"|"down"|"move"|"up", x, y}` is written as
  `"<cmd> <x> <y>\n"` to the FIFO via a fresh `O_WRONLY|O_NONBLOCK` fd per event.
  Evidence: `stream/server.py` (`handle`); audit/stream.md#F9. Status: kept.
- FR-STR-09: Browser decodes with WebCodecs `VideoDecoder` (configured from
  avcC), draws to a canvas sized from `hello`/the decoded frame, and plays audio
  via WebAudio scheduled by message timestamp.
  Evidence: `stream/web/app.js` (`configureVideo`, `draw`, `playAudio`);
  audit/stream.md#F10. Status: kept.
- FR-STR-10: Audio is muted by default; first unmute click creates/resumes the
  AudioContext.
  Evidence: `stream/web/app.js` (`setMuted`, `ensureAudio`);
  audit/stream.md#F11. Status: kept.
- FR-STR-11: Gesture semantics: >8 px movement sends `down` at the press point,
  `move`s throttled to 50 ms, `up` at release; otherwise one `tap` at the press
  point. Non-primary pointers and non-left mouse buttons are ignored.
  Evidence: `stream/web/app.js` (pointer handlers); audit/stream.md#F12.
  Status: kept.
- FR-STR-12: Client reconnects to the WS every 2 s on close and reconfigures the
  decoder on `hello`.
  Evidence: `stream/web/app.js` (`connect`, `socket.onclose`);
  audit/stream.md#F13. Status: kept.

## RUN — runtime orchestration (scripts)

- FR-RUN-01: `scripts/auriga.sh start` brings up `autoapp` (offscreen capture),
  the stream server, `caffeinate`, waits for both listeners, then opens Brave at
  `http://localhost:8080`.
  Evidence: `scripts/auriga.sh` (`cmd_start`, `cmd_status`);
  audit/runtime-orchestration.md#F1. Status: kept.
- FR-RUN-02: Start is all-or-nothing: when either component of a pair runs, the
  start refuses the whole pair instead of starting the other half.
  Evidence: `scripts/auriga.sh` (`find_autoapp`/`find_stream`, `cmd_start`);
  audit/runtime-orchestration.md#F3. Status: kept (as built; see deviations P6).
- FR-RUN-03: Exactly one FIFO `AURIGA_INPUT_FIFO` (default `/tmp/auriga-in`) is
  recreated (`rm`+`mkfifo`) with a background `sleep 31536000 > FIFO` writer so
  the stdin open does not block; stale writers are reaped.
  Evidence: `scripts/auriga.sh` (`start_fifo`); audit/runtime-orchestration.md#F4.
  Status: kept.
- FR-RUN-04: Stop is signal-based: cmdline-checked SIGTERM from the lock, 10 s
  grace, SIGKILL, then `pkill -f` for `autoapp`/stream/FIFO-writer orphans; no
  graceful shutdown, no `reset` for clients.
  Evidence: `scripts/auriga.sh` (`stop_pid`, `cmd_stop`);
  audit/runtime-orchestration.md#F8. Status: kept.
- FR-RUN-05: Pi fallback = start-on-Pi plus SSH tunnel on Mac (`-L 8080 -L 8081`).
  Evidence: deleted `scripts/pi-start.sh` / `scripts/mac-start.sh`.
  Status: dropped (Q1: macOS-local is the only supported mode).
- FR-RUN-06: Stream server binds `127.0.0.1` only for HTTP and WS; ports come from
  `AURIGA_HTTP_PORT`/`AURIGA_WS_PORT` (default 8080/8081) in one place.
  Evidence: `scripts/auriga.sh`, `stream/server.py` (`serve_http`),
  `stream/auriga_stream.py`; audit/runtime-orchestration.md#F12. Status: kept.

## DGL — dongle hardware (AutoLink A512)

- FR-DGL-01: Dongle enumerates MTP `2717:ff40` and re-enumerates AOA `18d1:2d00`
  after the host AOA v2 switch.
  Evidence: `docs/AutoLink A512 dongle.md#usb-identity`, `logs/*.log`
  (`Version Received`); audit/dongle-hardware.md#F1. Status: kept.
- FR-DGL-02: The host rejects `18d1:2d01` (AOA+ADB phone) as a dongle target.
  Evidence: `patches/aasdk-usb-filter.patch`, `aasdk-upstream/src/USB/USBHub.cpp`;
  audit/dongle-hardware.md#F2. Status: kept.
- FR-DGL-03: Dongle reports AA protocol 1.7 (`256.1792`); aasdk's `AASDK_MINOR`
  is 7 in `patches/aasdk-version-absl.patch`.
  Evidence: `docs/AutoLink A512 dongle.md#aa-protocol-version`,
  `aasdk-upstream/include/aasdk/Version.hpp`; audit/dongle-hardware.md#F4,F5.
  Status: kept (Q6: promoted into `patches/`).
- FR-DGL-04: `videoInfo` is a 364-byte little-endian struct (magic, width/height
  u32, SPS/PPS, phone BT address, 10-byte head-unit name, 8-byte session tag).
  Evidence: `docs/AutoLink A512 dongle.md#videoinfo-layout`; byte inspection of
  all snapshots; audit/dongle-hardware.md#F7. Status: kept (as a constraint; the
  `videoInfo.galaxy` snapshots are invalid and must not be restored).
- FR-DGL-05: BT pairing DB (`btapp.db`/`btapp.bk`, 207-byte or 33-byte forms);
  recovery = delete DB + cold replug + re-pair (6-digit numeric comparison).
  Evidence: `docs/AutoLink A512 dongle.md#btappdb-layout`, `#recovery`;
  audit/dongle-hardware.md#F8. Status: kept.
- FR-DGL-06: CarPlay mode (`05ac:12a8`) is a software-unreachable latch under the
  `2717:ff40` filter.
  Evidence: `docs/AutoLink A512 dongle.md#carplay-latch`,
  `patches/aasdk-usb-filter.patch`; audit/dongle-hardware.md#F10. Status: kept as
  a documented runbook note (Q8); no code path.

## CAP — minimal capture app (`capture/`, reference/dead)

- FR-CAP-01: AOA v2 switch of the dongle only, retried up to 240× at 500 ms.
  Evidence: `capture/src/Usb.cpp:48-110`; audit/minimal-capture.md#F1. Status:
  dropped (Q7: delete `capture/`).
- FR-CAP-02: AA version → TLS → auth → service discovery; advertises video, 3
  audio sinks, mic, sensor, input.
  Evidence: `capture/src/main.cpp:116-161`; audit/minimal-capture.md#F2,F3.
  Status: dropped (Q7).
- FR-CAP-03: Bluetooth service, Wi-Fi projection service, telephony audio sink are
  compiled but never instantiated.
  Evidence: `capture/CMakeLists.txt:50,53` vs `main.cpp:114-164`;
  audit/minimal-capture.md#F4. Status: dropped (Q7).
- FR-CAP-04: stdin protocol `tap|down|move|up X Y` and `quit` (`quit` only stops
  the reader loop).
  Evidence: `capture/src/main.cpp:202-224`; audit/minimal-capture.md#F16. Status:
  dropped (Q7).
- FR-CAP-05: `capture/` builds only with a Boost 1.85 pin and explicit
  `AASDK_SOURCE`/`AASDK_BUILD` overrides.
  Evidence: `capture/CMakeLists.txt:10-37`; audit/minimal-capture.md#F19.
  Status: dropped (Q7).

## PHONE — phone-side AA app design (no implementation)

- FR-PHONE-01: Phone runs the AA phone role (BT WPP bootstrap, dongle AP, TCP/TLS,
  AA 1.7, video/audio/input). Evidence: `PHONE-APP.md:88-102`;
  audit/phone-app-design.md#F1. Status: dropped (Q9: no code, no AARE checkout).
- FR-PHONE-02: Custom car UI rendered into a private `VirtualDisplay` +
  `Presentation` feeding the encoder, no `MediaProjection`.
  Evidence: `PHONE-APP.md:121-142`; audit/phone-app-design.md#F6. Status: dropped
  (Q9; claims about AARE internals not present in repo).
- FR-PHONE-03: Audio split: nav TTS on guidance channel, Spotify on media channel.
  Evidence: `PHONE-APP.md:167-176`; audit/phone-app-design.md#F7. Status: dropped
  (Q9).
- FR-PHONE-04: Pi car server roles (CAN/OBD-II, vehicle state, librespot PCM over
  USB, power sequencing). Evidence: `PHONE-APP.md:284-334`;
  audit/phone-app-design.md#F8. Status: dropped (Q9).

## BLD — build and tooling

- FR-BLD-01: A `Release` autoapp builds from the five OpenAuto patches
  (`capture -> macos -> auriga-usb-filter -> auriga-gps-guard ->
  auriga-identity`) plus two aasdk patches (`aasdk-usb-filter`,
  `aasdk-version-absl`: `Version.hpp` 6→7 + the protobuf absl include).
  Evidence: `patches/*.patch`, `scripts/build.sh`, `docs/Build.md`;
  audit/build-and-tooling.md#F1,F3,A1. Status: kept.
- FR-BLD-02: `patches/` is the source of truth for a clean rebuild; the build
  script refuses to run when a patch in `patches/` is not applied by its lists.
  Evidence: `scripts/build.sh` (`check_complete`), the reverse checks in
  `docs/Build.md`; audit/build-and-tooling.md#D1. Status: kept (satisfied).
- FR-BLD-03: Boost 1.85 is required (`io_service` removed from Boost ≥ 1.87);
  Homebrew default 1.92 fails. Evidence: `docs/Build.md#boost-must-be-185`;
  audit/build-and-tooling.md#X1. Status: kept.
- FR-BLD-04: CMake 4.4.4 requires `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`.
  Evidence: both `CMakeCache.txt`, `docs/Build.md#cmake-policy-minimum`;
  audit/build-and-tooling.md#X2. Status: kept.
- FR-BLD-05: `capture/` is a self-contained CMake project with `--out/--duration/
  --no-input`; no Mac build directory, documented as rejected.
  Evidence: `capture/CMakeLists.txt`; audit/build-and-tooling.md#F11.
  Status: dropped (Q7).
- FR-BLD-06: One script applies every patch and builds aasdk + autoapp from clean
  clones. Evidence: Q10 decision; `scripts/build.sh`;
  audit/build-and-tooling.md#I1. Status: kept.
- FR-BLD-07: The aasdk `Version.hpp` 6→7 and `protobuf/CMakeLists.txt` absl edits
  live in `patches/`, not only in the nested working tree. Evidence: Q6 decision;
  `patches/aasdk-version-absl.patch`; audit/build-and-tooling.md#D1. Status: kept.

## Non-functional

- NFR-01: File I/O must not sit in the AA flow-control path (`max_unacked=1` and
  ACK-after-write make disk latency phone-visible). Satisfied: the media ACK is
  sent before the queue copy and a writer thread does the file I/O.
  Evidence: `VideoMediaSinkService.cpp` (ACK before `write`),
  `AudioMediaSinkService.cpp`, `AurigaWriter.hpp` (bounded queue);
  audit/seams.md#F5,I5. Status: kept, satisfied.
- NFR-02: Video flush is per access unit; stream video poll is 8 ms — near-real-time
  latency for live mirroring. Evidence: `AurigaVideoOutput.cpp` (flush per AU),
  `stream/server.py` (`POLL_INTERVAL`). Status: kept.
- NFR-03: Stream server binds localhost only and has no auth; must never be exposed
  publicly. Evidence: `AGENTS.md#safety`, `stream/server.py` (`serve_http` bind).
  Status: kept.
- NFR-04: Platform: macOS (Apple Silicon) is the only supported head-unit host;
  the Pi fallback is dropped. Evidence: `baseline.md`; Q1 decision. Status: kept.
- NFR-05: Capture growth is bounded: per-session files rotate before 4 GiB and
  retain five sessions. Satisfied. Evidence: `AurigaSession.hpp`
  (`SEGMENT_LIMIT`, `KEEP_SESSIONS`), `AurigaSession.cpp` (`prune`); Q5 decision.
  Status: kept, satisfied.
- NFR-06: WAV header uses 32-bit RIFF sizes; wraps at ~4 GiB audio (~6.2 h).
  Evidence: `AurigaAudioOutput.cpp` (header rewrite); audit/stream.md#X3. Status:
  dropped (rotation before 4 GiB makes the wrap unreachable; absorbed by
  NFR-05/FR-STR-13).
- NFR-07: Startup readiness is a poll of the listen sockets, not a fixed
  `sleep 1`. Satisfied: `wait_port` polls HTTP then WS (`nc -z`, 20 s,
  `AURIGA_READY_TIMEOUT`). Evidence: `scripts/auriga.sh` (`wait_port`, `cmd_start`).
  Status: kept, satisfied.
- NFR-08: One `autoapp`/stream pair owns the dongle and capture dir; enforced by a
  lock file plus a cmdline-checked pid, not only `pgrep` heuristics. Satisfied:
  `<capture-dir>/.auriga.lock` + `.auriga.start` guard. Evidence:
  `scripts/auriga.sh` (`take_guard`, `write_lock`, `find_autoapp`/`find_stream`),
  `AGENTS.md#integration-contract`. Status: kept, satisfied.

## Constraints from external systems

- CON-DGL-01: USB IDs — dongle MTP `2717:ff40`, dongle AOA `18d1:2d00`, phone
  AOA+ADB `18d1:2d01` (never grab), phone MTP+ADB `04e8:6860`.
  Evidence: `AGENTS.md#usb--phone-invariants`. Unverified as hardware fact beyond
  observed `ioreg`.
- CON-DGL-02: Dongle BT Classic `AutoLink-A512` `ED:A2:A4:94:4F:B8`; Wi-Fi AP
  `AutoLink-A512` BSSID `e8:5c:b1:b5:c6:41` 5180 MHz WPA2 `12345678`.
  Evidence: `docs/AutoLink A512 dongle.md#bluetooth-and-wi-fi-identity`;
  audit/dongle-hardware.md#X7. Unverified.
- CON-DGL-03: Dongle re-enumerates MTP roughly every 22.0 s while idle (de-facto
  discovery watchdog). Evidence: `docs/AutoLink A512 dongle.md#idle-re-enumeration`;
  audit/dongle-hardware.md#X4. Unverified (not re-measured after BT DB reset).
- CON-HU-01: Captured AA stream is 1280x720 H.264 Baseline level 3.1, 4-byte
  Annex-B start codes, one slice/frame, IDR every ~1800 frames.
  Evidence: `docs/Android Auto head unit.md#aa-stream-format`; audit/stream.md#X1.
  Verified by ffprobe.
- CON-HU-02: aasdk is the TLS client, peer verification off (`SSL_VERIFY_NONE`),
  static headunit cert/key. Evidence: `SSLWrapper.cpp`, `Cryptor.cpp`;
  audit/phone-app-design.md#F2,F3. Verified.
- CON-STR-01: WebCodecs requires a secure context; `localhost` qualifies,
  `ws://` from an HTTPS page does not (mixed content).
  Evidence: `stream/web/app.js`, `AGENTS.md#safety`. Verified (vendor doc).
- CON-BLD-01: macOS AirPlay Receiver owns TCP 5000; capture mode binds port 0.
  Evidence: `patches/openauto-macos.patch`, `App.cpp`. Verified.

## Dropped

User decisions, 2026-10-29:
- Pi fallback: FR-RUN-05, `scripts/pi-start.sh`, `scripts/pi-stop.sh`,
  `scripts/mac-start.sh`, `scripts/mac-stop.sh`, and Pi run docs (Q1).
- Phone-side AA app design: FR-PHONE-01..04 and `PHONE-APP.md` (Q9).
- Minimal capture app: FR-CAP-01..05 and `capture/` (Q7).
- Truncate-on-session capture: FR-HU-12, replaced by FR-STR-13 (Q5).
- Multiple simultaneous browser viewers: replaced by FR-STR-14 (Q4).
- Streaming guidance/system audio: media-only contract (Q3).
- USB-hub-error retry path in FR-HU-11: keep only quit-and-wait reconnect.
- WAV 32-bit size wrap: NFR-06, made unreachable by rotation (NFR-05).

## Open questions

None. Resolved 2026-10-29:

- Q1 Pi support: drop. macOS-local is the only supported mode.
- Q2 Bluetooth reset: keep the dummy service as-is; investigate the first-session
  reset later; no `WirelessProjectionEnabled` hardware test now.
- Q3 Audio: media-only PCM to the browser; guidance/system are file-only.
- Q4 Viewers: one browser viewer per session.
- Q5 Capture retention: per-session timestamped files, rotate before 4 GiB,
  bounded retention.
- Q6 aasdk edits: promote `Version.hpp` 6→7 and the protobuf absl edit into
  `patches/`.
- Q7 `capture/`: drop.
- Q8 CarPlay mode: runbook note only; no code path.
- Q9 Phone-app design: drop.
- Q10 One-command rebuild: yes, add a patch-apply + build script.

## Refuted audit findings

- minimal-capture.md#B2 [high] is partly refuted. The premise "`quit` stops the
  io_service" is wrong: `quit` only breaks the stdin reader loop
  (`capture/src/main.cpp:219-220`) and does not stop the io_service. SIGTERM/SIGINT
  ARE handled via `signal_set` → `ioService.stop()` (`main.cpp:168-175`), so
  signal-driven stop finalizes WAV headers via destructors. The residual truth:
  `HeadUnit::stop()` is never called explicitly, and SIGKILL/crash leave the WAV
  header unpatched. Downgrade to medium; `--duration` (not `quit`) is the
  header-unfinalized path via `ioService.stop()`.
