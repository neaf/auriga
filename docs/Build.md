# Build

macOS (Apple Silicon) is the only supported host. Two CMake projects build from
two nested clones: aasdk (`build-aasdk-mac`) and OpenAuto
(`build-openauto-mac`). The root repo tracks `patches/`, `stream/`, `scripts/`
and docs; the nested clones and build directories are ignored.

## Toolchain

| Tool | Version used | Note |
| --- | --- | --- |
| CMake | 4.4.4 | older minimums need `CMAKE_POLICY_VERSION_MINIMUM` |
| Boost | 1.85.0_3 (`brew install boost@1.85`) | required, keg-only |
| Qt | 5.15.19 (`qt@5`) | must include QtConnectivity for `Qt5Bluetooth` |
| protobuf | 36.2 | headers include absl |
| abseil | 20260817.0 | |
| taglib | 2.3.2 | |
| rtaudio | 6.0.1 | not used in capture mode |
| util-linux | 2.42.4 | blkid headers |
| gpsd | 3.27.5 | optional at run time |
| openssl@3 | 3.5.9 | linked into the static aasdk consumer |
| libusb | 1.0.30 | |
| Python | 3.14.8 + `websockets` 17.3 | `.venv` for the stream server |
| ffmpeg / ffprobe | 9.0.2 | verification only |

Qt5 must provide DBus, Multimedia, MultimediaWidgets, Bluetooth and Network:

```bash
ls "$(brew --prefix qt@5)/lib/cmake" | grep -E "Qt5(Bluetooth|Multimedia|Network|DBus)"
```

## Build order

1. aasdk at `9bf6adf` with `patches/aasdk-usb-filter.patch` and two tree edits.
2. OpenAuto at `4cc739b8` with the four OpenAuto patches, in order.
3. The stream server's `.venv`.

### aasdk

Two edits are applied to the nested tree and are not in any patch file:

- `aasdk-upstream/include/aasdk/Version.hpp:22-23`: `AASDK_MINOR = 7` (AA 1.7).
- `aasdk-upstream/protobuf/CMakeLists.txt`: add absl's include directories to
  `aap_protobuf` on Darwin, because protobuf 36 headers include `absl/...`:

```cmake
if(CMAKE_SYSTEM_NAME STREQUAL "Darwin" AND TARGET absl::base)
    target_include_directories(aap_protobuf PUBLIC
        $<TARGET_PROPERTY:absl::base,INTERFACE_INCLUDE_DIRECTORIES>)
endif()
```

Then:

```bash
git -C aasdk-upstream apply "$PWD/patches/aasdk-usb-filter.patch"

cmake -S aasdk-upstream -B build-aasdk-mac \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DSKIP_BUILD_PROTOBUF=ON \
  -DSKIP_BUILD_ABSL=ON \
  -DAASDK_TEST=OFF \
  -DBoost_DIR="$(brew --prefix boost@1.85)/lib/cmake/Boost-1.85.0" \
  -DCMAKE_PREFIX_PATH="$(brew --prefix boost@1.85);$(brew --prefix protobuf);$(brew --prefix abseil);$(brew --prefix openssl@3);$(brew --prefix libusb)"

cmake --build build-aasdk-mac --target aasdk -j8
```

Artifacts: `build-aasdk-mac/lib/libaasdk.a` (~52 MB) and
`build-aasdk-mac/lib/libaap_protobuf.a` (~245 MB). aasdk builds `STATIC` on
Darwin.

### OpenAuto

```bash
git -C openauto apply "$PWD/patches/openauto-capture.patch"
git -C openauto apply "$PWD/patches/openauto-macos.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-usb-filter.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-gps-guard.patch"

cmake -S openauto -B build-openauto-mac \
  -DCMAKE_BUILD_TYPE=Release -DNOPI=ON \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DAASDK_INCLUDE_DIR="$PWD/aasdk-upstream/include/aasdk" \
  -DAASDK_LIB_DIR="$PWD/build-aasdk-mac/lib/libaasdk.a" \
  -DAAP_PROTOBUF_INCLUDE_DIR="$PWD/build-aasdk-mac/protobuf" \
  -DAAP_PROTOBUF_LIB_DIR="$PWD/build-aasdk-mac/lib/libaap_protobuf.a" \
  -DCMAKE_CXX_FLAGS_INIT="-I$PWD/aasdk-upstream/include -I$(brew --prefix abseil)/include -I$(brew --prefix taglib)/include -I$(brew --prefix gpsd)/include" \
  -DBoost_DIR="$(brew --prefix boost@1.85)/lib/cmake/Boost-1.85.0" \
  -DTAGLIB_LIBRARIES="$(brew --prefix taglib)/lib/libtag.dylib" \
  -DTAGLIB_INCLUDE_DIRS="$(brew --prefix taglib)/include/taglib" \
  -DOPENSSL_LIBRARIES="$(brew --prefix openssl@3)/lib/libssl.dylib;$(brew --prefix openssl@3)/lib/libcrypto.dylib" \
  -DCMAKE_EXE_LINKER_FLAGS="$(brew --prefix openssl@3)/lib/libssl.dylib $(brew --prefix openssl@3)/lib/libcrypto.dylib" \
  -DCMAKE_PREFIX_PATH="$(brew --prefix qt@5);$(brew --prefix boost@1.85);$(brew --prefix protobuf);$(brew --prefix abseil);$(brew --prefix taglib);$(brew --prefix rtaudio);$(brew --prefix util-linux);$(brew --prefix gpsd);$(brew --prefix openssl@3);$(brew --prefix libusb)"

cmake --build build-openauto-mac --target autoapp -j8
```

`AASDK_INCLUDE_DIR` must be the `aasdk` subdirectory (one include uses
`<Transport/...>`) and its parent must also be on the include path
(`CMAKE_CXX_FLAGS_INIT`) for `<aasdk/...>`. `-DNOPI=ON` disables the OMX video
backend and selects the plain Qt/capture backends.

Patch order matters: `openauto-capture` then `openauto-macos`, then the two
incremental `auriga-*` patches. The USB-filter patch calls `aurigaCaptureMode()`
from the macOS patch. Patches 2 and 3 both rewrite `App.cpp`; patches 1 and 4
both rewrite `SensorService.cpp`. Apply and verify with absolute paths, because a
relative path is resolved inside the nested clone:

```bash
git -C openauto apply --check --reverse "$PWD/patches/openauto-auriga-usb-filter.patch"
git -C openauto apply --check --reverse "$PWD/patches/openauto-auriga-gps-guard.patch"
git -C aasdk-upstream apply --check --reverse "$PWD/patches/aasdk-usb-filter.patch"
```

## Build quirks

### Boost must be 1.85

Symptom: compile errors on `boost::asio::io_service`.
Cause: Boost 1.92 (the Homebrew default) removed `io_service`; 1.85 still has it.
Workaround: pin `-DBoost_DIR=$(brew --prefix boost@1.85)/lib/cmake/Boost-1.85.0`.
Clear a cache configured against another Boost with `cmake -S ... -B ... '-UBoost_.*'`
before reconfiguring. `boost@1.85` is deprecated by Homebrew but the bottle still
installs; if it disappears, the source needs an `io_context` migration.

### CMake policy minimum

Symptom: a configure error from aasdk's `gitversion.cmake` or another module
that declares an old minimum.
Cause: CMake 4.4.4 rejects compatibility with pre-3.5 policies.
Workaround: `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` on both configure lines.
Both caches carry it.

### taglib links a bare `-ltag`

Symptom: link failure resolving `-ltag`.
Cause: `Findtaglib` appends `-ltag`; macOS has `libtag.dylib`, no `libtag`.
Workaround: override `TAGLIB_LIBRARIES` and `TAGLIB_INCLUDE_DIRS` with the
Homebrew paths (see the configure line).

### absl and gpsd include roots

Symptom: missing `absl/...` or `gps.h` during the OpenAuto compile.
Cause: OpenAuto does not add the generated `aap_protobuf` target's include
properties, nor `GPS_INCLUDE_DIRS`, to its own include list.
Workaround: add `-I$(brew --prefix abseil)/include` and
`-I$(brew --prefix gpsd)/include` in `CMAKE_CXX_FLAGS_INIT`.

### OpenSSL symbols with a static aasdk

Symptom: undefined libssl/libcrypto symbols at the OpenAuto link step.
Cause: `libaasdk.a` is static and does not carry OpenSSL; OpenAuto's link line
ignores its `OPENSSL_LIBRARIES` variable.
Workaround: put both dylibs in `CMAKE_EXE_LINKER_FLAGS`.

### AirPlay Receiver owns TCP 5000

Symptom: a non-capture `autoapp` cannot bind its listener.
Cause: macOS ControlCenter (AirPlay Receiver) listens on TCP 5000; OpenAuto's
AA-over-Wi-Fi listener wants the same port.
Workaround: run in capture mode. `AURIGA_CAPTURE_DIR` makes `App` bind port 0
and skip `startServerSocket()` (`openauto/src/autoapp/App.cpp:42-43,185-188`).
The acceptor is still constructed and listening on an ephemeral port on all
interfaces; it never accepts.

### New sources need a reconfigure

Symptom: a new `.cpp` under `openauto/src` is not compiled.
Cause: OpenAuto collects sources with `file(GLOB_RECURSE)` at configure time.
Workaround: re-run the configure step after adding or removing files.

### `patches/` is incomplete

Symptom: a pristine clone + the documented patches does not compile.
Cause: `patches/openauto-capture.patch` omits the
`IInputDeviceEventHandler.hpp` include that `AurigaInputDevice.cpp` needs, and
the two aasdk edits above are only in the nested tree.
Workaround: add the include and the two aasdk edits after applying patches, or
build from the existing nested trees.
Location: `patches/openauto-capture.patch`; reverse-check of the capture patch
fails on `AurigaInputDevice.cpp`.

## Artifacts

| Path | Content |
| --- | --- |
| `build-aasdk-mac/lib/libaasdk.a` | static aasdk |
| `build-aasdk-mac/lib/libaap_protobuf.a` | static generated protobuf |
| `build-openauto-mac/bin/autoapp` | symlink to the versioned binary |
| `build-openauto-mac/bin/autoapp-2026.10.28+git.4cc739b.dirty` | build of the dirty `4cc739b8` tree; the `.dirty` suffix means the binary matches the tree, not `patches/` |

## Stream server environment

```bash
/opt/homebrew/bin/python3.14 -m venv .venv
.venv/bin/pip install websockets
.venv/bin/python -c "import websockets; print(websockets.__version__)"   # 17.3
```

The start script prefers `$AURIGA_PYTHON`, then `.venv/bin/python`, then bare
`python3`; it exits if `websockets` cannot be imported
(`scripts/mac-headunit-start.sh:14-26`).

## Verification

```bash
cmake --build build-aasdk-mac --target aasdk -j8
cmake --build build-openauto-mac --target autoapp -j8
.venv/bin/python -m py_compile stream/auriga_stream.py scripts/aoa_probe.py scripts/aoa_read.py
for f in scripts/*.sh openauto-config/*.sh; do bash -n "$f"; done
git -C openauto apply --check --reverse "$PWD/patches/openauto-auriga-usb-filter.patch"
git -C openauto apply --check --reverse "$PWD/patches/openauto-auriga-gps-guard.patch"
git -C aasdk-upstream apply --check --reverse "$PWD/patches/aasdk-usb-filter.patch"
```

Build success is `Built target aasdk` and `Built target autoapp`.

Capture verification:

```bash
ffprobe -v error -select_streams v:0 -count_frames \
  -show_entries stream=width,height,profile,level,nb_read_frames \
  -of default=nw=1 captures-mac/video.h264        # 1280x720 Baseline, level 31
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels \
  -of default=nw=1 captures-mac/audio-media.wav   # pcm_s16le, 48000, 2
ffmpeg -loglevel info -i captures-mac/video.h264 -f null - 2>&1 | tail -1
```

Raw H.264 has no container timestamps: `ffprobe` reports
`r_frame_rate=1200000/1`, so frame count is the only usable duration proxy.

There is no automated test suite and no single build script; the commands above
are the full build and check path. Runtime verification of the rig is in
`docs/Android Auto head unit.md`.
