# Audit: build-and-tooling

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| .gitignore | 52 | yes |
| README.md | 389 | yes |
| DEVELOPING.md | 149 | yes |
| MAC-PORT.md | 329 | yes |
| NEXT-SESSION.md | 89 | yes |
| openauto-config/openauto-logs.ini | 17 | yes |
| openauto-config/openauto.ini | 29 | yes |
| openauto-config/run-mac.sh | 36 | yes |
| openauto-config/run.sh | 32 | yes |
| capture/CMakeLists.txt | 77 | yes |
| patches/openauto-macos.patch | 89 | yes |
| total | 1288 | |

Cross-checked (not assigned, read for verification): `patches/{openauto-capture,openauto-auriga-usb-filter,openauto-auriga-gps-guard,aasdk-usb-filter}.patch`, `scripts/{mac-headunit-start,mac-headunit-stop,pi-start,pi-stop}.sh`, `capture/README.md`, `openauto/CMakeLists.txt`, `openauto/src/autoapp/{autoapp.cpp,App.cpp,Service/ServiceFactory.cpp,UI/SettingsWindow.cpp}`, `openauto/src/autoapp/Configuration/Configuration.cpp`, `openauto/src/autoapp/Projection/Auriga*.cpp`, `aasdk-upstream/CMakeLists.txt`, both `CMakeCache.txt`.

## Functional behavior
- F1: A `Release` build of OpenAuto at `4cc739b8` from four patches produces `build-openauto-mac/bin/autoapp` (symlink to `autoapp-2026.10.28+git.4cc739b.dirty`). Evidence: `build-openauto-mac/bin/`, `git -C openauto log -1` = `4cc739b`, `cmake --build build-openauto-mac --target autoapp -- -n` prints `Built target autoapp`. Status: active.
- F2: aasdk builds `STATIC` on Darwin (`aasdk-upstream/CMakeLists.txt:287-288`); artifacts `libaasdk.a` 51,898,688 B and `libaap_protobuf.a` 245,206,744 B. Evidence: `build-aasdk-mac/lib/`. Status: active.
- F3: Patch order capture -> macos -> auriga-usb-filter -> auriga-gps-guard applies cleanly to a pristine `4cc739b8` tree and reproduces the working-tree diff byte-for-byte. Evidence: test clone, `diff /tmp/ao-frompatches.diff /tmp/ao-tree.diff` empty. Status: active.
- F4: Compile-time config is read from `openauto.ini` in the process CWD (`Configuration.cpp:29,93`); `Video.Resolution=2` -> `VIDEO_1280x720`, `Video.FPS=2` -> `VIDEO_FPS_30`. Evidence: `openauto-config/openauto.ini:7-8`, `VideoCodecResolutionType.pb.h:72`, `VideoFrameRateType.pb.h:72`, `ServiceFactory.cpp:149`, `openauto-config/openauto.log` "Resolution 1280x720". Status: active.
- F5: `AURIGA_CAPTURE_DIR` switches video/audio/mic/input backends to file sinks and makes `App` bind TCP port 0 and never start the TCP server. Evidence: `ServiceFactory.cpp:61-80,86-88,165-168,227-230,246`; `App.cpp:31,43,59,185`. Status: active.
- F6: Logging config is read from `openauto-logs.ini` in CWD; Console + `TextFile openauto.log`, both `Asynchronous=false`, `%Severity% >= info`. Evidence: `autoapp.cpp:76-88`, `openauto-config/openauto-logs.ini:4-17`, `openauto-config/openauto.log` present (25 KB). Status: active.
- F7: `run-mac.sh` creates `/tmp/auriga-in`, parks a `sleep 86400` writer on it, then `exec env AURIGA_CAPTURE_DIR=... QT_QPA_PLATFORM=offscreen "$BIN" < "$FIFO"`, without sudo. Evidence: `run-mac.sh:19-36`. Status: active.
- F8: Start/stop is pid-file based plus `pkill -f` patterns: `/tmp/auriga-mac-{autoapp,stream,caffeinate}.pid`, `/tmp/auriga-fifo-writer.pid`. Evidence: `mac-headunit-start.sh:42,63,75`; `mac-headunit-stop.sh:16-22`. Status: active.
- F9: AOA switching is restricted to `2717:ff40` and `18d1:2d01` is refused when a filter is set. Evidence: `patches/aasdk-usb-filter.patch:55-64,78-88`; caller passes `0x2717, 0xFF40` at `openauto/src/autoapp/autoapp.cpp:246-247`. Status: active.
- F10: New OpenAuto sources are found by `file(GLOB_RECURSE ...)` at configure time, not listed. Evidence: `openauto/CMakeLists.txt:152-154`. Status: active.
- F11: `capture/` (minimal app) is a self-contained CMake project with `--out/--duration/--no-input` flags; no build directory exists on the Mac, docs call it rejected. Evidence: `capture/CMakeLists.txt:43-55`, `capture/src/main.cpp:44-48`, `MAC-PORT.md:9-14`. Status: dead (documented as non-working stack).

## External facts and quirks
- X1: Boost 1.85 is genuinely required. Homebrew default is `boost 1.92.0_1`, whose tree has no `boost/asio/io_service.hpp`; `boost@1.85.0_3` has it. Symptom if unpinned: compile error on `io_service`. Cause: asio removed the alias. Workaround: `-DBoost_DIR=.../Boost-1.85.0` (`MAC-PORT.md:103-109`, cache value confirmed). Source: shell.
- X2: CMake here is 4.4.4; aasdk's `gitversion.cmake` still declares an old minimum, so `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` is mandatory. Both caches carry it. Source: code/cache.
- X3: macOS AirPlay Receiver owns TCP 5000; the patch binds an ephemeral port instead of 5000 in capture mode. Source: code `App.cpp:31-33,185`, `MAC-PORT.md:70-78`.
- X4: The H.264 captures carry no container timestamps. `ffprobe` reports `r_frame_rate=1200000/1` for the 1280x720 stream; frame count 3057 matches the docs, duration does not. Any timing/verify step based on ffprobe duration is wrong (`DEVELOPING.md:122` only counts frames, so it survives). Source: shell.
- X5: The WAV header size is only refreshed at `seekp(0,end)` points (`AurigaAudioOutput.cpp:165`); during a run RIFF size lags the file (observed 363,593,772 in header vs 363,872,300 bytes on disk). Truncated readback after an unfinalized run is expected. Source: shell.
- X6: Per-channel audio formats are not uniform: media 48 kHz/2 ch, guidance 16 kHz/1 ch, system 16 kHz/1 ch (`ServiceFactory.cpp:184,192,218`; ffprobe of `captures-mac/audio-*.wav`). Source: code + shell.
- X7: protobuf 36.2 headers pull in absl; the include root is injected through `CMAKE_CXX_FLAGS_INIT` rather than a target. Source: `build-openauto-mac/CMakeCache.txt`, `MAC-PORT.md:244-250`.
- X8: `Findtaglib` emits a bare `-ltag` that macOS cannot resolve; `TAGLIB_LIBRARIES`/`TAGLIB_INCLUDE_DIRS` are overridden by hand. Source: `MAC-PORT.md:216-217`, cache.
- X9: With a filter set, `USBHub::handleDevice` still accepts *any* AOAP non-ADB device (`18d1:2d00`), not only `2717:ff40`. A phone already in accessory mode would still be claimed. Source: code `patches/aasdk-usb-filter.patch:98-101`.
- X10: Repo root carries four ignored 207-byte dongle DB copies (`btapp.db.galaxy`, `btapp.db.galaxy2`, `btapp.bk.galaxy`, `btapp.bk.galaxy2`); `README.md:236-238` states those keys are stale after the re-pair. Source: shell.

## Doc and code inconsistencies
- D1: `DEVELOPING.md:32-34` and `:91-92` say `patches/` is the source of truth and "a clean rebuild applies the patches". Code: `patches/openauto-capture.patch` omits the `IInputDeviceEventHandler.hpp` include that the working tree has at `openauto/src/autoapp/Projection/AurigaInputDevice.cpp:18`; a pristine + patches tree fails to compile (see B1).
- D2: `README.md:283` (and the AGENTS audio note) says `captures/audio-*.wav` are "48 kHz, 16-bit, stereo". Code: guidance and system sinks are 16 kHz mono (`ServiceFactory.cpp:192,218`); no `audio-telephony.wav` is ever created because `openauto-config/openauto.ini:20` disables telephony.
- D3: `README.md:363` and `DEVELOPING.md` describe `openauto-config/run.sh` as the Pi launcher. `scripts/pi-start.sh:9` looks for `$BASE/openauto-run/run.sh`, a directory that is not in the repo (`git ls-files | grep openauto-run` empty) -> the documented Pi start path exits "missing .../run.sh".
- D4: `MAC-PORT.md:22-24` says `autoapp` builds from `openauto-capture.patch` + `openauto-macos.patch`; the same file (`:192-196`) applies four patches. The two-patch list is stale.
- D5: `capture/CMakeLists.txt:7-11` claims the cached `../aasdk` / `../build-aasdk` defaults make "the same source build on the Pi and the Mac". On this machine neither exists (trees are `aasdk-upstream`, `build-aasdk-mac`), and `capture/README.md` gives Pi-only build steps.
- D6: `DEVELOPING.md:40-45` "Current local changes" table lists only the USB-filter and GPS-guard edits; the largest delta in the tree (capture patch: `ServiceFactory.cpp:61-80`, eight new `Auriga*` projection files) is absent from the table.
- D7: `openauto-config/openauto.ini:22-24` (`Bluetooth.AdapterType`) and `:27-29` (`Input.EnableTouchscreen`, `Input.EnablePlayerControl`) are parsed into `Configuration` but have no reader anywhere in `openauto/src` (grep for `getEnableTouchscreen`, `getBluetoothAdapterType`, `getPlayerControlEnabled` outside `Configuration.cpp` = 0 hits) -> inert config. BT behaviour is driven only by `Bluetooth.AdapterAddress` (`ServiceFactory.cpp:126-134`).
- D8: `README.md:367` frames `captures/` as local media, but `.gitignore:23-26` ignores only `*.h264/*.mp4/*.wav/*.png`; three `captures/*-input.jsonl` are tracked because `*.jsonl` is not ignored.
- D9: `MAC-PORT.md:20-21` sizes are decimal-rounded (51 MB vs 51,898,688 B, 245 MB vs 245,206,744 B) and match only in decimal units; `du` in MiB reads 49M/234M. Cosmetic.

## Assumptions to revalidate
- A1: aasdk reproducibility depends on two manual edits kept out of `patches/` — `Version.hpp` `AASDK_MINOR = 7` and the absl include block in `protobuf/CMakeLists.txt` (`MAC-PORT.md:128-146`, tree status shows both `M`). If a rebuild only applies patches, aasdk stays at protocol 1.6 and AA negotiation fails.
- A2: `boost@1.85` is deprecated by Homebrew but still installable (`MAC-PORT.md:104-106`). If the bottle disappears, no documented build path exists; the fix is source-wide `io_context` migration.
- A3: Qt5 5.15 must ship QtConnectivity (Bluetooth); `SettingsWindow.cpp:21-22` includes `QBluetoothLocalDevice`/`QBluetoothHostInfo` unconditionally.
- A4: Capture-mode behaviour hinges on one env var, `AURIGA_CAPTURE_DIR` (`ServiceFactory.cpp:64-79`, `App.cpp:31`). Any shell that sets it changes sinks and TCP binding with no other signal; any run that does not set it writes no captures.
- A5: The two `openauto-auriga-*` patches stay incremental on top of capture+macos because both touch `App.cpp`; `DEVELOPING.md:74-76` states this, and the usb-filter patch needs `aurigaCaptureMode()` from the macos patch.
- A6: Build reproducibility assumes the GLOB predicate picks up files (`openauto/CMakeLists.txt:152`). Adding a source without re-running configure silently omits it from the build.
- A7: `capture/` is kept as "basis for a future emulator" (`README.md:341-342`) although the doc calls it rejected.
- A8: `.rearch/` is committed to the repo (`.rearch/STATE.md`, `inventory.md`, `baseline.md`) and is not in `.gitignore`; a new architecture may want it excluded.

## Bugs
- B1 [high]: `patches/openauto-capture.patch` is incomplete — it does not include `<f1x/openauto/autoapp/Projection/IInputDeviceEventHandler.hpp>`, which `AurigaInputDevice.cpp:212` needs (`eventHandler_->onTouchEvent`). `IInputDevice.hpp:34` only forward-declares the type. Scenario: fresh clone + the four documented `git apply` commands + `cmake --build` -> `error: member access into incomplete type 'IInputDeviceEventHandler'` (reproduced with `c++ -fsyntax-only` on the patch-built tree; the live tree compiles only because someone added the include at `AurigaInputDevice.cpp:18` on 2026-10-28 12:24, after the patch was written at 12:21). This breaks the stated "patches are the source of truth" contract.
- B2 [medium]: the documented patch-regeneration recipe cannot capture new files. `git -C openauto diff -- src/autoapp/Projection/AurigaVideoOutput.cpp` returns 0 lines because the eight `Auriga*` files are untracked (`??`), and `patches/openauto-capture.patch` contains 8 `new file mode` entries that a plain `git diff` will not reproduce. Scenario: follow `DEVELOPING.md:96-104` literally -> regenerated patch silently drops all new sources. Fix requires `git add -N` or `git diff --no-index`.
- B3 [medium]: Pi start path is broken. `scripts/pi-start.sh:9` sets `RUN_DIR=$BASE/openauto-run`; the repo ships `openauto-config/run.sh` and no `openauto-run/`. Scenario: `~/auriga/scripts/pi-start.sh` on the Pi -> "missing /home/pi/auriga/openauto-run/run.sh", exit 1 (`MAC-PORT.md:327-330` presents this as the working fallback).
- B4 [low]: `run-mac.sh:23-24` unconditionally `rm -f` + `mkfifo` the shared FIFO path. Scenario: `autoapp` restarted (script, not start script) while the stream server and any other writer hold the old inode -> taps go to a stale FIFO and are dropped silently; `mac-headunit-stop.sh` is then the only recovery.
- B5 [low]: `DEVELOPING.md:79-80` verification commands do not run as written: `git -C openauto apply --check --reverse patches/...` resolves the relative patch path inside `openauto/`. Reproduced: `error: can't open patch 'patches/openauto-capture.patch': No such file or directory`. Needs an absolute path or `-C . `.
- B6 [low]: `openauto-capture.patch` reverse-check on the live tree fails for `src/autoapp/Projection/AurigaInputDevice.cpp` (patch does not apply) while the other four patches reverse-check clean. The tree and `patches/` disagree on that one file (same root cause as B1/B2). Scenario: the "verify against current tree" step in `DEVELOPING.md:78-81` gives a false negative for the capture patch.
- B7 [low]: no SIGTERM handler exists in the autoapp sources (no `signal(`/`SIGINT`/`SIGTERM` in `openauto/src/autoapp/*.cpp`) and `mac-headunit-stop.sh:21` uses `pkill` (SIGTERM). Scenario: stop during a session -> WAV `data` size and the JSONL stream keep whatever was last flushed; the header stays at the last `seekp(0,end)` value (`AurigaAudioOutput.cpp:165`), so the tail of the file is unreadable by size-trusting tools.
- B8 [low]: `mac-headunit-start.sh:73-76` records `$!` of `nohup caffeinate -dimsu` in `/tmp/auriga-mac-caffeinate.pid`, but the guard is `pgrep -f "[c]affeinate -dimsu"`; if a user-started `caffeinate` exists, no pid file is written, so stop leaves it running and reports success.

## Dead code, leftovers, stale comments
- L1: `capture/` (23 sources + CMakeLists + README) — documented as the failed stack (`README.md:301-312`, `MAC-PORT.md:9-14`), no build directory on this host, still listed in the file map as the emulator base.
- L2: `capture/CMakeLists.txt:13-20` Apple branch points `SHARED IMPORTED` targets at `.a` files (`:22-33`); wrong library kind and never exercised.
- L3: `openauto-config/run.sh:31` hardcodes `LD_LIBRARY_PATH=/home/pi/auriga/build-aasdk/lib`, an absolute Pi-only path, inside a repo-relative script.
- L4: `run.sh:7`/`run-mac.sh:12` duplicate ~25 lines of FIFO and binary-discovery logic that differs only in one `|| true` and the sudo/LD_LIBRARY_PATH lines.
- L5: `patches/openauto-macos.patch:31-33` binds port 0 even though `startServerSocket()` is never called (`:41-44`); the acceptor is constructed, bound and listening on an ephemeral port for no purpose.
- L6: `.gitignore:30` keeps one historical file tracked (`logs/run-baseline-114525.filtered.log`); `logs/` otherwise holds 26 ignored runtime logs.
- L7: `openauto-config/openauto.log` (ignored, 25 KB) and `openauto-config/openauto.ini` (mtime 2026-10-28 11:51) are runtime state inside a source directory; `Configuration::save()` (`MainWindow.cpp:1379`, `SettingsWindow.cpp:364`) rewrites `openauto.ini` with ~40 keys while the committed file has 26 lines, so any UI save produces silent churn.
- L8: `.gitignore` covers `/build-*/` only at the repo root; a `capture/build-*` or `capture/build` produced by `capture/README.md`'s `-B build-capture` (repo root, so ignored) is fine, but any in-tree build under `capture/` would be tracked.
- L9: `README.md:346` "openauto-plan.md — full OpenAuto build/run/patch plan" duplicates MAC-PORT.md; two overlapping build documents with different patch counts (see D4).

## Improvement areas
- I1: Add `patches/aasdk-version-absl.patch` for `Version.hpp` + `protobuf/CMakeLists.txt` and a `scripts/build-from-patches.sh` that clones both upstreams into a temp dir, applies all patches, configures and builds. Mechanism: makes `patches/` self-verifying and would have caught B1/B2 at commit time.
- I2: Replace the two ~18-line `cmake` invocations copy-pasted into `MAC-PORT.md:160-171,222-239` and referenced from `DEVELOPING.md:53-59` with one checked-in `scripts/configure-mac.sh`. Mechanism: a `Boost_DIR`/`CXX_FLAGS_INIT` typo in prose currently costs a full reconfigure (`-UBoost_.*`, `MAC-PORT.md:177-183`) to detect.
- I3: Per-session output names plus a size cap. Mechanism: `AurigaVideoOutput.cpp:39` and `AurigaAudioOutput.cpp:70` open with `std::ios::trunc`, so a live session now holds 307 MB H.264 + 355 MB WAV (`captures-mac/`), and every new AA session deletes the previous capture (documented at `README.md:88-89`, `DEVELOPING.md:145`).
- I4: Rotate `openauto.log` (`openauto-logs.ini:11-17` has no rotation, `AutoFlush=true`); a long run grows it unbounded with `Asynchronous=false` blocking the calling thread on every record.
- I5: Add one automated check: a CI job that builds from patches and asserts `ffprobe -count_frames` + `-show_entries stream=width,height` on a sample. Mechanism: all current verification is a manual checklist (`DEVELOPING.md:106-127`) that requires the dongle, phone and `adb`.
- I6: List sources explicitly in `openauto/CMakeLists.txt:152` instead of `GLOB_RECURSE`. Mechanism: a silently missing TU today only shows up as a link error or a missing feature.
- I7: Delete or wire the inert ini keys (D7); drop `Input.*`/`Bluetooth.AdapterType` from `openauto.ini` so the file states what is actually configurable, and move the BT choice to `AdapterAddress` (already the only live knob).
- I8: Merge `run.sh` and `run-mac.sh` into one script parameterised by `AURIGA_PLATFORM` (build dir, sudo, LD_LIBRARY_PATH). Mechanism: two 30-line scripts that must stay in sync currently differ in ways that matter (sudo, rpath env, `|| true`).
- I9: Validate pid files before `kill` in `mac-headunit-stop.sh:6-13` (check process name/start time). Mechanism: `/tmp` pid files survive reboots; a reused pid gets killed.
- I10: `.gitignore` additions: `/captures/*.jsonl`, `capture/build*`, `/.rearch/` (decision, A8), and a `logs/*.log.*` rotation pattern.

## Interfaces
- Exposes: build artifacts `build-aasdk-mac/lib/{libaasdk.a,libaap_protobuf.a}` and `build-openauto-mac/bin/autoapp` (+ version-suffixed binary and symlink); env contract `AURIGA_CAPTURE_DIR` (sink switch + TCP disable), `AURIGA_INPUT_FIFO`, `AURIGA_PYTHON`, `AURIGA_DIR`, `QT_QPA_PLATFORM`; filesystem contract `/tmp/auriga-in`, `/tmp/auriga-{mac-}*.pid`, `/tmp/auriga-fifo-writer.pid`, `captures-mac/{video.h264,audio-{media,guidance,system}.wav,input.jsonl}`, `logs/openauto-mac-*.log`, `logs/stream-mac-*.log`; config contract `openauto.ini` / `openauto-logs.ini` resolved from CWD; the five files in `patches/`.
- Consumes: nested clones `openauto/` @ `4cc739b8` and `aasdk-upstream/` @ `9bf6adf` (`newdev`), both expected dirty; unpatched manual edits in those clones; Homebrew `boost@1.85` (keg-only), `qt@5` 5.15.19 with QtConnectivity, `protobuf` 36.2, `abseil`, `taglib`, `rtaudio`, `util-linux`, `gpsd`, `openssl@3`, `libusb`, `pkg-config`; CMake 4.4.4; `.venv` (Python 3.14.8 + `websockets` 17.3); `ffmpeg`/`ffprobe` for the checklist; `adb` + `ioreg` for verification.
- Threading: build/tooling itself is single-threaded (`cmake --build ... -j8`); the run scripts are POSIX `sh` (macOS `/bin/sh` = bash 3.2 in posix mode) and rely on `set -eu`; `run-mac.sh` ends in `exec env ... autoapp`, so the pid file PID is preserved across exec; `autoapp` itself runs 1 USB worker + 4 `io_service` workers (`autoapp.cpp:63-71`) and `AurigaInputDevice` reads stdin on its own thread (`AurigaInputDevice.cpp:47-70`), while `AurigaAudioOutput`/`AurigaVideoOutput` file writes happen on aasdk strand callbacks. The dummy `sleep 86400` FIFO writer exists purely so the reader thread never sees EOF.

## Open questions for the user
- Q1: Is the Pi stack still a supported target, or can `scripts/pi-*.sh`, `run.sh` and the Pi-only `LD_LIBRARY_PATH` go? (B3, D3)
- Q2: Delete `capture/` (23 files, unused, documented as rejected) or keep it for the planned headless emulator?
- Q3: Should the aasdk `Version.hpp` / `protobuf/CMakeLists.txt` edits be moved into `patches/` (I1) — i.e. is a one-command, source-of-truth rebuild a requirement?
- Q4: Per-session capture filenames — is a new naming scheme allowed to change the `captures-mac/video.h264` path the stream server and docs depend on?
- Q5: Does `.rearch/` belong in git (currently committed) or in `.gitignore`?
- Q6: Should the three tracked `captures/*-input.jsonl` stay in git, or be dropped and gitignored like the media?

## Result
Docs are accurate on numbers (3057 frames, lib sizes, config key semantics, Boost 1.85 necessity) but `patches/` is not a complete source of truth: a clean rebuild from the four documented patches fails to compile (B1), and the documented regeneration path drops the eight new files (B2). The Pi launch path in the docs points at a directory that does not exist (B3). Config in `openauto.ini` is correct and applied, with two dead key groups (D7).
