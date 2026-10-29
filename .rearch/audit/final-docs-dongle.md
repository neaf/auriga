# Audit: docs + dongle tools

Scope: the four topic docs, root `README.md`, `AGENTS.md`, the two dongle
diagnostics, the `dongle-backup/` data files, checked against
`.rearch/requirements.md` (DGL, CON, NFR) and against the code they cite.

Headline: every FR-DGL and every CON-* has a doc or code anchor. The new
`docs/` set is accurate against the tree except for line-reference drift and two
`videoInfo` byte claims. `README.md` is still the Pi-era document and
contradicts `docs/` on host, capture path, identity strings and the
`videoInfo.galaxy` status. Four NFRs marked "not satisfied" in the requirements
are implemented in code.

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| `README.md` | 377 | yes |
| `AGENTS.md` | 166 | yes |
| `docs/AutoLink A512 dongle.md` | 233 | yes |
| `docs/Android Auto head unit.md` | 404 | yes |
| `docs/Stream protocol.md` | 268 | yes |
| `docs/Build.md` | 293 | yes |
| `tools/aoa_probe.py` | 96 | yes |
| `tools/aoa_read.py` | 57 | yes |
| `dongle-backup/` (11 files + `README.md`) | data | all sizes, hashes, offsets inspected |

Extra reads for claim checks: `openauto/src/autoapp/{autoapp,App}.cpp`,
`Service/ServiceFactory.cpp`, `Service/AndroidAutoEntity.cpp`,
`Projection/AurigaSession.{cpp,hpp}`, `Projection/AurigaWriter.hpp`,
`Projection/Auriga{Video,Audio}Output.cpp`, `Projection/AurigaInputDevice.cpp`,
`Projection/AurigaAudioInput.cpp`, `Projection/DummyBluetoothDevice.cpp`,
`Service/{Pinger.cpp,AndroidAutoEntityFactory.cpp,InputSource/InputSourceService.cpp}`,
`aasdk-upstream/src/USB/{USBHub,AccessoryModeQueryChain,AccessoryModeQueryFactory,AccessoryModeProtocolVersionQuery}.cpp`,
`aasdk-upstream/include/aasdk/{Version.hpp,USB/AccessoryModeSendStringType.hpp}`,
all 7 `patches/*.patch`, `scripts/{auriga.sh,build.sh}`,
`openauto-config/{run.sh,openauto.ini}`, `stream/{server.py,auriga_stream.py,README.md}`,
`stream/lib/*.py`, `stream/web/app.js`, `captures/2026-10-28-macos-session2-video.h264`.

Commands run: `.venv/bin/python -m unittest discover -s tests` → 94 tests OK;
`py_compile` on both tools → OK; `ffprobe`/byte scans on the capture and the
`dongle-backup` files; `brew list --versions` for the toolchain table.

## Functional behavior
- F1: Only the dongle `2717:ff40` is sent the AOA chain, and `18d1:2d01` is refused as a target. `aasdk-upstream/src/USB/USBHub.cpp:84-98,115-125`; filter introduced by `patches/aasdk-usb-filter.patch:55-88`; wired at `openauto/src/autoapp/autoapp.cpp:245-246`. Maps FR-DGL-01/02, CON-DGL-01. Status: active.
- F2: The dongle exposes an 8-slot flat MTP config store that only manual `mtp-*` operations touch; no repo code reads or writes it. `docs/AutoLink A512 dongle.md:79-100`; confirmed: no `mtp-` call in any tracked script except `dongle-backup/README.md`. Status: active (manual procedure).
- F3: `videoInfo` is 364 B, magic `03 07 24 20`, LE width 1280 `0x04` / height 720 `0x08`, SPS 17 B `0x16`, PPS `0x2b`, phone address `0x54`, 10-byte head-unit name `0x68`, session tag `0x72`, u32 `0x168`. Verified byte-for-byte on `videoInfo.orig`, `.car-trip`, `.galaxy`, `.galaxy.active`. `docs/AutoLink A512 dongle.md:102-126`. Maps FR-DGL-04. Status: active.
- F4: `videoInfo.galaxy` and `.active` are invalid (width/height/start codes/SPS/PPS/tag all zero) and must not be restored; `.orig` and `.car-trip` are the only restorable snapshots. `docs/AutoLink A512 dongle.md:128-142`; measured. Status: active.
- F5: `btapp.db` has two forms, 207 B (7 × 29-byte blocks at `0x08,0x25,0x42,0x5f,0x7c,0x99,0xb6`, trailer `00 42 54 4c f3`) and 33 B (one block, trailer `00 42 54 0a 53`); recovery is delete both files, cold replug, re-pair. `docs/AutoLink A512 dongle.md:148-166,168-178`; layout verified on `btapp.db.orig`/`.galaxy-fresh`. Maps FR-DGL-05. Status: active.
- F6: `*.db`/`*.bk` backups are gitignored, so a fresh clone has no pairing DB and no test detects a stale key. `.gitignore:40-46`; `docs/AutoLink A512 dongle.md:144-146`. Status: active.
- F7: CarPlay `05ac:12a8` is a latch with no software path out; `handleDevice` returns silently for it. `aasdk-upstream/src/USB/USBHub.cpp:89-98,115-117`; `docs/AutoLink A512 dongle.md:191-200`. Maps FR-DGL-06, Q8. Status: documented note, no code.
- F8: Dongle MTP↔AOA re-enumerates on the order of tens of seconds, so the probe retries for 90 s at 0.25 s and `autoapp` simply waits for the next arrival. `tools/aoa_probe.py:4-6,86-92`; `openauto/src/autoapp/App.cpp:175-186`. Maps CON-DGL-03. Status: active, interval unverified.
- F9: `tools/aoa_probe.py` has `probe` (GET_PROTOCOL only) and `start` (6 SEND_STRING + ACCESSORY_START) modes against `2717:ff40`; `tools/aoa_read.py` claims interface 0 and prints 512-byte bulk-IN reads for 15 s. `tools/aoa_probe.py:20-92`; `tools/aoa_read.py:10-53`. Status: active diagnostics.
- F10: AA 1.7 is carried by `patches/aasdk-version-absl.patch` (`AASDK_MINOR = 7` at `aasdk-upstream/include/aasdk/Version.hpp:27`) plus the Darwin absl include for `aap_protobuf`. Maps FR-DGL-03, FR-BLD-07. Status: active.
- F11: The docs set is the only place the dongle frame layout and recovery recipes exist; nothing enforces them ("nothing validates the file; every safeguard is prose"). `docs/AutoLink A512 dongle.md:225-233`. Status: active gap.

## External facts and quirks
- X1: The AOA string set actually sent by the head unit is aasdk's, not the probe's: `Android` / `Android Auto` / `Android Auto` / `2.0.1` / `https://f1xstudio.com` / `HU-AAAAAA001`, indices 0-5 via `AccessoryModeSendStringType`. `aasdk-upstream/src/USB/AccessoryModeQueryFactory.cpp:43-64`; `include/aasdk/USB/AccessoryModeSendStringType.hpp:27-34`. `docs/AutoLink A512 dongle.md:36-51` is correct. Source: code.
- X2: Dongle reports AOA v2 and AA `256.1792`; aasdk accepts AOA 1 or 2 (`AccessoryModeProtocolVersionQuery.cpp:59`) and the phone-visible AA version is `AASDK_MAJOR/MINOR` 1.7. Source: code + log. Doc marks the `[2,0]` value `unverified` because no probe output is stored.
- X3: `videoInfo` SPS decodes to Baseline **3.2** (level_idc `0x20`) while the captured AA stream is Baseline **3.1** (`ffprobe level=31`). Two different facts, both true; `docs/AutoLink A512 dongle.md:115` vs `docs/Android Auto head unit.md:339`. Source: byte scan + ffprobe.
- X4: The 22 s idle re-enumeration is still unverified after the BT DB reset; the only evidence is the tool docstring. `tools/aoa_probe.py:4-6`; `docs/AutoLink A512 dongle.md:202-210`. Source: unverified.
- X5: BT/Wi-Fi identity (`ED:A2:A4:94:4F:B8`, BSSID `e8:5c:b1:b5:c6:41`, 5180 MHz, WPA2 `12345678`, class `0x200420`) is marked `unverified` throughout; the BT address is backed by `dongle-backup/bt.mac.txt` (13 B = 12 B + newline), nothing backs the rest. `docs/AutoLink A512 dongle.md:212-223`.
- X6: The `btapp` trailer is not a CRC of the body under nine variants, so hand-patched DBs fail semantically (no advertising) instead of being rejected. `docs/AutoLink A512 dongle.md:160-166`. Source: doc claim, not re-run here.
- X7: macOS has no `lsusb`, so `tools/aoa_probe.py:72` cannot work on the only supported host. Compare `AGENTS.md:50`, which uses `ioreg -p IOUSB`. Source: code + host.
- X8: `pyusb` is installed only in `.venv`; system `python3` is 3.9.6 without it, and both tools use `#!/usr/bin/env python3`. `docs/Build.md:291-292` says "they need `pyusb`" but not how to get it. Source: host check.
- X9: The running head unit (autoapp 29079, started 07:41) predates the 09:37 build, so `captures-mac/` still holds flat `video.h264`/`audio-*.wav`/`input.jsonl` and no `current` pointer. Every "verify it is working" command that reads `captures-mac/current/...` currently fails. Source: process list + directory listing.
- X10: The four-way patch coupling is real: patch 1 and 4 both rewrite `SensorService.cpp`, patches 2 and 3 both rewrite `App.cpp`, and 2/3 call `projection::captureModeEnabled()` defined by 1. `docs/Android Auto head unit.md:27-32`; confirmed from the patch headers. Source: code.
- X11: Toolchain table in `docs/Build.md:15-29` is exact on this host (CMake 4.4.4, Boost 1.85.0_3, Qt 5.15.19, protobuf 36.2, abseil 20260817.0, taglib 2.3.2, rtaudio 6.0.1, util-linux 2.42.4, gpsd 3.27.5, openssl@3 3.5.9, libusb 1.0.30, websockets 17.3), and the artifact sizes (`docs/Build.md:109-110`) match (51,898,688 B / 245,206,744 B).

## Doc and code inconsistencies
- D1: `README.md:3-5,12-27` says the host is a Raspberry Pi 3B with `captures/`; `docs/Build.md:3` and `scripts/auriga.sh:177` say macOS only.
- D2: `README.md:68` tells the user to run `scripts/mac-headunit-start.sh` / `mac-headunit-stop.sh`; both are deleted, `scripts/` holds only `auriga.sh` and `build.sh`.
- D3: `README.md:25,264-301,330-331` presents `capture/` as a live component; FR-CAP-01..05 are dropped (Q7).
- D4: `README.md:322-326,340-341` sends the reader to `PHONE-APP.md`; FR-PHONE-01..04 are dropped (Q9).
- D5: `README.md:92-93,120-137` describes Pi 4/5 forwarding and USB-host limits; FR-RUN-05 (Pi fallback) is dropped.
- D6: `README.md:48-51` cites `scripts/aa-tap.sh` and `captures/2026-10-28-session2-*`; the tap script is deleted and captures are per-session now.
- D7: `README.md:188` calls `dongle-backup/videoInfo.galaxy` the "current active config"; `docs/AutoLink A512 dongle.md:134` and the bytes show it is invalid (zero width, height, SPS, PPS, tag) and must not be restored.
- D8: `README.md:236-237` quotes identity strings `Auriga` / `Auriga Pi Capture` / `Android Auto capture head unit` / `1.0` / empty URI / `auriga-pi`; neither sender uses that set — `accessory strings` at `aasdk-upstream/src/USB/AccessoryModeQueryFactory.cpp:43-64` and `tools/aoa_probe.py:30-35` (`Auriga` / `Auriga Pi Headunit` / `Auriga AA capture` / `1.0` / `https://auriga.invalid` / `auriga-pi`).
- D9: `README.md:239` names `aasdk/include/aasdk/Version.hpp`; the tree is `aasdk-upstream/include/aasdk/Version.hpp:27`.
- D10: `docs/Android Auto head unit.md:400` verifies `captures-mac/video.h264`; the capture contract at `:117-126` (and `stream/auriga_stream.py:23-26`) is `<capture-dir>/current/session-<id>/video.h264`. `docs/Build.md:279` was repointed, this one was not.
- D11: `docs/Android Auto head unit.md:243` puts the Bluetooth-service registration at `ServiceFactory.cpp:115-125`; the branch is `ServiceFactory.cpp:141-150`.
- D12: `docs/Android Auto head unit.md:239` puts the touch geometry at `ServiceFactory.cpp:149-152`; the mapping is `ServiceFactory.cpp:173-175` (via `configuredVideoGeometry`, `:71-95`).
- D13: `docs/Android Auto head unit.md:59` and `docs/Build.md:83` cite `include/aasdk/Version.hpp:22-23`; `AASDK_MAJOR`/`MINOR` are at `:26-27`.
- D14: `docs/Stream protocol.md:16` cites `stream/server.py:495` for the HTTP bind (the call is `:496`); `:76` cites `:327-329` for the stale-offset guard (comment `:328-330`, guard `:331`).
- D15: `docs/Android Auto head unit.md:276` bounds the sensor service at `SensorService.cpp:30-48,238-260`; the night-mode re-read is `:233` and the 250 ms timer is `:264`.
- D16: `docs/Android Auto head unit.md:283` cites `DummyBluetoothDevice.cpp:30-42` for `isAvailable()`; it is `:42-45` (`isPaired` `:32-35`, address `:37-40`).
- D17: `docs/Android Auto head unit.md:129-130` says "the four files of one entity"; the same doc lists six at `:117-126` (video, three WAVs, `input.jsonl`, `manifest.json`).
- D18: `docs/AutoLink A512 dongle.md:124` says `videoInfo.car-trip` differs from `.orig` in "6 SPS bytes (`0x1e..0x23`), the PPS level byte and the `0x0c` field"; the diff is 4 SPS bytes at `0x1f-0x22`, the PPS byte at `0x2e`, `0x0c`, the 10-byte name `0x68-0x71` and the u32 at `0x168`.
- D19: `docs/AutoLink A512 dongle.md:113` labels offset `0x10` a u32 holding `0x815`; it is a 2-byte LE value `15 08` — the start code at `0x12` follows immediately.
- D20: `docs/AutoLink A512 dongle.md:81` says "Eight flat files"; the table at `:83-92` already has `btapp.bk` absent, i.e. 7 on the device today.
- D21: `docs/AutoLink A512 dongle.md:178,233` route the recovery and validation procedures to `dongle-backup/README.md`, which this stage deletes.
- D22: `docs/AutoLink A512 dongle.md:105,133,142` describe `posttrip/` (4 byte-identical duplicates); `docs-plan.md` gives it no fate.
- D23: `AGENTS.md:124` points at `stream/README.md` for "the full protocol and client behavior"; that file is to be folded into `docs/Stream protocol.md`, and its own title/architecture are Pi-era ("live Mac client for the Pi head unit", SSH tunnel diagram, `stream/README.md:1-31`).
- D24: `docs/Build.md:236-237` names the built artifact `autoapp-2026.10.28+git.4cc739b.dirty`; the current symlink points at `autoapp-2026.10.29+git.4cc739b.dirty` (both exist).
- D25: `README.md:104` hardcodes `cd /Users/tomaszwerbicki/dev/auriga`.
- D26: Requirements evidence pointers that no longer resolve: FR-DGL-01 → `README.md:154-155` (that is the CarPlay paragraph; the MTP→AOA fact is `README.md:18`); FR-DGL-03 → `README.md:160` (table ends at `:150`; the AA version row is `:149`); FR-DGL-05 → `RUNBOOK.md:162-182` (file deleted this stage; the same content is `README.md:215-231`, `docs/AutoLink A512 dongle.md:168-178`); CON-DGL-01 → `AGENTS.md:59-73` (table `:57-64`, invariants `:127-140`); CON-DGL-02 → `README.md:159` (identity table `:141-150`); NFR-03 → `AGENTS.md:119-121` (actual `:117-119`); NFR-08 → `AGENTS.md:124` (actual `:122`).
- D27: Requirements marks NFR-01, NFR-05, NFR-07, NFR-08 "not satisfied"; the code now implements all four: ACK before `write()` with a bounded queue (`VideoMediaSinkService.cpp:180-197`, `AurigaWriter.hpp:76-115`), `SEGMENT_LIMIT`/`KEEP_SESSIONS` (`AurigaSession.hpp:40-42`), `wait_port` (`scripts/auriga.sh:99-108,205`), and the `.auriga.lock` pair check (`scripts/auriga.sh:52-88,182-193`). `docs/Android Auto head unit.md:309-326,368-387` already states them as present.

## Assumptions to revalidate
- A1: "The dongle re-enumerates every ~22 s." Baked into `tools/aoa_probe.py:4-6` (90 s retry budget) and `docs/AutoLink A512 dongle.md:206`. If the interval is longer or the dongle parks in AOA, the probe times out after 90 s and the doc's "de-facto discovery watchdog" framing is wrong. No measurement since the BT DB reset.
- A2: "The 207-byte DB is stale and the 33-byte `btapp.db.galaxy-fresh` is current." Baked into `docs/AutoLink A512 dongle.md:136,144-146` and the safety rule `AGENTS.md:144-146`. Any re-pair since 2026-10-28 silently invalidates the only backup; nothing detects it.
- A3: "The 33-byte form is a complete replacement for the two-record form." `docs/AutoLink A512 dongle.md:165-166` marks it `unverified`; if false, a re-pair drops a second phone.
- A4: "`docs/` line references stay valid." Every claim cites `file:line`; D11-D16 show the drift already accrued in one phase. Once `patches/` or the nested trees are regenerated, more will rot.
- A5: "`dongle-backup/README.md` can be deleted after folding." The doc already points at it for the `mtp-*` command sequence (`docs/AutoLink A512 dongle.md:94-97,178,233`); fold the commands, not just the facts, or the procedures become prose with no executable steps.
- A6: "`scripts/auriga.sh` is the only runtime entry point." True in `scripts/`, but `README.md:68,115` and `stream/README.md` still name removed scripts; a reader following README hits `No such file`.
- A7: "The dongle is stateless enough to reconfigure from `dongle-backup/`." `docs/AutoLink A512 dongle.md:225-233` says nothing validates `videoInfo`; the invalid `.galaxy` snapshot in the same directory is the counter-example.

## Bugs
- B1 [medium]: `tools/aoa_probe.py:71-72` shells out to `lsusb`, which does not exist on macOS, and the surrounding `except usb.core.USBError` does not catch `FileNotFoundError`. Scenario: `sudo .venv/bin/python tools/aoa_probe.py start` on the Mac → the dongle is already switched to AOA, then the script dies with a traceback instead of reporting the new ID.
- B2 [medium]: `tools/aoa_read.py:25,51` assumes `claim_interface` succeeds; a `USBError` (autoapp holding the dongle, or permissions) is uncaught and prints no diagnosis. Scenario: run it while `autoapp` owns `18d1:2d00` → traceback, no hint that the head unit must be stopped.
- B3 [low]: `tools/aoa_read.py:46` treats `errno == 110` (Linux `ETIMEDOUT`) as the timeout; on Darwin pyusb raises with `errno 60`, so every idle 500 ms read falls into the error branch and prints plus sleeps 0.5 s, shrinking the useful window.
- B4 [low]: `tools/aoa_probe.py:85,54` accepts any argument as "probe": `aoa_probe.py strat` silently runs GET_PROTOCOL only, no error.
- B5 [low]: `scripts/auriga.sh:263-264` deletes `/tmp/auriga-mac-{autoapp,stream,caffeinate}.pid` and `/tmp/auriga-fifo-writer.pid`; nothing in the repo creates those files any more (leftover of the deleted `mac-headunit-stop.sh`).
- B6 [medium]: `docs/Android Auto head unit.md:392-401` and `AGENTS.md:54` verify `captures-mac/video.h264` or `captures-mac/current/...`; with the deployed flat-file capture (X9) the first path does not exist and the second has no `current`, so the documented verification step fails with no explanation.

## Dead code, leftovers, stale comments
- L1: `README.md` — the whole Pi/`capture/`/`PHONE-APP.md`/`mac-headunit-*` narrative (see D1-D9); rewrite target per `.rearch/docs-plan.md:12`.
- L2: repo root `btapp.db.galaxy`, `btapp.db.galaxy2`, `btapp.bk.galaxy`, `btapp.bk.galaxy2` — four 207-byte link-key DBs outside `dongle-backup/`, gitignored (`/.gitignore:47`), mentioned by no doc. Credential material in an undocumented location.
- L3: `tools/aoa_probe.py:4-6` docstring keeps the unverified 22 s claim and the Linux-only `lsusb` step (`:71-72`).
- L4: `tools/aoa_read.py:33-38` finds an OUT endpoint only to print it; no write path, so the "listen only" tool can never complete a handshake and prints ciphertext.
- L5: `auriga.sh:263-264` stale pid-file cleanup (B5).
- L6: `stream/README.md` — duplicate protocol doc with a Pi-era title, tunnel diagram and "the Pi remains the head unit" (`:1-31`); superseded by `docs/Stream protocol.md`.
- L7: `dongle-backup/README.md` (5,666 B) — deleted this stage, still cited by `docs/AutoLink A512 dongle.md:178,233` and `AGENTS.md:145`.
- L8: `capture/` (dropped Q7) still on disk with its own `README.md:1-75`; `README.md:25,264-301` still describes it.
- L9: `posttrip/` — 4 files byte-identical to `dongle-backup/` copies (`videoInfo.post` == `videoInfo.car-trip`, sha256 `325f2719…`; `btapp.db.post` == `btapp.db.orig`, `4023b49d…`), no stated owner.

## Improvement areas
- I1: Rewrite `README.md` to the target set in `.rearch/docs-plan.md:30` (what it is, quick start, build/run/test, doc pointers). It is the highest-traffic entry point and currently teaches the deleted runtime and the dropped `capture/` branch; every stale path in D1-D9 disappears with it.
- I2: Cut `AGENTS.md` from 166 to the planned <60 lines: keep start/stop/verify, USB invariants, safety; replace the duplicated protocol block (`AGENTS.md:99-125`) with a pointer to `docs/Stream protocol.md`, and add the missing `scripts/build.sh` and test commands.
- I3: Fold the executable `mtp-*` procedure into `docs/AutoLink A512 dongle.md` before deleting `dongle-backup/README.md`; today `docs/AutoLink A512 dongle.md:94-97` names the tools but not the sequence or the "stage under the remote basename" trap.
- I4: Replace `file:line` evidence with section anchors in requirements/docs where the target file is being rewritten (`README.md`, `AGENTS.md`); D26 is the current cost (7 of 14 DGL/CON pointers no longer resolve).
- I5: Give the tools a host-correct device listing (`ioreg -p IOUSB -l -w 0`), a `--help`, argument validation (`B4`), and a documented "run with `.venv/bin/python`, stop the head unit first" precondition; today `docs/Build.md:291-292` gives one half-sentence.
- I6: Turn the `videoInfo` validation list at `docs/AutoLink A512 dongle.md:230-232` into a check the procedure runs (magic, width, height, start code, PPS, phone address). It is the only safeguard against the invalid `.galaxy` snapshot being restored, and it exists only as prose.
- I7: Pin CON-DGL-02 and CON-DGL-03 with one stored artifact each (an `ioreg`/`system_profiler` capture for the BT/Wi-Fi identity and a timestamped MTP arrival log for the 22 s interval), or drop the numbers. Ten of the dongle facts are `unverified` today because no capture is stored.
- I8: Delete `posttrip/` and `stream/README.md` (exact duplicates / folded), and move the four root `btapp.*.galaxy*` credential DBs out of the repo.

## Interfaces
- Exposes: the four topic docs as the citable fact base (`docs/AutoLink A512 dongle.md` for USB IDs, `videoInfo`/`btapp.db` layouts, recovery; `docs/Android Auto head unit.md` for the capture contract and AA session behavior; `docs/Stream protocol.md` for the wire protocol; `docs/Build.md` for the build); `AGENTS.md` as the operator/agent contract; `tools/aoa_probe.py {probe|start}` and `tools/aoa_read.py` as CLI diagnostics with no arguments beyond the mode; `dongle-backup/*` as the only restorable dongle state (`videoInfo.orig`, `videoInfo.car-trip`, `btapp.db.galaxy-fresh`).
- Consumes: `openauto/` and `aasdk-upstream/` line numbers (every code citation); `patches/*.patch` for the filter/version/identity claims; the capture layout `<capture-dir>/current` + `manifest.json` + `session-<id>/` (`AurigaSession.cpp:107-233`); `scripts/auriga.sh` / `scripts/build.sh` behavior; the stream server's wire format for `docs/Stream protocol.md`.
- Threading: none. Docs are static. `tools/aoa_probe.py` is single-threaded, 0.25 s retry for up to 90 s; `tools/aoa_read.py` blocks on a 500 ms USB read for 15 s. Both contend with `autoapp` for the dongle interface and fail if it holds it.

## Open questions for the user
- Q1: Is `posttrip/` kept? Its 4 files are byte-identical to `dongle-backup/` copies and no doc assigns it a fate.
- Q2: Do the credential DBs (`btapp.db*`, `btapp.bk*`, incl. the 4 stray files at the repo root) stay in a gitignored in-repo directory, or move to an out-of-repo secret store? A fresh clone has no current link key either way.
- Q3: Are `tools/aoa_probe.py` / `tools/aoa_read.py` worth keeping, given the macOS host, `.venv`-only `pyusb`, and that both break while the head unit runs?
- Q4: After folding, is `dongle-backup/README.md` deleted outright, or kept as the MTP command reference (the topic doc currently delegates to it in two places)?
