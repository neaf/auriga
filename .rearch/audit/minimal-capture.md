# Audit: minimal-capture

Scope: `capture/` (the minimal headless aasdk app, "auriga_capture") plus the two docs that describe it. Not the working stack: OpenAuto is. `capture/` is reference code kept as the basis for a future headless emulator.

## Coverage
| File | Lines | Read fully |
| --- | --- | --- |
| README.md | 389 | yes |
| NEXT-SESSION.md | 89 | yes |
| capture/CMakeLists.txt | 77 | yes |
| capture/README.md | 90 | yes |
| capture/src/main.cpp | 239 | yes |
| capture/src/HeadUnit.cpp | 337 | yes |
| capture/src/HeadUnit.hpp | 95 | yes |
| capture/src/CaptureService.hpp | 23 | yes |
| capture/src/Usb.cpp | 134 | yes |
| capture/src/Usb.hpp | 35 | yes |
| capture/src/Log.hpp | 36 | yes |
| capture/src/VideoCapture.cpp | 197 | yes |
| capture/src/VideoCapture.hpp | 67 | yes |
| capture/src/AudioCapture.cpp | 235 | yes |
| capture/src/AudioCapture.hpp | 67 | yes |
| capture/src/InputCapture.cpp | 167 | yes |
| capture/src/InputCapture.hpp | 58 | yes |
| capture/src/BluetoothCapture.cpp | 131 | yes |
| capture/src/BluetoothCapture.hpp | 51 | yes |
| capture/src/SensorCapture.cpp | 134 | yes |
| capture/src/SensorCapture.hpp | 46 | yes |
| capture/src/MicrophoneCapture.cpp | 127 | yes |
| capture/src/MicrophoneCapture.hpp | 50 | yes |
| capture/src/WifiProjectionCapture.cpp | 99 | yes |
| capture/src/WifiProjectionCapture.hpp | 47 | yes |
| capture/src/WavWriter.cpp | 73 | yes |
| capture/src/WavWriter.hpp | 32 | yes |

Total 3125 lines. Build tested out-of-tree in the session temp dir (project files untouched).

## Functional behavior
- F1: AOA v2 switch of the dongle only (`2717:ff40` -> `18d1:2d00`), retried up to 240 times at 500 ms. Evidence: `capture/src/Usb.cpp:48-110`, `capture/src/main.cpp:75-97`. Status: active.
- F2: AA version request -> TLS handshake -> auth complete -> service discovery. Evidence: `capture/src/HeadUnit.cpp:34-51`, `HeadUnit.cpp:83-141`, `HeadUnit.cpp:143-191`. Status: active.
- F3: Advertised service set actually registered in `main()`: video sink, 3 audio sinks (media, system, guidance), microphone source, sensor source, input source. Evidence: `capture/src/main.cpp:116-161`. Status: active.
- F4: Bluetooth service, Wi-Fi projection service, telephony audio sink are compiled but never instantiated. Evidence: `capture/src/CMakeLists.txt:50,53` vs `capture/src/main.cpp:114-164` (no `BluetoothCapture`/`WifiProjectionCapture` construction; audio list `main.cpp:120-124` has 3 entries). Status: dead.
- F5: Head-unit identity in service discovery: `display_name` "Auriga Capture", make "Auriga", model "Raspberry Pi 3", `probe_for_support=false`, driver LEFT. Evidence: `capture/src/HeadUnit.cpp:150-171`. Status: active.
- F6: Ping: `PingRequest` sent right after the service-discovery response, then every 2 s; incoming pings answered. Evidence: `capture/src/HeadUnit.cpp:178-186`, `HeadUnit.cpp:286-316`, `HeadUnit.cpp:266-278`. Status: active.
- F7: Ping config advertised to the phone: interval 1000 ms, timeout 3000 ms, tracked 5, high-latency 200 ms. Evidence: `capture/src/HeadUnit.cpp:157-161`. Status: active, inconsistent with F6 (see B3).
- F8: Video sink: H.264 baseline, one config 1280x720@30, density 160, margins 0. Evidence: `capture/src/VideoCapture.cpp:49-73`. Status: active.
- F9: Video output: raw access-unit bytes appended to `<out>/video.h264`, opened with truncate at the setup request. Evidence: `capture/src/VideoCapture.cpp:92-114`, `VideoCapture.cpp:131-142`. Status: active.
- F10: Video focus: `VIDEO_FOCUS_PROJECTED` sent after the setup response resolves and on any focus request. Evidence: `capture/src/VideoCapture.cpp:107-112`, `VideoCapture.cpp:149-171`. Status: active.
- F11: Audio sinks: PCM 48 kHz/16 bit/2 ch, `max_unacked=1`, WAV opened on the start indication, closed on stop. Evidence: `capture/src/AudioCapture.cpp:129-132`, `AudioCapture.cpp:155-193`. Status: active.
- F12: Media ACK after every received buffer, using the session id from the start indication. Evidence: `capture/src/VideoCapture.cpp:180-195`, `capture/src/AudioCapture.cpp:218-233`. Status: active.
- F13: Sensor answers to start requests: driving status `UNRESTRICTED`, night mode false, location = empty batch. One batch per request, no periodic updates. Evidence: `capture/src/SensorCapture.cpp:74-125`. Status: active.
- F14: Microphone advertises PCM 48 kHz/16 bit/1 ch, accepts setup and open, sends no audio, always answers `session_id=0`. Evidence: `capture/src/MicrophoneCapture.cpp:38-112`. Status: active (stub).
- F15: Input source: 1280x720 touchscreen, injected taps logged to JSONL and sent as `InputReport`. Evidence: `capture/src/InputCapture.cpp:48-60`, `InputCapture.cpp:105-165`. Status: active.
- F16: stdin protocol: `tap|down|move|up X Y` and `quit`. Evidence: `capture/src/main.cpp:202-224`. Status: active, but `quit` only stops the reader (B4).
- F17: `--out DIR` (default `captures`), `--duration SECONDS` (0 = forever), `--no-input`. Evidence: `capture/src/main.cpp:34-58`, `main.cpp:177-187`. Status: active.
- F18: Any channel error or `ByeByeRequest` stops the whole io_service; the process exits. No reconnect. Evidence: `capture/src/HeadUnit.cpp:318-335`, `capture/src/main.cpp:166`. Status: active. This is why it "resets every session and does not recover".
- F19: `capture/` builds clean with Boost 1.85 + aasdk-upstream `9bf6adf` + `build-aasdk-mac` when `AASDK_SOURCE`/`AASDK_BUILD` are overridden: `cmake --build` -> `[100%] Built target auriga_capture`. Source: local build test. Status: experimental.

## External facts and quirks
- X1: `boost::asio::io_service` was removed from Boost >= 1.87. Default `find_package(Boost)` here resolves 1.92.0 and the build fails with `no type named 'io_service' in namespace 'boost::asio'` at `aasdk-upstream/include/aasdk/IO/Promise.hpp:249`. `capture/CMakeLists.txt:37` does not pin the version, so `cmake -S capture -B build-capture` picks the wrong Boost. Workaround: `-DBoost_DIR=$(brew --prefix boost@1.85)/lib/cmake/Boost-1.85.0`. Source: build test.
- X2: `capture/CMakeLists.txt:10-11` defaults `AASDK_SOURCE=../aasdk` and `AASDK_BUILD=../build-aasdk`. Neither exists in this tree (`aasdk-upstream/`, `build-aasdk-mac/` do). Configure fails without overrides despite the comment at `CMakeLists.txt:8-9` claiming both Pi and Mac build from the same source. Source: code + filesystem.
- X3: On APPLE the imported targets are declared `SHARED IMPORTED` but point at `libaasdk.a`/`libaap_protobuf.a` (`capture/CMakeLists.txt:13-33`). Links today, but the target type lies about the artifact; static-lib link order/`-Wl` semantics depend on it. Source: code.
- X4: AA sends `MEDIA_MESSAGE_CODEC_CONFIG` through `onMediaIndication` (video `aasdk-upstream/src/Channel/MediaSink/Video/VideoMediaSinkService.cpp:121-122`, audio `.../Audio/AudioMediaSinkService.cpp:111-112`), i.e. the codec-config blob arrives on the no-timestamp callback. Anything that routes both callbacks into one writer will concatenate config and media bytes. Source: vendor code.
- X5: `captures-mac/video.h264` and the `captures/*.h264` samples all start `00 00 00 01 67 42 80 1f` (Annex-B). They were produced by the OpenAuto capture patch, not by this app, so they do not validate the minimal app's output framing. Source: capture inspection.
- X6: `libusb_handle_events_timeout_completed` is called from 4 threads on one context (`capture/src/main.cpp:189-197`); aasdk's own pattern (`aasdk-upstream/src/USB/USBWrapper.cpp:130-131`) is one blocking `handleEvents()`. libusb allows concurrent callers but the completion thread then differs per callback. Source: code, unverified at runtime.

## Doc and code inconsistencies
- D1: `README.md:290` "Advertises video, 4 audio sinks, Bluetooth, input, sensor, microphone and Wi-Fi projection services" — code advertises 3 audio sinks and no Bluetooth/WPP (`capture/src/main.cpp:120-161`). Same error at `README.md:285` (table row lists Bluetooth and Wi-Fi projection as "logged, protocol handling") and `README.md:294` (WPP "advertises BSSID and returns SSID/password").
- D2: `capture/README.md:14-20` lists Bluetooth, Wi-Fi projection and telephony audio as advertised; code does not (`capture/src/main.cpp:114-164`). Both classes exist and compile (`capture/src/CMakeLists.txt:50,53`) but are never constructed.
- D3: `README.md:283` and `capture/README.md:27` promise `captures/audio-telephony.wav`; that file is never created (`capture/src/main.cpp:120-124`; the telephony name at `main.cpp:137-139` is unreachable).
- D4: `capture/README.md:25` "`video.h264` — H.264 Annex-B access units" — the app writes whatever aasdk hands it, with no framing conversion and no separation of the codec-config blob (`capture/src/VideoCapture.cpp:131-147`). Annex-B is unverified for this app's output.
- D5: `capture/README.md:32-33` "Prereqs: aasdk built at `../build-aasdk`" and `:44` "sets an rpath to `build-aasdk/lib`" — on this machine the tree is `build-aasdk-mac`, and `../aasdk`/`../build-aasdk` are absent (`capture/CMakeLists.txt:10-11,76`).
- D6: `capture/README.md:67` lists `quit` among stdin commands implying shutdown; code only breaks the read loop, the app keeps running (`capture/src/main.cpp:219-220`).
- D7: `capture/README.md:1-7` says the app "does not get past the phone's WPP" while `README.md:308-309` says it "captures some video, but resets on every session" — the two docs disagree on whether video ever arrives. Code has no mechanism preventing video (F9 active), so the `capture/README.md` framing is stale.
- D8: `README.md:249-250` places the version bump at `aasdk/include/aasdk/Version.hpp`; the file is `aasdk-upstream/include/aasdk/Version.hpp:21` (`AASDK_MINOR = 7`, true). `README.md:277` "commit `9bf6adf`" — true (`git -C aasdk-upstream log -1` = `9bf6adf`).
- D9: `README.md:88-91` and `:90` (truncation, timestamps ignored) are true: `capture/src/VideoCapture.cpp:96,134`, `capture/src/AudioCapture.cpp:178,198`, `capture/src/InputCapture.cpp:30`.
- D10: `NEXT-SESSION.md:41-42` "removing WPP, telephony, BT auth data, the whole BT service, and a reconnect loop; it still reset" — the removal is visible (D1/D2), a reconnect loop is absent from the source, so that claim is unverifiable from code.

## Assumptions to revalidate
- A1: Running the aasdk stack on 4 io threads plus 4 libusb event threads is safe. Baked in at `capture/src/main.cpp:189-200`. `Messenger` and `Transport` have internal strands (`aasdk-upstream/include/aasdk/Messenger/Messenger.hpp:54-55`, `.../Transport/Transport.hpp:56-59`) but `USBTransport` has no strand of its own. If false: intermittent USB transfer errors / corrupted streams under load, which would mimic the "AASDK Error 10" failures attributed to the dongle and BT DB.
- A2: `18d1:2d00` is never another device. Hardcoded at `capture/src/main.cpp:76`; the phone invariant (AOA+ADB phone is `18d1:2d01`) is only respected by luck of the PID match. If a phone ever enumerates as `2d00`, the app opens it.
- A3: `aasdk` 1.7 minor version is enough for this phone (`README.md:249-256`). Baked in via the aasdk build, not this code; no version negotiation check in `HeadUnit::onVersionResponse` (`capture/src/HeadUnit.cpp:83-109`).
- A4: Media ACK with `ack=1` per buffer and `max_unacked=1` keeps the phone streaming (`capture/src/VideoCapture.cpp:104,187`). If the phone expects cumulative acks, throughput collapses.
- A5: The dongle AP credentials in `WifiProjectionCapture` (`AutoLink-A512` / `12345678`, `capture/src/WifiProjectionCapture.cpp:77-78`) stay valid. Hardcoded, no config.
- A6: stdout/stderr logging is sufficient for runtime diagnosis (`capture/src/Log.hpp:14-30`); aasdk's own `AASDK_LOG` output is not configured anywhere, so aasdk diagnostics are silent.

## Bugs
- B1 [high]: The phones' `MEDIA_MESSAGE_CODEC_CONFIG` payload is written into the WAV data chunk as if it were PCM, corrupting the first frames of every audio capture. `capture/src/AudioCapture.cpp:205-208` forwards `onMediaIndication` into `onMediaWithTimestampIndication`, which writes unconditionally (`AudioCapture.cpp:199`). Scenario: start session -> phone sends codec config after start -> protobuf bytes land in `audio-media.wav` -> offset misalignment of the whole stream, audible click/DC at t=0. The same routing for video dumps an AVCC-format SPS/PPS blob into a file the doc calls Annex-B (`capture/src/VideoCapture.cpp:144-147`).
- B2 [high]: `quit` and `--duration` stop the io_service without ever calling `HeadUnit::stop()`, so `WavWriter::close()` runs only via destructors, after which `main` returns without a header patch if the process is killed. `capture/src/main.cpp:166,227-233` (no `headUnit->stop()` call anywhere). Scenario: SIGKILL or crash -> `audio-*.wav` keeps `data` size 0 (`capture/src/WavWriter.cpp:19-50,61-71`) -> file plays as empty until re-patched.
- B3 [medium]: Advertised ping interval 1000 ms vs actual 2000 ms, and timeout 3000 ms with tracked 5. `capture/src/HeadUnit.cpp:157-161` vs `HeadUnit.cpp:291`. Scenario: phone's control-channel watchdog can consider the head unit dead during a stall (>=3 s without ping) even though the head unit believes it pings every 2 s.
- B4 [medium]: stdin `quit` breaks only the reader loop; the process keeps running until `--duration` or a signal. `capture/src/main.cpp:219-220`. Scenario: operator types `quit`, session continues, captures keep growing.
- B5 [medium]: On `OPERATION_ABORTED` the error handlers return without re-arming `receive()`, permanently stalling that channel. `capture/src/HeadUnit.cpp:318-322`, `capture/src/VideoCapture.cpp:173-178`, `AudioCapture.cpp:210-216`, `InputCapture.cpp:98-103`, `SensorCapture.cpp:127-132`, `MicrophoneCapture.cpp:120-125`, `BluetoothCapture.cpp:124-129`, `WifiProjectionCapture.cpp:92-97`. Scenario: one abort -> channel silently stops delivering, only a full restart recovers.
- B6 [medium]: The video file is never closed on the stop indication, so late buffers after `Stop` are still appended and the next setup truncates the file mid-session. `capture/src/VideoCapture.cpp:123-129` (no `file_.close()`), `VideoCapture.cpp:96` (trunc on every setup). Audio does the opposite (closes on stop, truncates on start) — asymmetric (`capture/src/AudioCapture.cpp:178,190`).
- B7 [low]: `AudioCapture` reports `STATUS_READY` even when the WAV cannot be opened; the open happens later, at the start indication, so the file-open failure is invisible to the phone and the stream is dropped silently. `capture/src/AudioCapture.cpp:160-162` vs `AudioCapture.cpp:178-182`. Video reports `STATUS_WAIT` on failure (`capture/src/VideoCapture.cpp:99-103`).
- B8 [low]: AOA `SEND_STRING` treats any non-negative return as success, including a short or zero transfer. `capture/src/Usb.cpp:24-31`. Scenario: truncated string transfer -> AOA identity silently wrong (`README.md:246-247` claims specific strings).
- B9 [low]: `InputCapture::open_` is set on channel open and never cleared; touches keep being sent (and logged) after the channel is gone. `capture/src/InputCapture.cpp:65,133-136`.
- B10 [low]: `WavWriter` keeps the data size in `uint32_t` and patches a single RIFF size without odd-size padding. `capture/src/WavWriter.hpp:26`, `capture/src/WavWriter.cpp:66-70`. Scenario: >4 GB audio in one session (192 KB/s -> ~6.2 h) overflows the header; odd byte counts produce an unofficial chunk layout.
- B11 [low]: The detached stdin thread can call `input->tap()` after `ioService` and the service objects are destroyed. `capture/src/main.cpp:202-224` vs `227-233`. Scenario: a command arrives during shutdown -> dispatch on a destroyed strand. Process exit races make this hard to observe but it is a real use-after-free window.
- B12 [low]: `--duration` parses with `std::stoi` and no validation, so `--duration abc` aborts the whole run through the catch block. `capture/src/main.cpp:46-47,235-238`.

## Dead code, leftovers, stale comments
- L1: `capture/src/Usb.cpp:112-132` and `capture/src/Usb.hpp:31-33`, `openAoapDevice()` — never called; `main.cpp:75-94` reimplements the same loop inline.
- L2: `capture/src/BluetoothCapture.cpp:99-114`, `sendAuthenticationData()` — never called (`BluetoothCapture.hpp:44` declares it). The `bluetooth->add_supported_pairing_methods(... PIN ...)` at `BluetoothCapture.cpp:44-46` advertises a method this code refuses to serve.
- L3: `capture/src/CMakeLists.txt:50,53` compile `BluetoothCapture.cpp` and `WifiProjectionCapture.cpp` into a binary that never constructs them.
- L4: `CaptureService::pause()` / `resume()` (`capture/src/CaptureService.hpp:17-18`) are pure virtual, implemented empty in all 8 services (`VideoCapture.cpp:46-47`, `AudioCapture.cpp:74-75`, `InputCapture.cpp:45-46`, `SensorCapture.cpp:34-35`, `MicrophoneCapture.cpp:35-36`, `BluetoothCapture.cpp:33-34`, `WifiProjectionCapture.cpp:34-35`) and called from nowhere.
- L5: `capture/CMakeLists.txt:37,67-68` require `Boost::log_setup` and `Boost::log`; nothing in `capture/src/` includes or uses Boost.Log (`capture/src/Log.hpp` writes to `std::cerr`).
- L6: `capture/src/Log.hpp:4` includes `<sstream>`, unused.
- L7: `capture/src/main.cpp:120-147` builds the audio file name with a `switch` whose `telephony` branch (`main.cpp:137-139`) cannot be reached from the 3-element list at `main.cpp:120-124`; `AudioCapture::streamName()` duplicates the same mapping (`capture/src/AudioCapture.cpp:77-90`).
- L8: `capture/src/Usb.cpp:73` logs "AutoLink dongle not found in MTP mode" on every failed AOA attempt; `main.cpp:86-88` throttles only its own message, so a 120 s wait produces ~240 warnings.
- L9: `capture/src/main.cpp:68-69,189-200` mixes `io_service::work` with `ioService.stopped()` polling in the USB threads; the `work` object is never reset, so the only way out is `stop()` from a callback.

## Improvement areas
- I1: Kill the two unwired services or wire them. The doc set (README.md:285,290,294) describes behavior the binary cannot produce; either delete `BluetoothCapture`/`WifiProjectionCapture` and fix the docs, or register them in `main.cpp:114-161`. Same for the telephony audio sink, which is one line in `main.cpp:120-124`.
- I2: Separate codec config from media data. `onMediaIndication` carries codec config (X4); the fix is to store it per channel and prepend it once at setup, not to append it to the media file (B1 mechanism: `capture/src/AudioCapture.cpp:205-208`, `capture/src/VideoCapture.cpp:144-147`).
- I3: Make the WAV header self-healing, e.g. periodic seek-patch every second like the OpenAuto capture patch does; today the header is patched once at close (`capture/src/WavWriter.cpp:61-71`), which makes any crash leave an unplayable file.
- I4: Close the shutdown path properly: call `HeadUnit::stop()` after `ioService.run()` returns (or before `stop()`), and stop the stdin thread (`capture/src/main.cpp:227-233`, B2/B11).
- I5: Per-session output paths. Both the truncation (`VideoCapture.cpp:96`, `AudioCapture.cpp:178`, `InputCapture.cpp:30`) and the lack of a session suffix are the same root cause already named at `README.md:88-89`.
- I6: Drop the 4-thread USB event loop or reduce it to one, and run io in one thread until the concurrency model is proven (`capture/src/main.cpp:189-200`, A1). Simplification and a reliability win at the same time.
- I7: Pin Boost to 1.85 in `capture/CMakeLists.txt` (or migrate to `io_context`) and default `AASDK_SOURCE`/`AASDK_BUILD` to the trees that actually exist (`capture/CMakeLists.txt:10-11,37`, X1/X2). As-is the documented build command in `capture/README.md:39` fails on this machine.
- I8: Advertise and send one timestamp source. `aasdk` hands over a microsecond AA timestamp (`VideoCapture.cpp:131-134`, `AudioCapture.cpp:195-198`) which is discarded; writing it beside the payload would give the stream aspect what it needs for A/V sync (already named at `README.md:90-91`).

## Interfaces
- Exposes: a single executable `auriga_capture` (`capture/CMakeLists.txt:43`). CLI: `--out`, `--duration`, `--no-input`, `--help` (`capture/src/main.cpp:40-58`). Files: `<out>/video.h264`, `<out>/audio-media.wav`, `<out>/audio-system.wav`, `<out>/audio-guidance.wav`, `<out>/input.jsonl` (`capture/src/main.cpp:117,146,159`). stdin text protocol `tap|down|move|up X Y`, `quit` (`capture/src/main.cpp:202-224`), also usable via a FIFO as in `capture/README.md:70-77` — the same `/tmp/auriga-in` path the stream server uses, but with a different writer (the app reads stdin, so a FIFO must be redirected, the stream server writes to a FIFO).
- Consumes: `aasdk` + `aap_protobuf` static libs from `AASDK_BUILD` (`capture/CMakeLists.txt:10-33`); libusb for the AOA switch (`capture/src/Usb.cpp`); Boost.Asio, OpenSSL, protobuf, Threads (`capture/CMakeLists.txt:37-41`). Runtime inputs: the dongle at `2717:ff40`/`18d1:2d00`, the phone's AA session, stdin.
- Threading: main thread runs `ioService.run()`; 3 further `ioService.run()` threads; 4 threads spin `libusb_handle_events_timeout_completed` with a 100 ms timeout; 1 detached stdin thread (`capture/src/main.cpp:189-224`). Per-service strands (`HeadUnit.cpp:25`, each capture class's `strand_`), plus `Messenger`'s two internal strands. Callbacks from libusb arrive on whichever event thread wins; anything touching capture state must hop through a service strand.

## Open questions for the user
- Q1: Should `capture/` be kept at all, or is the headless emulator a fresh start? The docs call it both "rejected" (`NEXT-SESSION.md:39`) and "the basis for a future headless emulator" (`README.md:311-312`).
- Q2: Was Bluetooth/WPP deliberately removed from `main()` for the experiments described at `NEXT-SESSION.md:41-42`, or was the wiring lost? Decides whether L1/L2/L3 are history or a regression.
- Q3: Is the Boost 1.85 pin for `capture/` acceptable, or should the emulator target `io_context` so current Homebrew Boost works (X1)?
- Q4: Does any existing consumer read `<out>/video.h264` framing, or is the minimal app's output free to change (D4)?
