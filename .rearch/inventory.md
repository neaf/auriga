# Inventory

Date: 2026-10-29
Source: `git ls-files` (72 tracked files) plus no untracked non-ignored files.
Line counts are `wc -l`; binary/config blobs show size in bytes.

External trees, ignored and not inventoried file-by-file:
- `openauto/` — upstream `opencardev/openauto` clone at `4cc739b8`, dirty with
  the tracked patches applied.
- `aasdk-upstream/` — upstream `opencardev/aasdk` clone at `9bf6adf`, dirty with
  AASDK 1.7 + the tracked USB-filter patch.
- `build-aasdk-mac/`, `build-openauto-mac/`, `captures-mac/`, `logs/*.log`,
  `.venv/`, `.serena/` — generated/local.
- Local-only ignored dongle DBs (`btapp.*.db/.bk`, `posttrip/btapp.db.post`)
  are not in git.

## Files

| File | Kind | Lines | Aspect(s) |
|---|---|---:|---|
| `.gitignore` | config | 52 | build-and-tooling |
| `AGENTS.md` | doc | 162 | stream, runtime-orchestration, dongle-hardware |
| `DEVELOPING.md` | doc | 149 | openauto-integration, build-and-tooling |
| `MAC-PORT.md` | doc | 329 | openauto-integration, build-and-tooling |
| `NEXT-SESSION.md` | doc | 89 | openauto-integration, runtime-orchestration, minimal-capture, build-and-tooling |
| `PHONE-APP.md` | doc | 418 | phone-app-design |
| `README.md` | doc | 389 | openauto-integration, stream, runtime-orchestration, dongle-hardware, minimal-capture, phone-app-design, build-and-tooling |
| `RUNBOOK.md` | doc | 306 | openauto-integration, stream, runtime-orchestration, dongle-hardware |
| `capture/CMakeLists.txt` | build | 77 | minimal-capture, build-and-tooling |
| `capture/README.md` | doc | 90 | minimal-capture |
| `capture/src/AudioCapture.cpp` | source | 235 | minimal-capture |
| `capture/src/AudioCapture.hpp` | source | 67 | minimal-capture |
| `capture/src/BluetoothCapture.cpp` | source | 131 | minimal-capture |
| `capture/src/BluetoothCapture.hpp` | source | 51 | minimal-capture |
| `capture/src/CaptureService.hpp` | source | 23 | minimal-capture |
| `capture/src/HeadUnit.cpp` | source | 337 | minimal-capture |
| `capture/src/HeadUnit.hpp` | source | 95 | minimal-capture |
| `capture/src/InputCapture.cpp` | source | 167 | minimal-capture |
| `capture/src/InputCapture.hpp` | source | 58 | minimal-capture |
| `capture/src/Log.hpp` | source | 36 | minimal-capture |
| `capture/src/MicrophoneCapture.cpp` | source | 127 | minimal-capture |
| `capture/src/MicrophoneCapture.hpp` | source | 50 | minimal-capture |
| `capture/src/SensorCapture.cpp` | source | 134 | minimal-capture |
| `capture/src/SensorCapture.hpp` | source | 46 | minimal-capture |
| `capture/src/Usb.cpp` | source | 134 | minimal-capture |
| `capture/src/Usb.hpp` | source | 35 | minimal-capture |
| `capture/src/VideoCapture.cpp` | source | 197 | minimal-capture |
| `capture/src/VideoCapture.hpp` | source | 67 | minimal-capture |
| `capture/src/WavWriter.cpp` | source | 73 | minimal-capture |
| `capture/src/WavWriter.hpp` | source | 32 | minimal-capture |
| `capture/src/WifiProjectionCapture.cpp` | source | 99 | minimal-capture |
| `capture/src/WifiProjectionCapture.hpp` | source | 47 | minimal-capture |
| `capture/src/main.cpp` | source | 239 | minimal-capture |
| `captures/2026-10-28-macos-input.jsonl` | asset (trace) | 1 | stream |
| `captures/2026-10-28-macos-session2-input.jsonl` | asset (trace) | 4 | stream |
| `captures/2026-10-28-session2-input.jsonl` | asset (trace) | 1 | stream |
| `captures/README.md` | doc | 33 | stream |
| `dongle-backup/README.md` | doc | 124 | dongle-hardware |
| `dongle-backup/bt.mac.txt` | config (text) | 1 | dongle-hardware |
| `dongle-backup/ly-AutoLink-A512.orig` | asset | 0 (8 B) | dongle-hardware |
| `dongle-backup/ly_linktype_aa` | asset | 0 (1 B) | dongle-hardware |
| `dongle-backup/videoInfo.car-trip` | asset | 0 (364 B) | dongle-hardware |
| `dongle-backup/videoInfo.galaxy` | asset | 0 (364 B) | dongle-hardware |
| `dongle-backup/videoInfo.galaxy.active` | asset | 0 (364 B) | dongle-hardware |
| `dongle-backup/videoInfo.orig` | asset | 0 (364 B) | dongle-hardware |
| `logs/run-baseline-114525.filtered.log` | generated (tracked sample) | 120 | openauto-integration |
| `openauto-config/openauto-logs.ini` | config | 17 | openauto-integration, build-and-tooling |
| `openauto-config/openauto.ini` | config | 29 | openauto-integration, build-and-tooling |
| `openauto-config/run-mac.sh` | source (script) | 36 | openauto-integration, runtime-orchestration |
| `openauto-config/run.sh` | source (script) | 32 | openauto-integration, runtime-orchestration |
| `openauto-plan.md` | doc | 477 | openauto-integration, dongle-hardware |
| `patches/aasdk-usb-filter.patch` | source (patch) | 101 | openauto-integration, dongle-hardware |
| `patches/openauto-auriga-gps-guard.patch` | source (patch) | 27 | openauto-integration |
| `patches/openauto-auriga-usb-filter.patch` | source (patch) | 42 | openauto-integration, dongle-hardware |
| `patches/openauto-capture.patch` | source (patch) | 1101 | openauto-integration |
| `patches/openauto-macos.patch` | source (patch) | 89 | openauto-integration, build-and-tooling |
| `posttrip/ly-AutoLink-A512.post` | asset | 0 (8 B) | dongle-hardware |
| `posttrip/ly_linktype_aa.post` | asset | 0 (1 B) | dongle-hardware |
| `posttrip/videoInfo.post` | asset | 0 (364 B) | dongle-hardware |
| `scripts/aa-tap.sh` | source (script) | 12 | runtime-orchestration |
| `scripts/aoa_probe.py` | source (script) | 96 | dongle-hardware |
| `scripts/aoa_read.py` | source (script) | 57 | dongle-hardware |
| `scripts/mac-headunit-start.sh` | source (script) | 91 | runtime-orchestration |
| `scripts/mac-headunit-stop.sh` | source (script) | 24 | runtime-orchestration |
| `scripts/mac-start.sh` | source (script) | 27 | runtime-orchestration |
| `scripts/mac-stop.sh` | source (script) | 11 | runtime-orchestration |
| `scripts/pi-start.sh` | source (script) | 60 | runtime-orchestration |
| `scripts/pi-stop.sh` | source (script) | 21 | runtime-orchestration |
| `stream/README.md` | doc | 99 | stream |
| `stream/auriga_stream.py` | source | 423 | stream |
| `stream/web/app.js` | source | 258 | stream |
| `stream/web/index.html` | source | 36 | stream |

## Totals per aspect

Docs are counted in every aspect they discuss, so these totals overlap.

| Aspect | Files | Source+build | Docs/assets | Total |
|---|---:|---:|---:|---:|
| openauto-integration | 16 | 1360 patches + 114 config | 1739 docs + 120 log | 3333 |
| stream | 11 | 717 | 995 | 1712 |
| runtime-orchestration | 13 | 314 | 946 | 1260 |
| dongle-hardware | 18 | 296 | 1459 | 1755 |
| minimal-capture | 26 | 2557 | 568 | 3125 |
| phone-app-design | 2 | 0 | 807 | 807 |
| build-and-tooling | 11 | 332 | 956 | 1288 |

All aspects are below the ~8,000-line split budget.
