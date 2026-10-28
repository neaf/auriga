# Moving the working stack to macOS (skip the Pi)

## Goal

Run the proven OpenAuto head unit on the Mac with the AutoLink dongle plugged
directly into the Mac. No Pi, no powered hub, no SSH tunnel. The phone still
connects to the dongle's BT/Wi-Fi exactly as before; the dongle is host-agnostic.

Use **OpenAuto**, not the minimal `capture/` app. The minimal app completes AA
1.7/TLS/service discovery and captures real video, but it resets on every
session and does not recover. We tested removing WPP, telephony, the Bluetooth
auth data, the whole Bluetooth service, and adding a reconnect loop; it still
reset. OpenAuto is the only stack that projects end-to-end and auto-reconnects
after the dongle's first-session USB reset.

## Status (2026-10-28)

The macOS port builds, runs and projects:

- `build-aasdk-mac/lib/libaasdk.a` (51 MB) and `libaap_protobuf.a` (245 MB)
  build with aasdk `newdev` + `AASDK_MINOR = 7` and Boost 1.85.
- `build-openauto-mac/bin/autoapp` builds from OpenAuto `4cc739b8` +
  `patches/openauto-capture.patch` + `patches/openauto-macos.patch` (NOPI,
  offscreen capture).
- `scripts/mac-headunit-start.sh` runs `autoapp` + the stream server locally
  and opens `http://localhost:8080`; `scripts/mac-headunit-stop.sh` stops both.
- The stream server now waits for the capture files to appear, so it can start
  before the first AA session.

**Physical result (2026-10-28 19:03): projection works on the Mac.**

- Dongle direct to a Mac USB port (through the CalDigit dock's USB hub in this
  test), MTP `2717:ff40` -> AOA `18d1:2d00`.
- AA 1.7 (`Version Received: 256.1792`), TLS handshake, service discovery,
  1280x720/30 H.264 and 48 kHz/16-bit stereo media audio.
- Captured a full AA UI (Google Maps + Spotify) at 1280x720; 3057 frames over
  122 s and 68.6 s of media audio (mean -16.5 dB, peak -1.8 dB).
- Touch input works from both the browser canvas and the FIFO:
  `captures/2026-10-28-macos-session2-input.jsonl`; a tap on Spotify's
  pause/play button changed the projected UI.
- A fresh WebSocket client received 1 keyframe + 863 delta frames + 140 audio
  chunks in 3 s, so the browser pipeline is live on localhost.
- Brave at `http://localhost:8080` showed the live AA UI with the header
  `Auriga stream 1280x720 @ 30 fps frames ...`; audio starts muted until the
  🔇 button is clicked.
- Artifacts: `captures/2026-10-28-macos-session2-video.h264`,
  `...-audio-media.wav`, `...-input.jsonl`, and two extracted frames.

Dongle recovery on macOS: the first AA entity can fail with `AASDK Error 10`,
native 2, if it starts before the phone has associated with `AutoLink-A512`.
In that state the dongle stays in AOA and OpenAuto waits for a new USB device;
the phone connecting later does not revive the failed entity. A physical
unplug/replug (cold boot back to MTP) with the phone's BT/Wi-Fi on makes the
next AOA switch complete and project. This is the same first-session dongle
reset seen on the Pi; OpenAuto's automatic reconnect covers the case where the
phone is already associated.

Two macOS-only OpenAuto patches were needed:

- `SettingsWindow.cpp` referenced a `BluetoothAdapterLister` helper that does
  not exist in this tree and never compiled on macOS; replaced with the same
  `QBluetoothLocalDevice::allDevices()` enumeration as the Linux branch.
- OpenAuto always binds TCP 5000 for Android Auto over Wi-Fi, which conflicts
  with the macOS AirPlay Receiver (ControlCenter listens on 5000). In capture
  mode (`AURIGA_CAPTURE_DIR` set) it now binds an ephemeral port and does not
  accept TCP clients; the Auriga path is USB-only.

Other fixes are build flags only (absl/taglib/gps include paths, static aasdk's
OpenSSL symbols); see the exact configure line below.


## Hardware

- AutoLink dongle to a Mac USB port. The test Mac is a MacBook Air M4 (USB-C
  only), so the dongle was plugged into the CalDigit dock's USB-A port (the dock
  exposes a 4-port USB 2.0 hub). A passive USB-C to USB-A adapter is the
  closest-to-direct alternative; no separate powered hub was needed.
- Phone: Galaxy S25, paired to `AutoLink-A512`, Wi-Fi `AutoLink-A512` /
  `12345678`.
- Keep the iPhone/OPPO off.
- Prevent Mac sleep during tests: `caffeinate -dimsu` in a terminal (the start
  script does this).

## Brew dependencies

```bash
brew install boost@1.85 qt@5 taglib rtaudio util-linux gpsd \
  protobuf abseil libusb openssl@3 pkg-config
```

`boost@1.85` is required: aasdk/OpenAuto use `boost::asio::io_service`, which
Boost 1.92 removed. 1.85 still has it, so no source-wide patching. Homebrew
marks the formula deprecated/disabled but the bottle still installs
(`brew install boost@1.85` works as of 2026-10-28). It is keg-only; CMake must
be pointed at it explicitly (see `Boost_DIR` below), otherwise a cached
configure silently picks Homebrew's default Boost 1.92 and fails on
`boost::asio::io_service`.

Python for the stream server needs `websockets`; the repo uses a local venv:

```bash
/opt/homebrew/bin/python3.14 -m venv .venv
.venv/bin/pip install websockets
```

Qt5 must provide DBus, Multimedia, MultimediaWidgets, Bluetooth and Network.
Verify after install:

```bash
ls "$(brew --prefix qt@5)/lib/cmake" | grep -E "Qt5(Bluetooth|Multimedia|Network|DBus)"
```

If Qt5Bluetooth is missing, the Mac port needs a Qt5 build that includes
QtConnectivity (or a prebuilt Qt5 with it).

## Build aasdk 1.7 (macOS, static)

Use the `opencardev/aasdk` `newdev` source (the Pi tree matches it except
`Version.hpp`). Patch `Version.hpp`:

```cpp
static const uint16_t AASDK_MINOR = 7;
```

Protobuf 36 headers include absl headers. aasdk's macOS `aap_protobuf` target
does not add absl's include path. Patch `protobuf/CMakeLists.txt`, after the
`add_library(aap_protobuf ...)` block:

```cmake
if(CMAKE_SYSTEM_NAME STREQUAL "Darwin" AND TARGET absl::base)
    target_include_directories(aap_protobuf PUBLIC
        $<TARGET_PROPERTY:absl::base,INTERFACE_INCLUDE_DIRECTORIES>)
endif()
```

Configure/build:

```bash
cmake -S aasdk -B build-aasdk-mac \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DSKIP_BUILD_PROTOBUF=ON \
  -DSKIP_BUILD_ABSL=ON \
  -DAASDK_TEST=OFF \
  -DBoost_DIR="$(brew --prefix boost@1.85)/lib/cmake/Boost-1.85.0" \
  -DCMAKE_PREFIX_PATH="$(brew --prefix boost@1.85);$(brew --prefix protobuf);$(brew --prefix abseil);$(brew --prefix openssl@3);$(brew --prefix libusb)"

cmake --build build-aasdk-mac --target aasdk -j8
```

On macOS aasdk builds **static** `libaasdk.a` and `libaap_protobuf.a`.
`CMAKE_POLICY_VERSION_MINIMUM=3.5` is needed because aasdk's
`gitversion.cmake` still uses an old `cmake_minimum_required`.

If `build-aasdk-mac` was configured before `boost@1.85` was installed, the
Boost cache entries point at 1.92. Clear them before reconfiguring:

```bash
cmake -S aasdk -B build-aasdk-mac '-UBoost_.*' \
  -DBoost_DIR="$(brew --prefix boost@1.85)/lib/cmake/Boost-1.85.0"
```

## Build OpenAuto (macOS)

Pin the proven commit and apply both patches:

```bash
git clone https://github.com/opencardev/openauto.git openauto
git -C openauto checkout 4cc739b8
git -C openauto apply /path/to/auriga/patches/openauto-capture.patch
git -C openauto apply /path/to/auriga/patches/openauto-macos.patch
```

`openauto-macos.patch` contains the two source fixes described in Status:
the missing macOS Bluetooth lister and the AirPlay/TCP-5000 conflict.

Configure. The important bits:

- `NOPI=ON` (no Raspberry Pi OMX/BCM).
- `AASDK_INCLUDE_DIR` must be the `aasdk` subdirectory (OpenAuto includes
  `<Transport/...>` in one place) **and** the parent must be on the include
  path for `<aasdk/...>`.
- `AASDK_LIB_DIR` / `AAP_PROTOBUF_LIB_DIR` point at the static `.a` files.
- `AAP_PROTOBUF_INCLUDE_DIR` is the generated protobuf tree.
- `CMAKE_PREFIX_PATH` includes qt@5, boost@1.85, protobuf, abseil, taglib,
  rtaudio, util-linux, gpsd, openssl@3, libusb.
- `Boost_DIR` must point at 1.85 explicitly.
- absl, taglib and gpsd headers need explicit include roots on macOS.
- `Findtaglib` appends a bare `-ltag`, which macOS cannot resolve; override
  `TAGLIB_LIBRARIES`/`TAGLIB_INCLUDE_DIRS` with the Homebrew paths.
- Static `libaasdk.a` leaves OpenSSL symbols undefined; add libssl/libcrypto to
  `CMAKE_EXE_LINKER_FLAGS` (the `OPENSSL_LIBRARIES` variable is not used by this
  OpenAuto's link line).

```bash
cmake -S openauto -B build-openauto-mac \
  -DCMAKE_BUILD_TYPE=Release -DNOPI=ON \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DAASDK_INCLUDE_DIR="$PWD/aasdk/include/aasdk" \
  -DAASDK_LIB_DIR="$PWD/build-aasdk-mac/lib/libaasdk.a" \
  -DAAP_PROTOBUF_INCLUDE_DIR="$PWD/build-aasdk-mac/protobuf" \
  -DAAP_PROTOBUF_LIB_DIR="$PWD/build-aasdk-mac/lib/libaap_protobuf.a" \
  -DCMAKE_CXX_FLAGS_INIT="-I$PWD/aasdk/include -I$(brew --prefix abseil)/include -I$(brew --prefix taglib)/include -I$(brew --prefix gpsd)/include" \
  -DBoost_DIR="$(brew --prefix boost@1.85)/lib/cmake/Boost-1.85.0" \
  -DTAGLIB_LIBRARIES="$(brew --prefix taglib)/lib/libtag.dylib" \
  -DTAGLIB_INCLUDE_DIRS="$(brew --prefix taglib)/include/taglib" \
  -DOPENSSL_LIBRARIES="$(brew --prefix openssl@3)/lib/libssl.dylib;$(brew --prefix openssl@3)/lib/libcrypto.dylib" \
  -DCMAKE_EXE_LINKER_FLAGS="$(brew --prefix openssl@3)/lib/libssl.dylib $(brew --prefix openssl@3)/lib/libcrypto.dylib" \
  -DCMAKE_PREFIX_PATH="$(brew --prefix qt@5);$(brew --prefix boost@1.85);$(brew --prefix protobuf);$(brew --prefix abseil);$(brew --prefix taglib);$(brew --prefix rtaudio);$(brew --prefix util-linux);$(brew --prefix gpsd);$(brew --prefix openssl@3);$(brew --prefix libusb)"

cmake --build build-openauto-mac --target autoapp -j8
```

(Use `aasdk-upstream` instead of `aasdk` when reusing the Mac tree; the Pi's
`aasdk` tree is not present on the Mac.)

Actual macOS fixes applied:

- absl headers: protobuf 36 headers include `absl/...`; the generated
  `aap_protobuf` target carries them, but OpenAuto compiles against its own
  include list, so absl's include root is in `CMAKE_CXX_FLAGS_INIT`.
- taglib: OpenAuto includes `<taglib/fileref.h>`; both
  `.../include` and `.../include/taglib` are needed.
- gps: OpenAuto never adds `GPS_INCLUDE_DIRS` to its include list, and
  `gps.h` is not in a system include on macOS.
- blkid: found automatically from util-linux (no override needed).
- Qt5 `QDesktopWidget`/`QApplication` work with
  `QT_QPA_PLATFORM=offscreen`; capture mode uses file sinks, not Qt decode.

## Run on the Mac

The normal path is the launch script, from the repo root:

```bash
./scripts/mac-headunit-start.sh
```

It starts `openauto-config/run-mac.sh` (offscreen, capture dir
`captures-mac/`, input FIFO `/tmp/auriga-in`), starts the stream server with
the Mac capture paths, keeps the Mac awake with `caffeinate`, and opens
`http://localhost:8080`.

`openauto-config/run-mac.sh` runs without `sudo`; libusb can open the dongle as
the user. If AOA control transfers fail with permissions, run the script via
`sudo` for the test.

Manual equivalent:

```bash
cd openauto-config
./run-mac.sh

# in another terminal, from the repo root
.venv/bin/python stream/auriga_stream.py \
  --video captures-mac/video.h264 \
  --audio captures-mac/audio-media.wav \
  --fifo /tmp/auriga-in
```

Open `http://localhost:8080` in Brave/Chrome. No SSH tunnel needed on the Mac.
The stream server binds `127.0.0.1`; localhost is a secure context for
WebCodecs.

Stop with:

```bash
./scripts/mac-headunit-stop.sh
```

## Test sequence

1. Dongle in MTP; phone BT/Wi-Fi off.
2. Start `autoapp`; it switches MTP→AOA and waits.
3. Start the stream server + browser.
4. Turn phone BT/Wi-Fi on; it connects to `AutoLink-A512`.
5. Phone projects; video/audio/input captured.
6. The first AA session may reset on the dongle's Bluetooth pairing request;
   OpenAuto auto-reconnects; the next session is stable. Expect one reset.
7. If the phone sits on "Communication error 2" after the reset, close/relaunch
   Android Auto (ADB: `adb shell input tap` on EXIT, then
   `adb shell monkey -p com.google.android.projection.gearhead -c
   android.intent.category.LAUNCHER 1`).

## Known macOS risks

- USB/AOA: macOS libusb access, hotplug, and power management differ from
  Linux. The dongle may reset more/less; `mac-headunit-start.sh` runs
  `caffeinate` so the Mac does not sleep.
- The dongle's first-session reset is a dongle behaviour; OpenAuto's reconnect
  is the fix. Per-session output files are still needed so a reset does not
  overwrite the previous capture.
- The capture app binds TCP 5000 on Linux for AA-over-Wi-Fi. The macOS patch
  disables that in capture mode because AirPlay Receiver owns port 5000.
- OpenAuto's `display_name` is still `Crankshaft-NG`; patch to `Auriga`.
- File sinks ignore AA timestamps; A/V sync is best-effort. The long-term fix
  is feeding the stream directly from aasdk callbacks with timestamps.

## Fallback

The Pi stack is committed and working:
`~/auriga/scripts/pi-start.sh`, `scripts/mac-start.sh`, `stream/`,
`patches/openauto-capture.patch`. If the Mac port is blocked, move the dongle
back to the Pi and restart there.