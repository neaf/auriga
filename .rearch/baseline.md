# Baseline

Date: 2026-10-29
Branch: `rearch/2026-10-29`
Base tag: `rearch-base` (`bfd7903`)

Host: macOS (darwin), Apple Silicon. The working head-unit path is the Mac.
The Pi is a fallback host and is not reachable from this baseline.

## Build

Run from the repo root. Both are incremental builds of existing ignored trees.

| Command | Result |
|---|---|
| `cmake --build build-aasdk-mac --target aasdk -j8` | PASS (`Built target aasdk`) |
| `cmake --build build-openauto-mac --target autoapp -j8` | PASS (`Built target autoapp`) |

Inputs:
- `aasdk-upstream` at `9bf6adf`, dirty as expected (AASDK 1.7, USB filter,
  protobuf CMake edits).
- `openauto` at `4cc739b8`, dirty as expected (capture + macOS + Auriga
  patches).
- `patches/` is the source of truth; the nested clones are ignored.

## Tests

No automated test suite exists in the repo. No test command to run.

## Static checks

| Command | Result |
|---|---|
| `.venv/bin/python -m py_compile stream/auriga_stream.py scripts/aoa_probe.py scripts/aoa_read.py` | PASS |
| `for f in scripts/*.sh openauto-config/*.sh; do bash -n "$f"; done` | PASS |
| `git -C openauto apply --check --reverse ../patches/openauto-auriga-usb-filter.patch` | PASS |
| `git -C openauto apply --check --reverse ../patches/openauto-auriga-gps-guard.patch` | PASS |
| `git -C aasdk-upstream apply --check --reverse ../patches/aasdk-usb-filter.patch` | PASS |

The `capture/` C++ app is built on the Pi per `capture/README.md`; it is not
part of the macOS build.

## Run

```bash
./scripts/mac-headunit-start.sh   # autoapp + stream server + Brave
./scripts/mac-headunit-stop.sh
```

UI: `http://localhost:8080`; WebSocket: `ws://127.0.0.1:8081`.

## Manual checklist

The user asserted on 2026-10-29 that everything works; these were not re-run in
this session. Every later phase reuses this list.

- M1: Cold start. Dongle in MTP `2717:ff40`, phone BT/Wi-Fi on;
  `mac-headunit-start.sh` switches the dongle to AOA `18d1:2d00` and the phone
  projects.
- M2: During projection the phone stays MTP+ADB `04e8:6860`;
  `adb -s RFGL329J04J shell svc usb getFunctions` returns `mtp`.
- M3: Brave at `http://localhost:8080` shows the live 1280x720 AA UI.
- M4: Canvas taps and `echo 'tap 640 360' > /tmp/auriga-in` change the phone UI.
- M5: Audio is audible after clicking the mute button (48 kHz/16-bit stereo).
- M6: `captures-mac/video.h264` decodes with ffmpeg; `audio-media.wav` is
  non-empty; `input.jsonl` records injected taps.
- M7: `mac-headunit-stop.sh` stops `autoapp` and the stream server; a second
  start refuses to run a duplicate.
- M8: Pi fallback still works: `scripts/pi-start.sh` on the Pi plus
  `scripts/mac-start.sh` on the Mac (SSH tunnel).

## Known environment notes

- `openauto/` and `aasdk-upstream/` are separate ignored git clones, not
  submodules.
- `build-*`, `captures-mac/`, `logs/`, `.venv/`, `.serena/`, and dongle
  credential DBs are ignored.
- The dongle recovery caveat (stale TLS session needs a physical replug) is
  documented in `AGENTS.md` and `DEVELOPING.md`.
