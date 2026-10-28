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

## Hardware

- AutoLink dongle direct to a Mac USB port. No hub required for the first test;
  if the dongle browns out, use a small powered hub.
- Phone: Galaxy S25, paired to `AutoLink-A512`, Wi-Fi `AutoLink-A512` /
  `12345678`.
- Keep the iPhone/OPPO off.
- Prevent Mac sleep during tests: `caffeinate -dimsu` in a terminal.

## Brew dependencies

```bash
brew install boost@1.85 qt@5 taglib rtaudio util-linux gpsd \
  protobuf abseil libusb openssl@3 pkg-config
```

`boost@1.85` is required: aasdk/OpenAuto use `boost::asio::io_service`, which
Boost 1.92 removed. 1.85 still has it, so no source-wide patching.

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
  -DCMAKE_PREFIX_PATH="$(brew --prefix boost@1.85);$(brew --prefix protobuf);$(brew --prefix abseil);$(brew --prefix openssl@3);$(brew --prefix libusb)"

cmake --build build-aasdk-mac -j8
```

On macOS aasdk builds **static** `libaasdk.a` and `libaap_protobuf.a`.
`CMAKE_POLICY_VERSION_MINIMUM=3.5` is needed because aasdk's
`gitversion.cmake` still uses an old `cmake_minimum_required`.

## Build OpenAuto (macOS)

Pin the proven commit and apply the capture patch:

```bash
git clone https://github.com/opencardev/openauto.git openauto
git -C openauto checkout 4cc739b8
git -C openauto apply /path/to/auriga/patches/openauto-capture.patch
```

Configure. The important bits:

- `NOPI=ON` (no Raspberry Pi OMX/BCM).
- `AASDK_INCLUDE_DIR` must be the `aasdk` subdirectory (OpenAuto includes
  `<Transport/...>` in one place) **and** the parent must be on the include
  path for `<aasdk/...>`.
- `AASDK_LIB_DIR` / `AAP_PROTOBUF_LIB_DIR` point at the static `.a` files.
- `AAP_PROTOBUF_INCLUDE_DIR` is the generated protobuf tree.
- `CMAKE_PREFIX_PATH` includes qt@5, boost@1.85, protobuf, abseil, taglib,
  rtaudio, util-linux, gpsd, openssl@3, libusb.

```bash
cmake -S openauto -B build-openauto-mac \
  -DCMAKE_BUILD_TYPE=Release -DNOPI=ON \
  -DAASDK_INCLUDE_DIR="$PWD/aasdk/include/aasdk" \
  -DAASDK_LIB_DIR="$PWD/build-aasdk-mac/lib/libaasdk.a" \
  -DAAP_PROTOBUF_INCLUDE_DIR="$PWD/build-aasdk-mac/protobuf" \
  -DAAP_PROTOBUF_LIB_DIR="$PWD/build-aasdk-mac/lib/libaap_protobuf.a" \
  -DCMAKE_CXX_FLAGS_INIT="-I$PWD/aasdk/include" \
  -DCMAKE_PREFIX_PATH="$(brew --prefix qt@5);$(brew --prefix boost@1.85);$(brew --prefix protobuf);$(brew --prefix abseil);$(brew --prefix taglib);$(brew --prefix rtaudio);$(brew --prefix util-linux);$(brew --prefix gpsd);$(brew --prefix openssl@3);$(brew --prefix libusb)"

cmake --build build-openauto-mac --target autoapp -j8
```

Likely macOS fixes:

- `Findblkid`/`Findgps` may need explicit
  `-DBLKID_INCLUDE_DIR="$(brew --prefix util-linux)/include/blkid"`,
  `-DGPS_INCLUDE_DIR="$(brew --prefix gpsd)/include"`.
- Static `libaasdk.a` may leave absl symbols unresolved; add the absl
  libraries/targets to the link or link `libprotobuf.dylib` plus absl. Check the
  link command against the aasdk target's `target_link_libraries`.
- Qt5 `QDesktopWidget`/`QApplication` still require a GUI session; capture mode
  uses file sinks, so `QT_QPA_PLATFORM=offscreen` can work, or run with a normal
  window.

## Run on the Mac

Use the same config/capture patch:

```bash
cd openauto-run
sudo env AURIGA_CAPTURE_DIR="$PWD/../captures-mac" \
  QT_QPA_PLATFORM=offscreen \
  ../build-openauto-mac/bin/autoapp
```

On macOS, try without `sudo` first; libusb can open the dongle as the user. If
AOA control transfers fail with permissions, use `sudo` for the test.

Start the stream server locally (it defaults to Pi paths, so pass Mac paths):

```bash
python3 stream/auriga_stream.py \
  --video captures-mac/video.h264 \
  --audio captures-mac/audio-media.wav \
  --fifo /tmp/auriga-in
```

Open `http://localhost:8080` in Brave/Chrome. No SSH tunnel needed on the Mac.
The stream server binds `127.0.0.1`; localhost is a secure context for
WebCodecs.

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
  Linux. The dongle may reset more/less; test with `caffeinate`.
- The dongle's first-session reset is a dongle behaviour; OpenAuto's reconnect
  is the fix. Per-session output files are still needed so a reset does not
  overwrite the previous capture.
- Qt5 Bluetooth availability in Homebrew's `qt@5`; verify before building.
- aasdk macOS static libraries and absl/protobuf link order.
- OpenAuto's `display_name` is still `Crankshaft-NG`; patch to `Auriga`.
- File sinks ignore AA timestamps; A/V sync is best-effort. The long-term fix
  is feeding the stream directly from aasdk callbacks with timestamps.

## Fallback

The Pi stack is committed and working:
`~/auriga/scripts/pi-start.sh`, `scripts/mac-start.sh`, `stream/`,
`patches/openauto-capture.patch`. If the Mac port is blocked, move the dongle
back to the Pi and restart there.
