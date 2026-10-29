# Audit: openauto-integration

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| README.md | 389 | yes |
| DEVELOPING.md | 149 | yes |
| MAC-PORT.md | 329 | yes |
| NEXT-SESSION.md | 89 | yes |
| RUNBOOK.md | 306 | yes |
| openauto-plan.md | 477 | yes |
| openauto-config/openauto-logs.ini | 17 | yes |
| openauto-config/openauto.ini | 29 | yes |
| openauto-config/run-mac.sh | 36 | yes |
| openauto-config/run.sh | 32 | yes |
| patches/aasdk-usb-filter.patch | 101 | yes |
| patches/openauto-auriga-gps-guard.patch | 27 | yes |
| patches/openauto-auriga-usb-filter.patch | 42 | yes |
| patches/openauto-capture.patch | 1101 | yes (3 chunks) |
| patches/openauto-macos.patch | 89 | yes |
| logs/run-baseline-114525.filtered.log | 120 | yes |

Verification reads outside the list (to check doc claims against code): `openauto/` working tree (`src/autoapp/App.cpp`, `ServiceFactory.cpp`, `AndroidAutoEntity.cpp`, `BluetoothService.cpp`, `InputSourceService.cpp`, `SensorService.cpp`, `autoapp.cpp`, `Configuration.cpp`, `DummyBluetoothDevice.cpp`, `CMakeLists.txt`), `aasdk-upstream/` (`USBHub.cpp/.hpp`, `Version.hpp`, `ErrorCode.hpp`, `protobuf/*.proto`), `scripts/mac-headunit-start.sh`, `scripts/mac-headunit-stop.sh`, `scripts/pi-start.sh`, `stream/auriga_stream.py`, `.gitignore`, `logs/openauto-mac-20261028-193226.log`, `logs/openauto-mac-20261029-074101.log`, `captures-mac/*` byte headers.

## Functional behavior
- F1: AOA switch is restricted to vendor/product `0x2717/0xFF40`; other devices are never sent the AOA query chain. Evidence: `patches/aasdk-usb-filter.patch:55-64` (`isAccessoryModeSource`), `:69-88` (early return), `patches/openauto-auriga-usb-filter.patch:30-39`, applied at `openauto/src/autoapp/autoapp.cpp:245-246`. Status: active.
- F2: Capture mode is a single opt-in switch, env `AURIGA_CAPTURE_DIR`; it substitutes the video/audio/mic/input backends and creates the dir. Evidence: `openauto/src/autoapp/Service/ServiceFactory.cpp:64-97`, `:165-167`, `:227-229`, `:246-248`; `patches/openauto-capture.patch:960-1000`. Status: active.
- F3: Video sink writes raw Annex-B H.264 access units to `$AURIGA_CAPTURE_DIR/video.h264` and reports config resolution/FPS. Evidence: `patches/openauto-capture.patch:854-892`; file starts `00 00 00 01 67 42 80 1f` (SPS, Baseline 3.1) in `captures-mac/video.h264`. Status: active.
- F4: Audio sinks write one WAV per channel: media 48000/2ch/16, guidance 16000/1ch/16, system 16000/1ch/16; header rewritten every ≥1 s of data. Evidence: `patches/openauto-capture.patch:440-572`; `ServiceFactory.cpp:184,192,218`; `logs/openauto-mac-20261029-074101.log:151,157,161`. Status: active.
- F5: Silent microphone source: 20 ms paced zero buffers, `sampleRate/50 * ch * bytes/sample`. Evidence: `patches/openauto-capture.patch:328-350`, buffer `sampleRate_/50*ch*(bits/8)` at `:346`. Status: active.
- F6: Touch input comes from stdin as line commands `tap|down|move|up X Y` plus `quit`; each command is appended to `input.jsonl` and converted to AA `ACTION_DOWN/UP/MOVED`. Evidence: `patches/openauto-capture.patch:704-796`, JSONL at `:810-812`. Status: active.
- F7: Input device starts only when the phone sends `KeyBindingRequest`; before that, touches are ignored. Evidence: `openauto/src/autoapp/Service/InputSource/InputSourceService.cpp:120-131`, `patches/openauto-capture.patch:785-789`. Status: active.
- F8: Reconnect after an entity error works through `onAndroidAutoQuit -> waitForDevice`; `onUSBHubError` has no retry (the retry block is commented out). Evidence: `openauto/src/autoapp/App.cpp:236-252`, `:277-289`. Status: active (retry path), dead (hub-error path).
- F9: Capture mode skips `enumerateDevices()` (no AOA probe of every USB device) and skips `startServerSocket()`. Evidence: `openauto/src/autoapp/App.cpp:57-66`, `:185-188`, `patches/openauto-auriga-usb-filter.patch:8-24`, `patches/openauto-macos.patch:37-45`. Status: active.
- F10: Advertised service set: video sink, media/guidance/system audio sinks, microphone source, sensor source, input source, Bluetooth (only when `WirelessProjectionEnabled`); WPP and telephony audio are not advertised. Evidence: `ServiceFactory.cpp:108-128`, `:199-213` (telephony block commented), `:124` (WPP commented). Status: active.
- F11: AA identity is hardcoded: `display_name = "Crankshaft-NG"` (set twice), `head_unit_make "f1x"`, `model "Crankshaft-NG Autoapp"`, `driver_position RIGHT`. Evidence: `openauto/src/autoapp/Service/AndroidAutoEntity.cpp:181-196`. Status: active.
- F12: Sensor polling every 250 ms; night mode from `/tmp/night_mode_enabled`; GPS read only when `gps_open("127.0.0.1","2947")` succeeded. Evidence: `openauto/src/autoapp/Service/Sensor/SensorService.cpp:37-44`, `:238-260`; `patches/openauto-auriga-gps-guard.patch:4-24`. Status: active.
- F13: Bluetooth service answers pairing with `STATUS_SUCCESS`, `already_paired=false`, auth data `"123456"` PIN, and advertises `car_address=""` + `BLUETOOTH_PAIRING_UNAVAILABLE` when the device is a `DummyBluetoothDevice`. Evidence: `openauto/src/autoapp/Service/Bluetooth/BluetoothService.cpp:68-83`, `:117-141`; `openauto/src/autoapp/Projection/DummyBluetoothDevice.cpp:34-37`. Status: active.
- F14: Every new AA entity truncates all four sinks (`video.h264`, `audio-*.wav`, `input.jsonl`) at channel-open time. Evidence: `patches/openauto-capture.patch:465`, `:632`, `:863`; observed three sessions in one run, `logs/openauto-mac-20261029-074101.log:151,307` and `:168,324`. Status: active.

## External facts and quirks
- X1: First AA entity after a start fails with `AASDK Error: 10` (`USB_TRANSFER`), native 1/2, **before** the version request; OpenAuto reconnects and the next entity projects. Symptom: one wasted session per start, plus capture truncation. Evidence: `logs/openauto-mac-20261029-074101.log:27-65,81-110`; `aasdk-upstream/include/aasdk/Error/ErrorCode.hpp:37`. Source: capture.
- X2: `Devices enumeration failed: AASDK Error: 30` is `OPERATION_ABORTED` and is expected — the active entity cancels the enumerator. It only appears in pre-filter builds (`logs/openauto-mac-20261028-193226.log:51`). Source: code (`ErrorCode.hpp:58`) + capture.
- X3: With no `gpsd`, `SensorService` logs `can't connect to GPSD` and never calls `gps_read`; the pre-guard crash was `gps_shm_read` on an unopened context. Evidence: `SensorService.cpp:37-44`; `logs/openauto-mac-20261029-074101.log:51`. Source: code.
- X4: The offscreen Qt platform reports an 800x600 primary screen; in non-capture mode the Qt `InputDevice` derives touchscreen geometry from that screen, while capture mode uses config resolution (1280x720). Evidence: `logs/run-baseline-114525.filtered.log:2-7`; `autoapp.cpp:104-128`; `ServiceFactory.cpp:147-170`. Source: capture.
- X5: On the Pi, RtAudio selects the PulseAudio backend; with no PulseAudio daemon all three audio opens fail (`pa_context_connect() failed`). Evidence: `logs/run-baseline-114525.filtered.log:37,97-113`. Source: capture. Irrelevant in capture mode (file sinks).
- X6: macOS AirPlay Receiver owns TCP 5000, so `App`'s acceptor construction would fail in a non-capture build; capture mode binds port 0 instead. Evidence: `patches/openauto-macos.patch:17-35`; `openauto/src/autoapp/App.cpp:41-43`. Source: code + vendor behaviour.
- X7: WAV header is only accurate to the last 1 s boundary. Measured mid-run: header data size 379,256,832 vs actual 379,371,520 (Δ 114,688 bytes); `ffprobe` reports 1975.296 s. Evidence: `patches/openauto-capture.patch:496-501`, `captures-mac/audio-media.wav`. Source: measurement.
- X8: Every start emits 9 pairs of `unable to open cs param file (/boot/crankshaft/crankshaft_env.sh)` warnings from Crankshaft config scraping. Evidence: `logs/run-baseline-114525.filtered.log:8-21`, `logs/openauto-mac-20261028-193226.log:12-26`. Source: capture.
- X9: AASDK writes its own colored log lines interleaved with the OpenAuto sink, with a blank line, into the same stream. Evidence: `logs/run-baseline-114525.filtered.log:95-98`. Source: capture.
- X10: `aasdk` hotplug registration still matches any device (`LIBUSB_HOTPLUG_MATCH_ANY`) and filters only in `handleDevice` after reading the descriptor; a non-AOAP source match costs a hard 1 s strand sleep before the AOA query chain. Evidence: `aasdk-upstream/src/USB/USBHub.cpp:55-60`, `:139-142`. Source: code.

## Doc and code inconsistencies
- D1: `README.md:84-87`, `MAC-PORT.md:61`, `RUNBOOK.md:281-284` say the first-session reset happens "on the dongle's AA Bluetooth pairing request". `logs/openauto-mac-20261029-074101.log:27-65` shows the first entity dying with Error 10 / native 1 immediately after `start()` and before `Version Received`, i.e. before any BT pairing request can occur. The BT-pairing attribution is unverified.
- D2: `openauto-plan.md:132-133,476` attribute the "unavailable" BT advertisement to `Bluetooth.AdapterType=NONE`. The selector is an empty `Bluetooth.AdapterAddress` (`ServiceFactory.cpp:143-151`); `AdapterType` is never read outside the GUI.
- D3: `README.md:57-61` and `MAC-PORT.md:189-196` require four OpenAuto patches; `MAC-PORT.md:22-24` (Status) still says the macOS build is "capture + macos" only.
- D4: `DEVELOPING.md:32-34` "patches/ is the source of truth… a clean rebuild applies the patches" is false: `patches/openauto-capture.patch:590-600` omits `#include <f1x/openauto/autoapp/Projection/IInputDeviceEventHandler.hpp>` present at `openauto/src/autoapp/Projection/AurigaInputDevice.cpp:18`; and the aasdk `Version.hpp` 1.6→1.7 and `protobuf/CMakeLists.txt` absl edit exist only as dirty tree edits plus prose in `MAC-PORT.md:131-146`.
- D5: `DEVELOPING.md:78-81` verify commands (`git -C openauto apply --check --reverse patches/...`) fail as written: the relative patch path resolves inside `openauto/` (verified: "can't open patch"). Needs an absolute path or `-C .` on the outer repo.
- D6: `openauto-plan.md:215-217` claims "2,212 of 2,332 lines are sensorPolling()" and cites `logs/run-baseline-114525.filtered.log`; the committed file has 120 lines, zero sensor lines, and exactly one timestamp (`:95`, 11:45:48) while `openauto-plan.md:186` describes a 5-minute run. The artifact covers ~23 s.
- D7: `RUNBOOK.md:266` says the macOS patch "disables OpenAuto's TCP-5000 listener"; `MAC-PORT.md:77-78` says it "binds an ephemeral port and does not accept TCP clients". Code binds port 0 (still a listening socket on all interfaces) and skips `async_accept` (`App.cpp:41-43,185-188`). USB-only is behaviourally true, socket-free is not.
- D8: `openauto-plan.md:244-245` says the WAV writer has "finalization on stop"; `mac-headunit-stop.sh:10,21` sends SIGTERM to a Qt app with no signal handler, so destructors (`AurigaAudioOutput::stop` → `updateHeader`) never run. X7 shows the practical effect.
- D9: `README.md:88`, `RUNBOOK.md:285`, `DEVELOPING.md:145` list only video/audio as truncating; `input.jsonl` truncates too, per session (`patches/openauto-capture.patch:632`).
- D10: `openauto-config/run.sh` is the Pi launcher in the repo, but `scripts/pi-start.sh:6,8,23` requires `~/auriga/openauto-run/run.sh` and `openauto.ini` there. Nothing in the repo creates that directory; `RUNBOOK.md:120` documents the Pi path without a copy step.

## Assumptions to revalidate
- A1: A fresh clone + `patches/` + the two documented manual aasdk edits reproduces the working binary. Baked into `DEVELOPING.md:61-81`. False today (D4) — a clean rebuild fails at `AurigaInputDevice.cpp`.
- A2: The dongle always enumerates as `2717:ff40` before AOA. Baked into `aasdk-upstream/src/USB/USBHub.cpp:113-127` and `autoapp.cpp:245-246`. If the dongle is in CarPlay mode (`05ac:12a8`) or already AOA `18d1:2d00`, the filter means no AOA attempt is ever made and `autoapp` sits at `Waiting for device...` forever (`App.cpp:279-289`).
- A3: Touch coordinate space equals the configured video resolution. Baked into `ServiceFactory.cpp:147-170` (geometry from `openauto.ini`, not from the actual decoded stream). If the phone negotiates a different resolution, every tap lands at the wrong place and nothing detects it.
- A4: AA delivers whole Annex-B access units per `write()`. Baked into `patches/openauto-capture.patch:879-892` and the stream's start-code splitter (`stream/auriga_stream.py:33`). If aasdk hands over a partial AU, `video.h264` gets a split frame and the stream emits a corrupt one — no frame boundary marker exists in the file format.
- A5: "Phone stays `04e8:6860`" relies on the descriptor filter only. Any device that enumerates as `18d1:2d00` (e.g. a phone already AOA-switched by another host) is grabbed as the head-unit target (`USBHub.cpp:107-112`).
- A6: Truncation is detected by the stream server via file-size shrink (`stream/auriga_stream.py:218-222`). If a new session regrows past the previous offset within one 0.2 s poll, the `reset` is missed and clients keep decoding the old GOP.
- A7: `gpsEnabled_` implies a valid `gpsData_` for the process lifetime (`SensorService.cpp:238-249`). If `gpsd` dies after `gps_open`, `gps_read` still runs against a stale shm handle — the guard does not cover that.

## Bugs
- B1 [high]: `patches/openauto-capture.patch` omits `#include <f1x/openauto/autoapp/Projection/IInputDeviceEventHandler.hpp>` in `AurigaInputDevice.cpp`, which calls `eventHandler_->onTouchEvent(...)`. `patches/openauto-capture.patch:590-600` vs `openauto/src/autoapp/Projection/AurigaInputDevice.cpp:18`; `git apply --check --reverse` fails on exactly that file. Scenario: fresh clone → apply the four documented patches → compile error (incomplete type) — the documented rebuild path does not build.
- B2 [medium]: Capture sinks truncate at every session, so the routine first-session reset wipes the capture that would otherwise be the useful one. `patches/openauto-capture.patch:863`; observed wiping at `logs/openauto-mac-20261029-074101.log:168,232,324`. Scenario: start → session 1 fails → session 2 projects → session 3 (any later error) opens with `trunc` and destroys session 2's video mid-run.
- B3 [medium]: `input.jsonl` (and the three media files) are reopened with `trunc` per entity, so a mid-run reconnect discards already logged touches. `patches/openauto-capture.patch:632`; `logs/openauto-mac-20261029-074101.log:172,330`. Scenario: tap during session 2 → session 3 starts → JSONL 0 bytes.
- B4 [medium]: SIGTERM from the stop script kills `autoapp` without finalizing the WAV writers; the RIFF/data sizes stay at the last 1 s boundary. `scripts/mac-headunit-stop.sh:10,21`, `patches/openauto-capture.patch:508-519`. Scenario: stop mid-session → player sees a duration up to 1 s short; `.wav` header is never repaired.
- B5 [medium]: `AURIGA_INPUT_FIFO` is honored by `openauto-config/run-mac.sh:22` and `run.sh:17`, but hardcoded to `/tmp/auriga-in` in `scripts/mac-headunit-start.sh:61` and `scripts/pi-start.sh` (stream args). Scenario: `AURIGA_INPUT_FIFO=/tmp/x` exported → `autoapp` reads `/tmp/x`, the stream writes `/tmp/auriga-in`; every tap is silently lost and the stream write blocks with no reader.
- B6 [medium]: A drag whose browser client disappears before `up` leaves the AA pointer pressed, because nothing synthesizes `ACTION_UP` on disconnect or on session stop. `patches/openauto-capture.patch:757-771`; no release in `stop()` (`:643-660`). Scenario: start a drag, close the tab → AA keeps the finger down.
- B7 [low]: `AurigaInputDevice::eventHandler_` is written under `mutex_` in `stop()` but read without the lock in `sendTouch()`. `patches/openauto-capture.patch:652-653` vs `:785-796`. Scenario: stop during a command → data race on a raw pointer.
- B8 [low]: `readerLoop()` breaks on stdin EOF with `running_` still `true` (`:721-724`); a later `start()` on the same object returns early at `:626-629`, leaving input silently dead.
- B9 [low]: `quit` stops only the reader thread (`:772-775`) and does not exit `autoapp`; if `start()` is then called again on the same object the assignment `reader_ = std::thread(...)` (`:640`) is on a still-joinable thread → `std::terminate`.
- B10 [low]: `tap` blocks the reader thread for 80 ms (`:754`) while `down/move/up` events queue behind it; a fast drag right after a tap gets stale coordinates.
- B11 [low]: `pause`/resume and `suspend` are no-ops for the file sinks (`:504-523`), so AA-side audio suspend does not stop or mark silence in the WAV; timeline and wall clock diverge.
- B12 [low]: WAV sizes are `uint32` (`:544-558`); media at 192,000 B/s exceeds 4 GiB after ~6.2 h, after which the header is corrupt while the file keeps growing.
- B13 [low]: `set_display_name("Crankshaft-NG")` is called twice in the same message (`AndroidAutoEntity.cpp:182,194`).
- B14 [low]: In capture mode the acceptor is still constructed and bound to `0.0.0.0:<ephemeral>`, i.e. a listening socket on all interfaces for the whole run, contradicting "USB-only". `openauto/src/autoapp/App.cpp:41-43`.

## Dead code, leftovers, stale comments
- L1: Crankshaft GUI/OS hooks in `main()`: `touch /tmp/shutdown`, `touch /tmp/reboot`, `/usr/local/bin/autoapp_helper usbreset`, nine `/opt/crankshaft/cameracontrol.py` and two `/opt/crankshaft/service_daynight.sh` calls. `openauto/src/autoapp/autoapp.cpp:161-231`.
- L2: Full Qt UI stack still constructed for a headless build: `MainWindow`, `SettingsWindow`, `WarningDialog`, `UpdateDialog`, `ConnectDialog` (`autoapp.cpp:134-159`), plus `QScreen` geometry probing whose result only affects the unused Qt input path (`:104-128`).
- L3: `ConnectDialog`/TCP client path (`autoapp.cpp:253-255`, `App::start(socket)`) — WPP is disabled and capture mode never accepts TCP.
- L4: `App::onUSBHubError` retry logic commented out (`App.cpp:277-289`); `//acceptor_.close();` (`App.cpp:231`); `//usbHub_->cancel(); //connectedAccessoriesEnumerator_->cancel();` (`App.cpp:98-99`).
- L5: `ServiceFactory::createWifiProjectionService` exists but is only referenced by a comment (`ServiceFactory.cpp:124,262-266`).
- L6: Broken indentation left inside the `#else` branch of the GPS guard (`SensorService.cpp:246-249`) after `patches/openauto-auriga-gps-guard.patch:18-22`.
- L7: `AurigaAudioOutput::start()` / `suspend()` and `AurigaAudioInput::open()` are empty stubs (`patches/openauto-capture.patch:291-294,452-456,469-472`).
- L8: Config keys written to `openauto-config/openauto.ini` that capture mode ignores: `[Audio] OutputBackendType` (`:14`), `[Input] EnableTouchscreen`, `EnablePlayerControl` (`:28-29`), `[AudioChannel] SystemEnabled` (`:19`, always on per `ServiceFactory.cpp:214-218`), `[Bluetooth] AdapterType` (`:23`).
- L9: `openauto-plan.md:282-333` build-plan steps (Step 0..6 "needs OK") and `:450-464` Mac-build note are superseded by MAC-PORT; still written as instructions.

## Improvement areas
- I1: Make `patches/` actually complete: add the missing include (B1), and ship the aasdk `Version.hpp` and `protobuf/CMakeLists.txt` edits as patch files. Mechanism: today the only record is prose plus dirty trees, so a fresh clone cannot be rebuilt, and `git apply` success is silently unverified.
- I2: Per-session output. Mechanism: `AurigaVideoOutput::open`/`AurigaAudioOutput::open`/`AurigaInputDevice::start` use `std::ios::trunc` on a fixed name; a session id (or `O_APPEND` to a size-capped rollover) removes the mid-run data loss in B2/B3 and the `reset` handling the stream needs.
- I3: Graceful shutdown. Mechanism: install SIGTERM/SIGINT (or accept a `quit` command that calls `App::stop()`), so `stop()` runs on services and the WAV headers finalize; today kill is the only path (B4).
- I4: Reduce video write cost and growth. Mechanism: one `write()` + `flush()` syscall pair per access unit (`patches/openauto-capture.patch:889-891`) with no batching and no size cap — 313 MB after ~35 min here; batch to a fixed buffer with a timed flush, and add a rotation cap.
- I5: Stop advertising config that capture mode ignores. Mechanism: in capture mode `ServiceFactory` bypasses `Audio.OutputBackendType`, `Input.*`, `SystemEnabled`, `AdapterType`; either honor or log them once at startup so the ini stops lying (L8).
- I6: One FIFO contract. Mechanism: derive the FIFO path once from `AURIGA_INPUT_FIFO` and pass it to both `autoapp` stdin and `auriga_stream.py --fifo` (B5).
- I7: Guarantee pointer release. Mechanism: synthesize `ACTION_UP` when the stream client disconnects and at `InputSourceService::stop()` (B6).
- I8: Take the 80 ms tap delay out of the reader thread. Mechanism: post down and up as two timed io_service callbacks so `move`/`up` from the browser are not delayed (B10).
- I9: Do not bind a socket at all in capture mode. Mechanism: `acceptor_` is a member constructed in the initializer list (`App.cpp:41-43`); make the port a runtime decision after the env check, or hold the acceptor as `std::optional` (B14).
- I10: Single source for the AA identity. Mechanism: `display_name`/`head_unit_*` are hardcoded and duplicated (`AndroidAutoEntity.cpp:182,194`); put them in `openauto.ini` so the rename task in `README.md:35-36` is config, not a patch.
- I11: Restore a retry on hub error or document the hard stop. Mechanism: `onUSBHubError` never re-arms `waitForDevice` (`App.cpp:279-289`), so any rejection after startup ends the run silently — the observed "stuck at `Waiting for device...`" state.

## Interfaces
- Exposes (consumed by `stream/` and any other local process):
  - `$AURIGA_CAPTURE_DIR/video.h264` — Annex-B H.264, one access unit appended per AA frame, flushed per AU (`patches/openauto-capture.patch:879-892`).
  - `audio-media.wav` 48000 Hz/2 ch/16-bit, `audio-guidance.wav` 16000/1/16, `audio-system.wav` 16000/1/16; 44-byte header, sizes refreshed ~1 s (`:540-572`). Only `audio-media.wav` is streamed (`stream/auriga_stream.py:404`); guidance/system are captured but unused.
  - `input.jsonl` — JSON lines `{"ts":µs_epoch,"cmd":"tap|down|move|up","x","y"}`, truncated per session (`:810-812`).
  - FIFO `/tmp/auriga-in` (default; overridable via `AURIGA_INPUT_FIFO`) — text lines `tap X Y`, `down X Y`, `move X Y`, `up X Y`, `quit`; coordinates in configured video space (1280x720).
  - PID files `/tmp/auriga-mac-autoapp.pid`, `/tmp/auriga-mac-stream.pid`, `/tmp/auriga-mac-caffeinate.pid`, `/tmp/auriga-fifo-writer.pid`; stream log `logs/stream-mac-*.log`, app log `logs/openauto-mac-*.log`, plus `openauto.log` written into `openauto-config/` by `openauto-logs.ini:13`.
  - Exclusive ownership of USB `2717:ff40` → `18d1:2d00`.
- Consumes:
  - USB dongle via libusb (AOA switch, bulk endpoints); nothing else may claim `2717:ff40` while running.
  - stdin = the FIFO (`openauto-config/run-mac.sh:36`); a writer must stay attached or the open blocks (`:26`).
  - `openauto.ini` and `openauto-logs.ini` resolved relative to CWD, which is why both run scripts `cd` into `openauto-config/` (`openauto/src/autoapp/Configuration/Configuration.cpp:29`, `autoapp.cpp:76-77`).
  - opt-in env `AURIGA_CAPTURE_DIR` (`ServiceFactory.cpp:64-82`); `AURIGA_INPUT_FIFO` (scripts only); `QT_QPA_PLATFORM=offscreen` (`run-mac.sh:35`).
  - Optional `gpsd` on `127.0.0.1:2947` (`SensorService.cpp:37`).
  - Nothing from `stream/`; the data flow to the UI is one-way through files + FIFO.
- Threading:
  - `main()` starts 1 USB-event thread (`libusb_handle_events` loop) + 4 `ioService.run()` threads (`openauto/src/autoapp/autoapp.cpp:47-72`).
  - Each service owns a `boost::asio::strand` on that pool; all channel and sink work runs there; `AurigaAudioOutput`/`AurigaVideoOutput` guard the file with `std::mutex` (`patches/openauto-capture.patch:485,882`).
  - `AurigaInputDevice` adds one raw `std::thread` doing blocking `poll`/`read` on stdin and calling `eventHandler_->onTouchEvent` → `strand_.dispatch` (`:704-736`, `InputSourceService.cpp:196-199`); `stop()` joins it from the strand thread.
  - `AurigaAudioInput` and `SensorService` use `deadline_timer` callbacks on the io_service rather than threads.
  - Qt GUI objects live on the main thread (`qApplication.exec()`), which never returns while running.

## Open questions for the user
- Q1: Capture naming policy for the rearchitecture — timestamped per-session files, or one file with a rotation cap?
- Q2: Is the phone-on-USB (`adb`) requirement meant to hold in non-capture mode too, i.e. must `enumerateDevices()` go away entirely?
- Q3: Should the AA identity (`Crankshaft-NG`, headunit info, driver position RIGHT) become configuration, and what values are wanted?
- Q4: Is the `capture/` minimal app still in scope, or does it get dropped in favour of OpenAuto-only?
- Q5: Stop semantics: is `kill` acceptable (accepting an unterminated WAV header), or must shutdown finalize captures?
