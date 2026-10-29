# Audit: headunit adapter (patched OpenAuto `autoapp` + patched aasdk)

Audited against `.rearch/requirements.md` (HU-01..12, NFR-01..08, CON-HU-01/02,
CON-BLD-01, CON-DGL-02). All seven patches apply in reverse cleanly against the
nested trees (`git apply --check --reverse`, all 7 pass), so the trees and
`patches/` agree today.

## Coverage
| File | Lines | Read fully |
| --- | --- | --- |
| `patches/openauto-capture.patch` | 2080 | yes |
| `patches/openauto-macos.patch` | 79 | yes |
| `patches/openauto-auriga-usb-filter.patch` | 44 | yes |
| `patches/openauto-auriga-gps-guard.patch` | 27 | yes |
| `patches/openauto-auriga-identity.patch` | 31 | yes |
| `patches/aasdk-usb-filter.patch` | 101 | yes |
| `patches/aasdk-version-absl.patch` | 28 | yes |
| `docs/Android Auto head unit.md` | 404 | yes |
| `docs/Build.md` | 293 | yes |
| `openauto/src/autoapp/App.cpp` | 269 | yes |
| `openauto/src/autoapp/Service/ServiceFactory.cpp` | 282 | yes |
| `openauto/src/autoapp/Projection/AurigaSession.cpp` | 285 | yes |
| `openauto/src/autoapp/Projection/AurigaVideoOutput.cpp` | 166 | yes |
| `openauto/src/autoapp/Projection/AurigaAudioOutput.cpp` | 237 | yes |
| `openauto/src/autoapp/Projection/AurigaAudioInput.cpp` | 132 | yes |
| `openauto/src/autoapp/Projection/AurigaInputDevice.cpp` | 236 | yes |
| `openauto/include/.../AurigaWriter.hpp` | 220 | yes |
| `openauto/include/.../AurigaSession.hpp` | 76 | yes |
| `openauto/src/autoapp/autoapp.cpp` | 314 | excerpts (35-90, 225-265) |
| `openauto/src/autoapp/Service/MediaSink/VideoMediaSinkService.cpp` | 267 | excerpts (100-267) |
| `openauto/src/autoapp/Service/MediaSink/AudioMediaSinkService.cpp` | 248 | excerpts (160-249) |
| `openauto/src/autoapp/Service/Sensor/SensorService.cpp` | 296 | excerpts (20-79, 215-284) |
| `openauto/src/autoapp/Service/AndroidAutoEntity.cpp` | 375 | excerpts (170-215) |
| `openauto/src/autoapp/Service/InputSource/InputSourceService.cpp` | 207 | excerpts (80-207) |
| `openauto/src/autoapp/Service/Bluetooth/BluetoothService.cpp` | 169 | excerpts (55-155) |
| `openauto/src/autoapp/Projection/DummyBluetoothDevice.cpp` | 50 | excerpts (25-50) |
| `openauto/src/autoapp/Service/Pinger.cpp` | 78 | excerpts (20-70) |
| `openauto/src/autoapp/Service/AndroidAutoEntityFactory.cpp` | 74 | excerpts (60-75) |
| `aasdk-upstream/src/USB/USBHub.cpp` | 165 | excerpts (30-150) |
| `openauto/src/autoapp/Configuration/Configuration.cpp` | 620 | excerpts (115-135, greps) |
| `scripts/build.sh` | 212 | excerpts (1-80, greps) |
| `stream/lib/session.py` | 214 | excerpts (1-40, greps) |
| `openauto-config/openauto.ini`, `openauto-config/run.sh` | 30 / 45 | yes |

## Functional behavior

FR mapping (kept FRs → code). All twelve HU FRs map to live code; the evidence
line numbers in `requirements.md` are stale for FR-HU-02/03/04/05/06 (they point
at the pre-rewrite patch layout, e.g. `openauto-capture.patch:854-892` is now the
`AurigaAudioOutput` constructor/write helpers, not the video sink).

- F1 (FR-HU-01): AOA switch restricted to `2717:ff40`. `USBHub` gets the pair (`openauto/src/autoapp/autoapp.cpp:243-246`); `handleDevice` returns early for any non-AOAP device that does not match (`aasdk-upstream/src/USB/USBHub.cpp:113-119`), and the all-device enumerator is skipped in capture mode (`openauto/src/autoapp/App.cpp:52-63`). Status: active. Caveat A2 below: an already-AOA device of any vendor (`18d1:2d00`) is still accepted.
- F2 (FR-HU-02): single opt-in env. One cached read (`AurigaSession.cpp:38-59`), `captureModeEnabled()` (`:61-64`). Substitution sites: video `ServiceFactory.cpp:239-246`, audio `:97-114,197,205,231`, input `:177-187`, mic `:257-264`, TCP `App.cpp:39-40,182-184`. Status: active. Note two different predicates are used: `captureSession_ != nullptr` for sinks/input, `captureModeEnabled()` for mic and `App` (`ServiceFactory.cpp:258`).
- F3 (FR-HU-03): Annex-B AU append, flush per AU. `AurigaVideoOutput.cpp:113-142` (`file_.flush()` at `:135`), sink write is a copy only (`:70-79`). Status: active.
- F4 (FR-HU-04): three WAVs, 48000/2/16, 16000/1/16, 16000/1/16 (`ServiceFactory.cpp:197,205,231`), 44-byte header, rewrite every 1 s of audio (`AurigaAudioOutput.cpp:153-176,178-210`). Status: active.
- F5 (FR-HU-05): silent mic, 20 ms `deadline_timer` pacing, `sampleRate/50*channels*bytes` zero buffer (`AurigaAudioInput.cpp:56-93`; 640 B at 16 kHz mono). Status: active.
- F6 (FR-HU-06): stdin line protocol `tap|down|move|up|quit`, JSONL log, AA touch actions (`AurigaInputDevice.cpp:122-231`). Status: active.
- F7 (FR-HU-07): input starts only after a successful `KeyBindingRequest` (`InputSourceService.cpp:102-132`, `start()` at `:122`). Status: active.
- F8 (FR-HU-08): `UNRESTRICTED` driving status, night mode from `/tmp/night_mode_enabled`, 250 ms poll, `gps_read` guarded by `gpsEnabled_` (`SensorService.cpp:35-52,238-270`). Status: active.
- F9 (FR-HU-09): dummy Bluetooth → `car_address=""`, `BLUETOOTH_PAIRING_UNAVAILABLE`, `STATUS_SUCCESS`, `already_paired=false`, PIN `123456` (`BluetoothService.cpp:60-84,120-155`; `DummyBluetoothDevice.cpp:30-42`). Status: active.
- F10 (FR-HU-10): identity is now `Auriga`/`Auriga`/`Auriga` (`AndroidAutoEntity.cpp:181,193-200`, `patches/openauto-auriga-identity.patch`). The requirement still says `Crankshaft-NG` / `f1x` / `RIGHT` "kept (rename to Auriga; outstanding task)" — the rename is **done**; requirement text is stale. Status: active.
- F11 (FR-HU-11): reconnect only via `onAndroidAutoQuit → waitForDevice` (`App.cpp:224-251`); hub-error retry is commented out (`App.cpp:253-265`). Status: active (quit-and-wait), retry dead.
- F12 (FR-HU-12, dropped): every sink still opens with `std::ios::trunc` (`AurigaVideoOutput.cpp:46`, `AurigaAudioOutput.cpp:74`, `AurigaInputDevice.cpp:50`) but into a fresh `session-<id>/`, so nothing truncates a previous session. Status: per-session, as decided.
- F13 (FR-STR-13 at the HU side): rotation at `SEGMENT_LIMIT = 4 GiB - 16 MiB` (`AurigaSession.hpp:40`; `AurigaVideoOutput.cpp:138-141`; `AurigaAudioOutput.cpp:164-168`) and retention `KEEP_SESSIONS = 5` (`AurigaSession.hpp:42`; `AurigaSession.cpp:235-280`). Status: active.
- F14 (FR-STR-07 signal at the HU side): rotation truncates in place and bumps the manifest count (`AurigaVideoOutput.cpp:146-160`, `AurigaAudioOutput.cpp:215-231`, `AurigaSession.cpp:164-178`); the stream's stream-name set (`stream/lib/session.py:27`) matches `AurigaSession.cpp:72`. Status: active.
- F15 (NFR-01): media ACK is sent before the sink is asked to take the buffer (`VideoMediaSinkService.cpp:177-190`, `AudioMediaSinkService.cpp:209-221`); the sink copy is a queue push (`AurigaWriter.hpp:79-115`), one writer thread per sink does all file I/O. **The requirement's "currently violated" is stale: NFR-01 is satisfied by this code.** Status: active, satisfied.
- F16 (NFR-02): per-AU flush (`AurigaVideoOutput.cpp:135`). Status: active.
- F17 (NFR-03): the stream server is localhost-only (other aspect), but the HU still constructs a listener in capture mode: `tcp::endpoint(v4(), 0)` → `0.0.0.0:<ephemeral>` (`App.cpp:39-40`), never accepted (`App.cpp:182-184`). Status: active, a listening socket on all interfaces exists.
- F18 (NFR-05): bounded growth, but the bound is large: 5 sessions × 4 streams × ~4 GiB ≈ 80 GiB worst case, and a rotated segment's bytes are discarded (`AurigaVideoOutput.cpp:146-152`).
- F19 (CON-BLD-01): port 5000 avoided via `captureModeEnabled() ? 0 : 5000` (`App.cpp:39-40`). Status: active.

## External facts and quirks
- X1: `gps_open()` returns 0 on success, so `if (gps_open(...))` is the *failure* branch (`SensorService.cpp:37-43`). Correct today; it reads like an inverted check and a "fix" would reintroduce the crash the gps guard exists to prevent. Source: code + gpsd convention.
- X2: macOS AirPlay Receiver owns TCP 5000, so a non-capture run cannot bind; capture mode binds 0 but still listens on every interface (`App.cpp:39-40`). Source: code + `docs/Build.md:205-213`.
- X3: the AA video channel sends SPS/PPS out of band as `MEDIA_MESSAGE_CODEC_CONFIG`, not in the media stream; the sink re-injects it at each segment head (`VideoMediaSinkService.cpp:193-211`, `AurigaVideoOutput.cpp:81-95,120-131`). Source: code.
- X4: `Video.FPS=2` and `Video.Resolution=2` in `openauto-config/openauto.ini` mean `VIDEO_FPS_30` and `VIDEO_1280x720` (enum values verified in `aasdk-upstream/protobuf/aap_protobuf/service/media/sink/message/{VideoFrameRateType,VideoCodecResolutionType}.proto`). Source: code.
- X5: `USBHub` sleeps a fixed 1 s inside the strand before starting the query chain on a non-AOAP match (`aasdk-upstream/src/USB/USBHub.cpp:139-141`). A cold dongle start pays that second. Source: code.
- X6 [important]: the rig currently running (`pgrep`: pid 29079 `build-openauto-mac/bin/autoapp`, pid 29090 `auriga_stream.py --video captures-mac/video.h264 --audio captures-mac/audio-media.wav`) writes the **flat, pre-session** layout: `captures-mac/{video.h264,audio-*.wav,input.jsonl}` with no `current` symlink, and the log shows `[AurigaVideoOutput] writing .../captures-mac/video.h264`. The 09:37 binary in `build-openauto-mac/bin/` contains the session code (`strings` finds `AurigaSessionManager`) but is not the running one. So the documented per-session contract is not what the live rig produces. Source: process list, `logs/openauto-mac-20261029-074101.log`, `ls captures-mac`.
- X7: `AASDK Error: 10` occurrences exist in the logs (`Native Code: 2`, `4294967197`, `4294967292`), consistent with the doc's "first entity fails" section; the trigger is still unverified. Source: `logs/openauto-mac-*.log`.

## Doc and code inconsistencies
- D1: `docs/Android Auto head unit.md:239` says touch geometry comes from `ServiceFactory.cpp:149-152`; it is `:173-175`. Stale line range.
- D2: `docs/Android Auto head unit.md:243` says the Bluetooth service is registered at `ServiceFactory.cpp:115-125`; it is `:141-150`. Stale line range.
- D3: `docs/Android Auto head unit.md:245` says `Audio.OutputBackendType`, `Input.EnableTouchscreen`, `Input.EnablePlayerControl` are "parsed but not read by any code path; inert". False outside capture mode: `getAudioOutputBackendType()` is read at `ServiceFactory.cpp:106`, `getTouchscreenEnabled()` at `InputDevice.cpp:202,244,259`, `getPlayerControlEnabled()` is used by `InputDevice`. They are inert **only** in capture mode, where the Qt/Rt backends are replaced (`ServiceFactory.cpp:101-113,178-187`).
- D4: `docs/Android Auto head unit.md:268-269` says `display_name` is set once "in the `headunit_info` block"; it is set once at `AndroidAutoEntity.cpp:181`, before `connection_configuration`, outside the `headunit_info` block (`:193-200`).
- D5: `docs/Android Auto head unit.md:400` verifies `captures-mac/video.h264`; the contract is `captures-mac/<session>/video.h264` via `captures-mac/current` (`docs/Android Auto head unit.md:116-126`, `docs/Build.md:274-282`). The line matches the stale live rig (X6), not the code.
- D6: `docs/Android Auto head unit.md:153-154` says `fps` "may be fractional; `29.97` is printed as such". `configuredVideoGeometry()` only produces 30.0 or 60.0 (`ServiceFactory.cpp:71-95`) and `writeManifest` streams a `double` with default formatting (`AurigaSession.cpp:186`) → `"fps":30`. Fractional fps is not implemented.
- D7: `docs/Build.md:236-237` lists the `build-openauto-mac/bin` artifacts as `autoapp` → `autoapp-2026.10.28+git.4cc739b.dirty`; there are now two versioned binaries, and `autoapp` points at `autoapp-2026.10.29+git.4cc739b.dirty`.
- D8: `requirements.md:50-52` (FR-HU-10) describes `Crankshaft-NG` / make `f1x` / model `Crankshaft-NG Autoapp` and calls the rename outstanding; `AndroidAutoEntity.cpp:181,193-200` already says `Auriga`.
- D9: `requirements.md:231-234` (NFR-01) says "Currently violated"; the code now ACKs before the queue copy and keeps file I/O on writer threads (`VideoMediaSinkService.cpp:177-190`, `AurigaWriter.hpp:79-115`). Requirement is stale, and it contradicts `docs/Android Auto head unit.md:309-317`.
- D10: `requirements.md:58-60` (FR-HU-12) is listed as `dropped` yet still describes `patches/openauto-capture.patch:465,632,863` as truncation points; those lines are `AurigaAudioOutput`/`AurigaInputDevice` code, and the behavior is per-session now.
- D11: `docs/Android Auto head unit.md:9-13` pins `openauto/` at `4cc739b8` and `aasdk-upstream/` at `9bf6adf` (`newdev`) — verified true (`git rev-parse`). The "dirty by design" set is exactly the 11 modified + 11 untracked Auriga files; no unpatched tree edits remain (contradicting the old FR-DGL-03 note about an "unpatched tree edit").

## Assumptions to revalidate
- A1: codec config arrives before the first media chunk on the video channel. If not, `AurigaVideoOutput::writeChunk` has already set `segmentStarted_` (`:120-131`) and the SPS/PPS are dropped for that whole segment: the segment head has no SPS/PPS, `stream/lib/h264.py` has nothing to build avcC from, the browser cannot configure `VideoDecoder`. Baked into `AurigaVideoOutput.cpp:120-131`; nothing retries or warns.
- A2: "any AOA device that is not `18d1:2d01` is the dongle". `USBHub.cpp:113-125` only excludes `cAOAPWithAdbId`; a phone left in AOA with ADB off (`18d1:2d00`) would be opened and handed to `AOAPDevice::create` (`App.cpp:148`). Breaks if a phone is ever left in that state (the doc's own recovery step says exactly that is possible).
- A3: one channel open per AA entity. B3 below depends on it.
- A4: the phone keeps sending 4-byte-start-code Annex-B and one slice per frame (CON-HU-01). The HU copies bytes verbatim (`AurigaWriter.hpp:85-110`); a phone/profile change silently changes the file format that `stream/lib/h264.py` parses.
- A5: the writer threads keep up with ~100 kB/s video. If not, chunks are dropped silently (B8) and the log is the only trace.
- A6: `AURIGA_CAPTURE_DIR` is on a filesystem with rename-over-symlink and >4 GiB files (APFS: yes). `writeManifest`/`publishCurrent` depend on atomic rename (`AurigaSession.cpp:207,228`).
- A7: `captureModeEnabled()` is read once per process (`AurigaSession.cpp:40`). Changing the env of a live process does nothing; every component must see the same value, which is why `App` and `ServiceFactory` can branch independently.

## Bugs
- B1 [medium]: video codec config can be lost for a whole segment. `AurigaVideoOutput::writeChunk` writes the cached SPS/PPS only when `!segmentStarted_` (`AurigaVideoOutput.cpp:120-131`); a `setCodecConfig` that arrives after the first media chunk only affects the *next* rotation. Scenario: phone sends the first frame before `MEDIA_MESSAGE_CODEC_CONFIG` → `video.h264` head has no SPS/PPS → no avcC for the browser until a 4 GiB rotation.
- B2 [medium]: `AurigaInputDevice::start` after `quit` calls `std::terminate`. `quit` sets `running_ = false` (`AurigaInputDevice.cpp:190-192`) and the reader loop exits, but `stop()` is not called and `reader_` stays joinable; a second `start()` passes `running_.exchange(true)` (`:44`) and assigns a new `std::thread` over a joinable one (`:58`) → `std::terminate`. The same path re-runs `log_.open()` on an open `ofstream` (`:50`), which sets `failbit` and silently stops JSONL logging. Scenario: a second `KeyBindingRequest` inside one AA entity after a `quit`.
- B3 [medium]: a sink reopened after `stop()` accepts data and writes nothing. `AurigaWriter::start()` returns early once `stopping_` is set (`AurigaWriter.hpp:64-74,119-127`), but `AurigaVideoOutput::open()`/`AurigaAudioOutput::open()` still return `true` (`:39-62` / `:67-92`), so the channel is reported `STATUS_SUCCESS` (`VideoMediaSinkService.cpp:134-136`) while the file stays at 0/44 bytes and the queue grows to 64 MiB. Scenario: media channel close→open inside one entity.
- B4 [low]: `AurigaInputDevice::sendTouch` reads `eventHandler_` with no lock (`:200-213`) while `stop()` writes it under `mutex_` (`:70-71`); `logEvent` takes the mutex but `sendTouch` does not. Data race on the reader thread; UB, benign in practice.
- B5 [low]: `mintSessionId` caps the suffix search at 99 (`AurigaSession.cpp:92-100`) and returns a colliding id when 99 ids exist for the same second, which then shares (and truncates) an existing session directory.
- B6 [low]: `AurigaWriter::run` busy-spins when `sink_` is empty (`AurigaWriter.hpp:170-173`): `continue` without waiting, so a null sink would burn a core. Unreachable today (all sinks pass a lambda).
- B7 [low]: `AurigaInputDevice::pending_` is only trimmed on `\n` (`:144-152`); a writer that never sends a newline grows it without bound.
- B8 [medium]: dropped media is invisible downstream. Queue overflow drops the oldest chunk and only logs the 1st and every 100th (`AurigaWriter.hpp:169-200,203-212`), but the manifest and the file get no marker, so `video.h264` silently loses NALs mid-stream (decoder resync only at the next IDR, ~60 s). The ACK was already sent (`VideoMediaSinkService.cpp:177-190`), so the phone cannot react either.
- B9 [low]: the WAV header rewrite is not atomic for readers. `writeHeader` seeks to 0 and writes 44 bytes in place on the file the stream server is tailing (`AurigaAudioOutput.cpp:178-210`), so a concurrent read of the first sector can see a half-updated `RIFF`/`data` size.

## Dead code, leftovers, stale comments
- L1: `App.cpp:253-265`, commented-out `onUSBHubError → waitForDevice()` retry (intentional per FR-HU-11, but the code stays).
- L2: `App.cpp:72-74` and `App.cpp:88-89`, commented-out close/return and `usbHub_->cancel()/enumerator_->cancel()` blocks inside `start()`.
- L3: `ServiceFactory.cpp:143-149`, `// TODO: What is WiFi Projection Service?` plus the commented `createWifiProjectionService` call; `createWifiProjectionService` itself (`:274-277`) and `WifiProjectionService` are still compiled and never constructed.
- L4: `ServiceFactory.cpp:212-225`, commented-out telephony sink block, with `TelephonyAudioChannel.hpp` still included (`:29,37`).
- L5: `VideoMediaSinkService.cpp:234-245` writes `/tmp/entityexit` on `VIDEO_FOCUS_NATIVE`; only `MainWindow.cpp:1754-1759` reads and deletes it. Crankshaft UI hook, unrelated to Auriga, and the only place the video path touches the UI.
- L6: Crankshaft leftovers in the UI: `system("/usr/local/bin/crankshaft ...")` and `/boot/crankshaft/...` reads (`SettingsWindow.cpp:87-101,143-151,847,862,923-927`, `UpdateDialog.cpp:70-112`). Dead on macOS; the settings window is unreachable in capture mode only because the platform is offscreen.
- L7: stale capture artifacts of the prefetch layout in `captures-mac/` (`video.h264`, `audio-{media,guidance,system}.wav`, `input.jsonl`, no `session-*`, no `current`), produced by the still-running old binary (X6).
- L8: `AurigaVideoOutput::init()` returns `true` unconditionally (`:64-67`); `AurigaAudioOutput::start()`/`suspend()` are empty (`:114-116,133-135`), so `MEDIA_CHANNEL_STOP` does not stop capture — the sink keeps accepting until the entity dies.
- L9: `IAudioOutput::setCodecConfig` / `IVideoOutput::setCodecConfig` are default no-op virtuals added only for the capture sinks (`openauto-capture.patch:599-621`); every other backend inherits a no-op.
- L10: `AurigaVideoOutput` carries `#include <mutex>` + `codecConfigMutex_` for a buffer written on the strand and read on the writer thread, while `accepting_` — also cross-thread — is a plain `bool` (`AurigaVideoOutput.hpp:37-46`). Inconsistent, and `accepting_` is the unsound one.

## Improvement areas
- I1: `configuredVideoGeometry()` is computed twice per entity (`ServiceFactory.cpp:131` and `:173`); the second call can disagree with the geometry already published in the manifest if the configuration is reloaded mid-run. Store it once on the factory.
- I2: two capture-mode predicates in one module: `captureSession_ != nullptr` (sinks, input) vs `captureModeEnabled()` (mic, `App`). One predicate removes the possibility that they ever disagree.
- I3: 44 lines of WAV-specific code are duplicated between the video and audio sinks (`rotate()`, writer wiring, stop ordering). One base sink with a `SegmentFile` policy would drop the duplication that B3 exists in.
- I4: each of the four sinks owns a writer thread and its own 64 MiB cap (`AurigaWriter.hpp:44-45`), so worst case is 4 threads and 256 MiB of RAM for a 100 kB/s video + 3 low-rate audio channels. One writer with per-stream queues removes the threads, not the caps.
- I5: rotation throws away up to 4 GiB per stream (`AurigaVideoOutput.cpp:146-152`). New segment file names (documented FR-STR-13 target) would keep the data and remove the stream server's `size < offset` heuristic.
- I6: skip constructing the acceptor in capture mode (`App.cpp:39-40`) instead of binding `0.0.0.0:0`; or bind `127.0.0.1`. Removes an unused listening socket from the NFR-03 surface.
- I7: the codec-config path should either block the first media write until config is known or write config at the *current* file offset when it arrives late (B1); a one-line "config not seen yet" log would make it diagnosable.
- I8: `AurigaInputDevice` has no restart story (B2) and no lock discipline for `eventHandler_` (B4). Either make the reader a one-shot that `stop()`s before allowing a new `start()`, or keep the reader alive across `quit`.
- I9: no automated test covers the HU contract (`tests/` is Python only): the manifest schema, `current` publication, `SEGMENT_LIMIT` arithmetic and the rotation signal are assertions that only runtime exercises.
- I10: `AurigaWriter` could `fsync` on rotation only; per-chunk `flush()` (`AurigaVideoOutput.cpp:135`) is the right latency trade-off today but costs a syscall per frame.

## Interfaces
- Exposes: `AURIGA_CAPTURE_DIR` (the single capture-mode switch, `AurigaSession.cpp:38-64`); the on-disk contract `capture-dir/current -> session-<id>/` containing `video.h264`, `audio-{media,guidance,system}.wav`, `input.jsonl`, `manifest.json` with `{session,width,height,fps,video,audio-media,audio-guidance,audio-system}` segment counts (`AurigaSession.cpp:182-211`); rotation signalled only by the manifest count and in-place truncation; retention of 5 sessions; `AURIGA_INPUT_FIFO` line protocol `tap|down|move|up X Y`, `quit`, coordinates in the configured video geometry (`AurigaInputDevice.cpp:156-198`); AA identity `Auriga` ×5 + `DRIVER_POSITION_RIGHT` + ping 1000/3000/5 (`AndroidAutoEntity.cpp:181-200`); the AA protocol minor `7` (`aasdk-version-absl.patch`); `USBHub` constructor with optional VID/PID (`aasdk-usb-filter.patch`).
- Consumes: `openauto-config/openauto.ini` resolved from the CWD via `Configuration` (`Video.Resolution`, `Video.FPS`, `AudioChannel.*`, `Bluetooth.*`; `openauto-config/run.sh` cds there); stdin/FIFO; the dongle over libusb (`2717:ff40` → AOA `18d1:2d00`); the AA protocol over USB (never TCP in capture mode); GPSD on `127.0.0.1:2947` (optional); `/tmp/night_mode_enabled`; the stream server reads the files, the manifest and `current` (`stream/lib/session.py:27,104-145`).
- Threading: Qt main thread (`qApplication.exec()`), 4 `io_service.run()` threads and 4 libusb event threads (`autoapp.cpp:44-70`); one `boost::asio::strand` per service carrying channel receive, the queue copy, the ACK and `stop()`; 1 writer thread per sink (4 total) draining a bounded queue; 1 stdin reader thread; `deadline_timer` callbacks (not threads) for the mic and sensor polls. `AurigaSessionManager::noteRotation` runs on a writer thread and takes the session mutex; the entity-creation path mints/publishes on the io_service thread.

## Open questions for the user
- Q1: the rig runs an older `autoapp` and `auriga_stream.py` (X6). Should the new architecture be specified against the tree (per-session) and the runtime simply restarted, or does something depend on the flat layout?
- Q2: is a phone ever expected to sit in AOA without ADB (`18d1:2d00`, A2)? If yes, the USB filter needs an extra discriminator (serial/descriptor) before FR-DGL-02 holds.
- Q3: should a dropped chunk invalidate the current segment (cut a new file) instead of silently corrupting it (B8)?
- Q4: is a media channel ever reopened inside one AA entity (B3), and does anything call `AurigaAudioOutput::suspend()` expecting capture to pause?
