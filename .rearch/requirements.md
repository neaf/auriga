# Functional requirements

Consolidated from `.rearch/inventory.md`, `.rearch/baseline.md` and the seven
aspect audits plus `seams.md`. Duplicate behaviors merged across aspects. Every
requirement carries evidence (`file:line` + audit reference) and a status:
`kept`, `open` (experimental/unclear), or `dropped`.

Baseline: manual checklist M1–M8 asserted passing by the user on 2026-10-29.

## HU — head unit (patched OpenAuto / `autoapp`)

- FR-HU-01: AOA switch is restricted to the AutoLink dongle VID/PID
  `2717:ff40`; no other device is sent the AOA query chain.
  Evidence: `patches/aasdk-usb-filter.patch:55-88`,
  `openauto/src/autoapp/autoapp.cpp:245-246`; audit/openauto-integration.md#F1.
  Status: kept.
- FR-HU-02: Capture mode is a single opt-in env `AURIGA_CAPTURE_DIR` that
  substitutes video/audio/mic/input file sinks and disables the TCP server.
  Evidence: `openauto/src/autoapp/Service/ServiceFactory.cpp:64-97,165-167,227-229,246-248`;
  audit/openauto-integration.md#F2. Status: kept.
- FR-HU-03: Video sink appends raw Annex-B H.264 access units to
  `$AURIGA_CAPTURE_DIR/video.h264`, flushed per AU.
  Evidence: `patches/openauto-capture.patch:854-892`;
  audit/openauto-integration.md#F3. Status: kept.
- FR-HU-04: Three audio sinks write one WAV each — media 48 kHz/2ch/16-bit,
  guidance 16 kHz/1ch/16-bit, system 16 kHz/1ch/16-bit — header refreshed ~1 s.
  Evidence: `patches/openauto-capture.patch:440-572`,
  `ServiceFactory.cpp:184,192,218`; audit/openauto-integration.md#F4. Status: kept.
- FR-HU-05: Silent microphone source paces 20 ms zero buffers.
  Evidence: `patches/openauto-capture.patch:328-350`; audit/openauto-integration.md#F5.
  Status: kept.
- FR-HU-06: Touch input is read from stdin (the FIFO) as `tap|down|move|up X Y`
  plus `quit`, logged to `input.jsonl`, converted to AA input actions.
  Evidence: `patches/openauto-capture.patch:704-812`; audit/openauto-integration.md#F6.
  Status: kept.
- FR-HU-07: Input device starts only after the phone sends `KeyBindingRequest`;
  earlier touches are ignored.
  Evidence: `InputSourceService.cpp:120-131`; audit/openauto-integration.md#F7.
  Status: kept.
- FR-HU-08: Sensor answers driving status `UNRESTRICTED`, night mode from
  `/tmp/night_mode_enabled`, GPS read guarded by `gps_open` success, 250 ms poll.
  Evidence: `SensorService.cpp:37-44,238-260`;
  `patches/openauto-auriga-gps-guard.patch:4-24`; audit/openauto-integration.md#F12.
  Status: kept.
- FR-HU-09: Bluetooth service (dummy device) answers pairing with
  `STATUS_SUCCESS`, PIN `123456`, advertises `BLUETOOTH_PAIRING_UNAVAILABLE`.
  Evidence: `BluetoothService.cpp:68-141`, `DummyBluetoothDevice.cpp:34-37`;
  audit/openauto-integration.md#F13. Status: kept (Q2: keep as-is; investigate
  the first-session reset later, no `WirelessProjectionEnabled` hardware test).
- FR-HU-10: AA identity is hardcoded `Crankshaft-NG` / make `f1x` /
  model `Crankshaft-NG Autoapp` / driver `RIGHT`.
  Evidence: `AndroidAutoEntity.cpp:181-196`; audit/openauto-integration.md#F11.
  Status: kept (rename to `Auriga`; documented outstanding task).
- FR-HU-11: Reconnect after an entity error via `onAndroidAutoQuit ->
  waitForDevice`.
  Evidence: `App.cpp:236-289`; audit/openauto-integration.md#F8. Status: kept
  (quit-and-wait path). The commented-out USB-hub-error retry path is dropped.
- FR-HU-12: Every new AA entity truncates all sinks (`video.h264`,
  `audio-*.wav`, `input.jsonl`) at channel-open time.
  Evidence: `patches/openauto-capture.patch:465,632,863`; audit/openauto-integration.md#F14.
  Status: dropped (Q5: replaced by per-session retention, FR-STR-13).

## STR — stream server + browser client

- FR-STR-01: HTTP server on `127.0.0.1:8080` serves `stream/web` static files
  (`ThreadingHTTPServer`, daemon thread, request logging off).
  Evidence: `stream/auriga_stream.py:387-411`; audit/stream.md#F1. Status: kept.
- FR-STR-02: WebSocket on `127.0.0.1:8081`, no auth; connect gets one JSON
  `hello` `{type,width,height,fps,codec,description}` with base64 avcC from SPS/PPS.
  Evidence: `stream/auriga_stream.py:78-86,168-180,343-356,417`; audit/stream.md#F2.
  Status: kept.
- FR-STR-03: Video tail: read `video.h264` Annex-B, split NALs on 4-byte start
  codes, emit one VCL NAL per frame as `type:u8=1|3 | ts_us:u64 BE | AVCC`.
  Evidence: `stream/auriga_stream.py:32-55,246-299`; audit/stream.md#F3. Status: kept.
- FR-STR-04: Startup seeks to the last type-5 NAL in the last 8 MiB; else offset 0.
  Evidence: `stream/auriga_stream.py:89-113,135-136`; audit/stream.md#F4. Status: kept.
- FR-STR-05: Late clients get the cached GOP (messages since last keyframe)
  inserted into `self.gop` before joining the broadcast set.
  Evidence: `stream/auriga_stream.py:124,285-299,347-356`; audit/stream.md#F5.
  Status: kept (decoded-losing; bug B1 fixed by FR-STR-14 single-viewer design).
- FR-STR-06: Audio tail: skip the 44-byte WAV header, forward PCM as `type 2 |
  ts_us | payload` capped at 7680 bytes; only `audio-media.wav` is streamed.
  Evidence: `stream/auriga_stream.py:25-26,301-341,403-404`; audit/stream.md#F6,F7.
  Status: kept (Q3: media-only contract; guidance/system WAVs are file-only).
- FR-STR-13: Capture files are per-session (timestamped names), rotate before
  4 GiB, and keep a bounded number of sessions. Evidence: Q5 decision;
  audit/openauto-integration.md#F14; audit/stream.md#X4. Status: kept.
- FR-STR-14: Exactly one browser viewer per session; a second client is rejected
  or replaces the first. Evidence: Q4 decision; audit/stream.md#B2/B3. Status:
  kept.
- FR-STR-07: Session truncation (`size < offset`) closes/reopens at 0, re-extracts
  SPS/PPS, clears the GOP, broadcasts `{"type":"reset"}` then `hello`.
  Evidence: `stream/auriga_stream.py:218-238`; audit/stream.md#F8. Status: kept.
- FR-STR-08: Client input `{type:"tap"|"down"|"move"|"up", x, y}` is written as
  `"<cmd> <x> <y>\n"` to the FIFO via a fresh `O_WRONLY|O_NONBLOCK` fd per event.
  Evidence: `stream/auriga_stream.py:357-381`; audit/stream.md#F9. Status: kept.
- FR-STR-09: Browser decodes with WebCodecs `VideoDecoder` (configured from
  avcC), draws to a 1280x720 canvas, and plays audio via WebAudio scheduled by
  message timestamp.
  Evidence: `stream/web/app.js:65-97,130-175,237-253`; audit/stream.md#F10. Status: kept.
- FR-STR-10: Audio is muted by default; first unmute click creates/resumes the
  AudioContext.
  Evidence: `stream/web/app.js:13,237-256`; audit/stream.md#F11. Status: kept.
- FR-STR-11: Gesture semantics: >8 px movement sends `down` at the press point,
  `move`s throttled to 50 ms, `up` at release; otherwise one `tap`.
  Evidence: `stream/web/app.js:192-235`; audit/stream.md#F12. Status: kept.
- FR-STR-12: Client reconnects to the WS every 2 s on close/error and
  reconfigures the decoder on `hello`.
  Evidence: `stream/web/app.js:27-48,65-97`; audit/stream.md#F13. Status: kept.

## RUN — runtime orchestration (scripts)

- FR-RUN-01: `mac-headunit-start.sh` brings up `autoapp` (offscreen capture),
  the stream server, `caffeinate`, then opens Brave at `http://localhost:8080`.
  Evidence: `scripts/mac-headunit-start.sh:68-91`; audit/runtime-orchestration.md#F1.
  Status: kept.
- FR-RUN-02: Start is idempotent per component via `pgrep -f`; skips running
  components instead of failing.
  Evidence: `scripts/mac-headunit-start.sh:31-34,48-51`; audit/runtime-orchestration.md#F3.
  Status: kept.
- FR-RUN-03: Exactly one FIFO `/tmp/auriga-in` is recreated (`rm`+`mkfifo`) with
  a background `sleep 86400 > FIFO` writer so the stdin open does not block.
  Evidence: `openauto-config/run-mac.sh:22-27`; audit/runtime-orchestration.md#F4.
  Status: kept.
- FR-RUN-04: Stop is signal-based: pid-file kill plus `pkill -f` for
  `autoapp`/stream; no graceful shutdown, no `reset` for clients.
  Evidence: `scripts/mac-headunit-stop.sh:6-22`; audit/runtime-orchestration.md#F8.
  Status: kept.
- FR-RUN-05: Pi fallback = start-on-Pi plus SSH tunnel on Mac (`-L 8080 -L 8081`).
  Evidence: `scripts/pi-start.sh`, `scripts/mac-start.sh`;
  audit/runtime-orchestration.md#F9. Status: dropped (Q1: macOS-local is the only
  supported mode; delete Pi scripts and docs).
- FR-RUN-06: Stream server binds `127.0.0.1` only for HTTP and WS.
  Evidence: `stream/auriga_stream.py:395,417`; audit/runtime-orchestration.md#F12.
  Status: kept.

## DGL — dongle hardware (AutoLink A512)

- FR-DGL-01: Dongle enumerates MTP `2717:ff40` and re-enumerates AOA `18d1:2d00`
  after the host AOA v2 switch.
  Evidence: `README.md:154-155`, `logs/*.log` (19 `Version Received`);
  audit/dongle-hardware.md#F1. Status: kept.
- FR-DGL-02: The host rejects `18d1:2d01` (AOA+ADB phone) as a dongle target.
  Evidence: `patches/aasdk-usb-filter.patch:78-88`; audit/dongle-hardware.md#F2.
  Status: kept.
- FR-DGL-03: Dongle reports AA protocol 1.7 (`256.1792`); aasdk minor was edited
  6→7 to match (currently an unpatched tree edit).
  Evidence: `README.md:160`, `aasdk-upstream/include/aasdk/Version.hpp:27`;
  audit/dongle-hardware.md#F4,F5. Status: kept (see Q6 re: promotion into `patches/`).
- FR-DGL-04: `videoInfo` is a 364-byte little-endian struct (magic, width/height
  u32, SPS/PPS, phone BT address, 10-byte head-unit name, 8-byte session tag).
  Evidence: byte inspection of all five snapshots; audit/dongle-hardware.md#F7.
  Status: kept (as a constraint; the "active" galaxy snapshot is invalid — see
  bug B1).
- FR-DGL-05: BT pairing DB (`btapp.db`/`btapp.bk`, 207-byte or 33-byte forms);
  recovery = delete DB + cold replug + re-pair (6-digit numeric comparison).
  Evidence: `RUNBOOK.md:162-182`, `README.md:226-242`; audit/dongle-hardware.md#F8.
  Status: kept.
- FR-DGL-06: CarPlay mode (`05ac:12a8`) is a software-unreachable latch under the
  `2717:ff40` filter.
  Evidence: `README.md:148-163`, `patches/aasdk-usb-filter.patch:55-64`;
  audit/dongle-hardware.md#F10. Status: kept as a documented runbook note (Q8);
  no code path.

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

- FR-BLD-01: A `Release` autoapp builds from the four patches
  (`capture -> macos -> auriga-usb-filter -> auriga-gps-guard`) plus the two
  aasdk edits promoted into `patches/` (`Version.hpp` 6→7,
  `protobuf/CMakeLists.txt` absl include).
  Evidence: `MAC-PORT.md`, `patches/*.patch`; audit/build-and-tooling.md#F1,F3,A1.
  Status: kept (target; bug B1 fixed by adding the missing include to the patch).
- FR-BLD-02: `patches/` is the source of truth for a clean rebuild.
  Evidence: `DEVELOPING.md:32-34`; audit/build-and-tooling.md#D1. Status: kept
  (target; currently false: missing include + two unpatched aasdk edits).
- FR-BLD-03: Boost 1.85 is required (`io_service` removed from Boost ≥ 1.87);
  Homebrew default 1.92 fails. Evidence: `MAC-PORT.md:103-109`;
  audit/build-and-tooling.md#X1. Status: kept.
- FR-BLD-04: CMake 4.4.4 requires `-DCMAKE_POLICY_VERSION_MINIMUM=3.5`.
  Evidence: both `CMakeCache.txt`; audit/build-and-tooling.md#X2. Status: kept.
- FR-BLD-05: `capture/` is a self-contained CMake project with `--out/--duration/
  --no-input`; no Mac build directory, documented as rejected.
  Evidence: `capture/CMakeLists.txt:43-55`; audit/build-and-tooling.md#F11.
  Status: dropped (Q7).
- FR-BLD-06: One script applies every patch and builds aasdk + autoapp from clean
  clones. Evidence: Q10 decision; audit/build-and-tooling.md#I1. Status: kept.
- FR-BLD-07: The aasdk `Version.hpp` 6→7 and `protobuf/CMakeLists.txt` absl edits
  live in `patches/`, not only in the nested working tree. Evidence: Q6 decision;
  audit/build-and-tooling.md#D1. Status: kept.

## Non-functional

- NFR-01: File I/O must not sit in the AA flow-control path (`max_unacked=1` and
  ACK-after-write make disk latency phone-visible). Currently violated.
  Evidence: `VideoMediaSinkService.cpp:117,177-187`, `AudioMediaSinkService.cpp:209-218`;
  audit/seams.md#F5,I5. Status: kept (target), not satisfied.
- NFR-02: Video flush is per access unit; stream video poll is 8 ms — near-real-time
  latency for live mirroring. Evidence: `patches/openauto-capture.patch:889-891`,
  `stream/auriga_stream.py:283`. Status: kept.
- NFR-03: Stream server binds localhost only and has no auth; must never be exposed
  publicly. Evidence: `AGENTS.md:119-121`, `stream/auriga_stream.py:395,417`.
  Status: kept.
- NFR-04: Platform: macOS (Apple Silicon) is the only supported head-unit host;
  the Pi fallback is dropped. Evidence: `baseline.md:7-8`; Q1 decision. Status:
  kept.
- NFR-05: Capture growth is bounded: per-session files rotate before 4 GiB and
  retain a bounded number of sessions. Evidence: `captures-mac/`, `RUNBOOK.md:292`;
  audit/stream.md#X4; Q5 decision. Status: kept (target), not satisfied.
- NFR-06: WAV header uses 32-bit RIFF sizes; wraps at ~4 GiB audio (~6.2 h).
  Evidence: `AurigaAudioOutput.cpp:150,163`; audit/stream.md#X3. Status: dropped
  (rotation before 4 GiB makes the wrap unreachable; absorbed by NFR-05/FR-STR-13).
- NFR-07: Startup readiness is a poll of the capture file or the 8080 listen
  socket, not a fixed `sleep 1`. Evidence: `scripts/mac-headunit-start.sh:69`.
  Status: kept (target), not satisfied.
- NFR-08: One `autoapp`/stream pair owns the dongle and capture dir; enforced by
  a pid/lock check, not only `pgrep` heuristics. Evidence: `AGENTS.md:124`.
  Status: kept (target).

## Constraints from external systems

- CON-DGL-01: USB IDs — dongle MTP `2717:ff40`, dongle AOA `18d1:2d00`, phone
  AOA+ADB `18d1:2d01` (never grab), phone MTP+ADB `04e8:6860`.
  Evidence: `AGENTS.md:59-73`. Unverified as hardware fact beyond observed `ioreg`.
- CON-DGL-02: Dongle BT Classic `AutoLink-A512` `ED:A2:A4:94:4F:B8`; Wi-Fi AP
  `AutoLink-A512` BSSID `e8:5c:b1:b5:c6:41` 5180 MHz WPA2 `12345678`.
  Evidence: `README.md:159`; audit/dongle-hardware.md#X7. Unverified.
- CON-DGL-03: Dongle re-enumerates MTP roughly every 22.0 s while idle (de-facto
  discovery watchdog). Evidence: `openauto-plan.md:74-80`; audit/dongle-hardware.md#X4.
  Unverified (not re-measured after BT DB reset).
- CON-HU-01: Captured AA stream is 1280x720 H.264 Baseline level 3.1, 4-byte
  Annex-B start codes, one slice/frame, IDR every ~1800 frames.
  Evidence: capture + `stream/README.md:93-94`; audit/stream.md#X1. Verified by ffprobe.
- CON-HU-02: aasdk is the TLS client, peer verification off (`SSL_VERIFY_NONE`),
  static headunit cert/key. Evidence: `SSLWrapper.cpp:97-139`, `Cryptor.cpp:61-65`;
  audit/phone-app-design.md#F2,F3. Verified.
- CON-STR-01: WebCodecs requires a secure context; `localhost` qualifies,
  `ws://` from an HTTPS page does not (mixed content).
  Evidence: `stream/web/app.js:29`, `AGENTS.md:119-121`. Verified (vendor doc).
- CON-BLD-01: macOS AirPlay Receiver owns TCP 5000; capture mode binds port 0.
  Evidence: `patches/openauto-macos.patch:17-35`, `App.cpp:41-43`. Verified.

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
