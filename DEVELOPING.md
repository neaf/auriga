# DEVELOPING.md — changing the Auriga package

This file is for changing the head-unit stack itself. For running and
integrating the package, see [`AGENTS.md`](AGENTS.md).

## Architecture

```
phone --BT/WiFi--> AutoLink A512 dongle --USB AOA--> autoapp (OpenAuto)
                                                        |
                                           captures-mac/current -> session-<id>/
                                           video.h264, audio-*.wav, input.jsonl
                                                        |
                                              auriga_stream.py
                                              HTTP 8080 / WS 8081
                                                        |
                                          Brave (WebCodecs + WebAudio)
                                                        |
                                          tap JSON -> /tmp/auriga-in
```

The dongle is an AA relay. OpenAuto is the proven head-unit implementation;
the minimal `capture/` app is not the working stack. The Mac path removes the
Pi and the SSH tunnel.

## Source of truth

- The root repo tracks docs, scripts, `stream/`, and `patches/`.
- `openauto/` and `aasdk-upstream/` are **separate git clones**, ignored by the
  root repo. Their working trees are expected to be patched/dirty.
- **`patches/` is the source of truth** for changes to those clones. A clean
  rebuild applies the patches; do not rely on the nested working trees being
  clean or present.
- Build outputs (`build-aasdk-mac/`, `build-openauto-mac/`) and runtime data
  (`captures-mac/`, `logs/`) are ignored.

## Current local changes

| Area | File | Change |
| --- | --- | --- |
| OpenAuto | `include/.../Auriga*`, `src/autoapp/Projection/Auriga*`, `Service/ServiceFactory.cpp`, `Service/MediaSink/*` | capture sinks, session manager, writer queue, input device, silent mic, capture services and the one capture-mode predicate. Patch: `patches/openauto-capture.patch`. |
| OpenAuto | `src/autoapp/App.cpp`, `UI/SettingsWindow.cpp` | ephemeral TCP port and no `startServerSocket()` in capture mode, macOS Bluetooth lister fix. Patch: `patches/openauto-macos.patch`. |
| OpenAuto | `src/autoapp/autoapp.cpp`, `App.cpp` | Pass `0x2717, 0xFF40` to `USBHub`; skip `enumerateDevices()` in capture mode. Patch: `patches/openauto-auriga-usb-filter.patch`. |
| OpenAuto | `src/autoapp/Service/Sensor/SensorService.cpp` | Call `gps_read()` only after a successful `gps_open()`; prevents intermittent `gps_shm_read` segfaults without GPSD. Patch: `patches/openauto-auriga-gps-guard.patch`. |
| OpenAuto | `src/autoapp/Service/AndroidAutoEntity.cpp` | AA identity `Auriga` / `Auriga` / `Auriga`. Patch: `patches/openauto-auriga-identity.patch`. |
| aasdk | `include/aasdk/USB/USBHub.hpp`, `src/USB/USBHub.cpp` | Optional accessory-source VID/PID; check the descriptor before opening; only AOA-switch the configured source; ignore AOA+ADB phones when filtering. Patch: `patches/aasdk-usb-filter.patch`. |
| aasdk | `include/aasdk/Version.hpp`, `protobuf/CMakeLists.txt` | AA protocol 1.7 and the absl include path for `aap_protobuf`. Patch: `patches/aasdk-version-absl.patch`. |

Do **not** reintroduce `LIBUSB_HOTPLUG_MATCH_ANY` + an AOA switch for every
non-AOAP device. That is what switched the development phone into accessory
mode and launched Android Auto's USB preflight error.

## Build (macOS)

Full prerequisites and the exact configure lines are in
[`docs/Build.md`](docs/Build.md). Incremental builds:

```bash
cmake --build build-aasdk-mac --target aasdk -j8
cmake --build build-openauto-mac --target autoapp -j8
```

Patch order for a fresh tree:

```bash
# aasdk-upstream
git -C aasdk-upstream apply /path/to/auriga/patches/aasdk-usb-filter.patch
git -C aasdk-upstream apply /path/to/auriga/patches/aasdk-version-absl.patch

# openauto at 4cc739b8
git -C openauto apply /path/to/auriga/patches/openauto-capture.patch
git -C openauto apply /path/to/auriga/patches/openauto-macos.patch
git -C openauto apply /path/to/auriga/patches/openauto-auriga-usb-filter.patch
git -C openauto apply /path/to/auriga/patches/openauto-auriga-gps-guard.patch
git -C openauto apply /path/to/auriga/patches/openauto-auriga-identity.patch
```

The two `openauto-auriga-*` patches are **incremental**: they assume the
capture and macOS patches are already applied. Verify a patch against the
current working tree with:

```bash
git -C openauto apply --check --reverse patches/openauto-auriga-usb-filter.patch
git -C aasdk-upstream apply --check --reverse patches/aasdk-version-absl.patch
```

`scripts/build.sh` applies all seven to fresh clones and builds both targets;
run it after changing a patch.

## Editing workflow

1. Edit the nested `openauto/` or `aasdk-upstream/` working tree.
2. Rebuild aasdk if its headers/sources changed, then relink OpenAuto.
3. Restart and verify (see checklist below).
4. Regenerate the corresponding patch in `patches/`.
5. Update `docs/Android Auto head unit.md` or this file if behavior or the
   patch order changed.
6. Commit the **root repo** (nested clones are ignored), including the patch
   and docs.

Regenerate the aasdk patches:

```bash
git -C aasdk-upstream diff -- include/aasdk/USB/USBHub.hpp src/USB/USBHub.cpp \
  > patches/aasdk-usb-filter.patch
git -C aasdk-upstream diff -- include/aasdk/Version.hpp protobuf/CMakeLists.txt \
  > patches/aasdk-version-absl.patch
```

For the incremental OpenAuto patches, diff against the same files with the
base patches applied but the new change reverted, so the resulting patch
applies on top of `openauto-capture.patch` + `openauto-macos.patch`. Check it
with `git -C openauto apply --check --reverse`.

## Verification checklist

Before reporting a package change as done:

```bash
cmake --build build-aasdk-mac --target aasdk -j8
cmake --build build-openauto-mac --target autoapp -j8

./scripts/auriga.sh stop
./scripts/auriga.sh start
./scripts/auriga.sh status

pgrep -fl "autoapp|auriga_stream"
adb -s RFGL329J04J shell svc usb getFunctions   # expect: mtp
ioreg -p IOUSB -l -w 0 | grep -E 'o (AutoLink|SAMSUNG_Android)@|"idProduct" = (26720|11520|11521|65344)'
tail -20 "$(ls -t logs/openauto-mac-*.log | head -1)"   # Version Received + pings
ffmpeg -loglevel info -i captures-mac/current/video.h264 -f null - 2>&1 | tail -1
```

Expected: phone `04e8:6860` (MTP+ADB), dongle `18d1:2d00` (AOA), at least one
`Version Received: 256.1792`, pings, and growing video frames. Extract a frame
or check Brave to confirm the UI.

If the first AA entity fails with a stale TLS session, the dongle can stay in
AOA and `autoapp` waits at `Waiting for device...`. A `libusb` reset does not
fix it; the dongle needs a physical replug (cold boot to MTP). Ask the user.

## Commit hygiene

- Commit the root repo; do not commit nested clones, build outputs,
  `captures-mac/`, `logs/`, `.venv/`, `.serena/`, or dongle DBs.
- Keep `patches/` and the docs in sync with the code.
- Do not include secrets, dongle link keys, or credential databases.
- Report the exact build/test commands and their result.

## Known internal issues / next steps

- The first AA entity can die with `AASDK Error 10` either during setup or right
  after the channels start; OpenAuto reconnects and the next session is stable.
  The cause is `unverified` — see
  [`docs/Android Auto head unit.md`](docs/Android%20Auto%20head%20unit.md)
  (first AA entity section).
- File sinks ignore AA timestamps; streamed A/V is not sample-synced.
- Retention keeps five sessions; a rotated segment's bytes are discarded.
- The live rig may still be running an older `autoapp`/stream build; check
  `./scripts/auriga.sh status` before believing a code change is deployed.
