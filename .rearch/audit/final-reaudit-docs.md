# Audit: final re-audit — docs + requirements traceability

Tree at `00b5be6` (phase 8 "fix final audit findings"), working tree clean.
Inputs: `.rearch/requirements.md`, `.rearch/audit/final-docs-dongle.md`,
`.rearch/audit/final-runtime-build.md`.

Headline: every kept FR now resolves to code or a doc fact; all prior
`file:line` drift in the four topic docs is fixed (anchors + symbols replace the
drifting numbers). `README.md` is **not** rewritten and still carries live
contradictions and dropped paths; `.rearch/phases.md:246-248` and
`.rearch/deviations.md:286-292` claim its contradictions are "already fixed" —
false. Three factual defects remain inside the topic docs: the `AASDK Error 10`
narrative contradicts the only stored log, `videoInfo.car-trip`'s SPS diff range
is still wrong, and two dongle-doc offsets/state sentences are wrong.

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| `README.md` | 379 | yes |
| `AGENTS.md` | 166 | yes |
| `DEVELOPING.md` | 157 | yes |
| `docs/AutoLink A512 dongle.md` | 255 | yes |
| `docs/Android Auto head unit.md` | 419 | yes |
| `docs/Stream protocol.md` | 264 | yes |
| `docs/Build.md` | 302 | yes |
| `.rearch/requirements.md` | 353 | yes |
| `dongle-backup/README.md` | 124 | yes |
| Total | 2419 | |

Cross-check reads (claim verification, not full audits): `openauto/src/autoapp/{autoapp,App}.cpp`,
`Service/{ServiceFactory,AndroidAutoEntity,AndroidAutoEntityFactory,Pinger}.cpp`,
`Service/{Sensor/SensorService,Bluetooth/BluetoothService,InputSource/InputSourceService,MediaSink/VideoMediaSinkService,MediaSink/AudioMediaSinkService}.cpp`,
`Projection/{AurigaSession.cpp,AurigaSession.hpp,AurigaWriter.hpp,AurigaVideoOutput.cpp,AurigaAudioOutput.cpp,AurigaAudioInput.cpp,AurigaInputDevice.cpp,DummyBluetoothDevice.cpp}`,
`aasdk-upstream/{include/aasdk/USB/*.hpp,src/USB/{USBHub,AccessoryModeQuery*}.cpp,src/{Transport/SSLWrapper,Messenger/Cryptor}.cpp}`,
`stream/{server.py,auriga_stream.py,lib/{h264,clock}.py,web/app.js}`, `scripts/auriga.sh`,
`scripts/build.sh`, `openauto-config/{run.sh,openauto.ini}`, `.gitignore`, all 7
`patches/*.patch`, `tools/{aoa_probe,aoa_read}.py`, `.rearch/{phases,deviations,docs-plan}.md`,
`logs/openauto-mac-20261029-*.log`.

Commands run: `.venv/bin/python -m unittest discover -s tests` → **100 tests OK**;
`py_compile` on `stream/ scripts/ tools/` → OK; `bash -n` on both scripts → OK;
`ffprobe -count_frames` on `captures/2026-10-28-macos-session2-video.h264`;
NAL-offset scan + byte diff of all four `videoInfo` snapshots; sha256 of all
`dongle-backup/` files; `brew list --versions`; `ls`/`pgrep` of the live pair.

## Functional behavior
- F1 (FR-HU-01/02, FR-DGL-01/02): AOA chain only for `2717:ff40`, `18d1:2d01`
  refused, `18d1:2d00` claimed, capture mode = non-empty `AURIGA_CAPTURE_DIR`.
  Evidence: `openauto/src/autoapp/autoapp.cpp:245-246`,
  `aasdk-upstream/src/USB/USBHub.cpp:84-87,89-98,115-125`,
  `Projection/AurigaSession.cpp:38-64`; doc `docs/AutoLink A512 dongle.md:12-26`.
  Status: active, verified.
- F2 (FR-HU-03/04/05/06/12, NFR-01/05): per-entity `session-<id>/` with six
  files, `trunc` into a fresh dir, three WAV sinks (48k/2ch, 16k/1ch ×2),
  silent 20 ms mic, stdin input device, 4 GiB−16 MiB rotation, 5-session
  retention, ACK-before-copy. Evidence:
  `ServiceFactory.cpp:130-136,173-180,197,205,231,240-241`,
  `AurigaSession.cpp:107-147,182-233,235-280`, `AurigaSession.hpp:38-42`,
  `AurigaWriter.hpp:44-45,77-116,205-216`,
  `VideoMediaSinkService.cpp:177-190`, `AurigaAudioOutput.cpp:170-175`,
  `AurigaAudioInput.cpp:71,89`; docs `docs/Android Auto head unit.md:105-211`.
  Status: active, verified.
- F3 (FR-HU-07/09/10, FR-STR-*): input device starts from `KeyBindingRequest`
  (`InputSourceService.cpp:122`), identity `Auriga`/RIGHT/year 2018/vehicle_id
  `2024110822150988` (`AndroidAutoEntity.cpp:180-203`), BT dummy device
  `isAvailable()==false` + `BLUETOOTH_PAIRING_UNAVAILABLE` + PIN `123456`
  (`BluetoothService.cpp:82-83,124-125,140`), pinger 5000 ms / 5 unacked
  (`AndroidAutoEntityFactory.cpp:65`, `Pinger.cpp:59`). Docs
  `docs/Android Auto head unit.md:229-234,261-293`. Status: active, verified.
- F4 (FR-STR-01..14): ports/binds, `config.json`, 8 ms poll, 50 ms session
  poll, `AUDIO_CHUNK=7680`, `VIEWER_QUEUE=240`, `GOP_MAX_FRAMES=2400`,
  `REPLACED_CODE=4001`, `LAST_IDR_WINDOW=8 MiB`, 1 MiB/256 KiB read caps,
  4-byte audio alignment, `max_size=None`, content clock. Evidence
  `stream/server.py:48-57,138-160,244-397,409-457,469-538,541-570`,
  `stream/lib/h264.py:11-12,191-202`, `stream/lib/clock.py:18-62`,
  `stream/web/app.js:9-12,42-76,243-290,339-366`. Docs
  `docs/Stream protocol.md:9-264`. Status: active, verified.
- F5 (FR-RUN-01..04/06, NFR-07): start order FIFO → autoapp → stream → poll
  HTTP then WS (20 s, `AURIGA_READY_TIMEOUT`) → caffeinate → lock → browser;
  ports passed to the server; stop = cmdline-checked SIGTERM, 10 s, SIGKILL,
  `pkill` orphans; FIFO writer `sleep 31536000`, stale writers reaped.
  Evidence `scripts/auriga.sh:23-24,101-120,130-133,183-238,265-280`;
  doc `docs/Android Auto head unit.md:372-400`. Status: active, verified
  (one-pair scope caveat: D8).
- F6 (FR-BLD-01..07): 7 patches (5 OpenAuto + 2 aasdk), pins
  `9bf6adf93366…`/`4cc739b81362…`, `check_complete`, policy minimum, Boost pin,
  `build: ok: N patches -> aasdk + autoapp`. Evidence
  `scripts/build.sh:29-37,85-92,170-210`; `docs/Build.md:37-165,233-243`.
  Status: active, verified.
- F7 (FR-DGL-04/05, CON-DGL-*): `videoInfo` 364 B layout, `btapp.db` 33/207 B
  forms, valid/invalid backups, recovery recipes. Evidence: byte scans below;
  doc `docs/AutoLink A512 dongle.md:124-188`. Status: active, verified except
  D19/D20 and the `unverified` items listed under X4-X6.
- F8 (DGL documentation, manual): MTP procedure now lives in the topic doc
  (`docs/AutoLink A512 dongle.md:103-122`), so the fold requirement of prior
  A5/I3 is met; `dongle-backup/README.md` is redundant, not missing.
  Status: active.

## External facts and quirks
- X1: All 7 patches exist and match their claimed file sets; `openauto-capture`
  is the only patch touching `ServiceFactory.cpp` and `SensorService.cpp`;
  `openauto-macos` touches only `App.cpp` + `UI/SettingsWindow.cpp`
  (`grep '^+++' patches/*.patch`). Source: code.
- X2: `videoInfo.car-trip` vs `.orig` differs at exactly `0x0c`, `0x1f-0x22`
  (4 SPS bytes), `0x2e`, `0x68-0x71`, `0x168-0x16b`. `videoInfo.galaxy` ==
  `videoInfo.galaxy.active` (sha `d2fcb4337247…`, zeroed `0x04,0x08,0x12-0x4f,
  0x72-0x79`). Source: byte scan.
- X3: Measured capture head and stream shape reproduce the docs exactly: SPS
  @0, PPS @21, IDR @29, first slice @3645; 3059 NALs (1 SPS, 1 PPS, 2 IDR,
  3055 non-IDR); 3057 frames; second IDR at VCL index 1800; 12,274,423 B;
  Baseline level 31; `r_frame_rate=1200000/1`. Source: `ffprobe` + NAL scan.
- X4: `logs/openauto-mac-20261029-072459.log` shows `onBluetoothPairingRequest`
  (:130-136) and `Version Received: 256.1792` (:57) **before** the `AASDK
  Error: 10` burst (:139-148) in the same entity. Source: log capture.
- X5: The live pair is still the pre-rework stack: pids 29079/29090 started
  07:41 with the removed CLI (`auriga_stream.py --video … --audio …`), no
  `.auriga.lock`, `captures-mac/` flat (`video.h264` still growing at 10:18),
  no `current`, no `session-*`. Source: `ps` + `ls`.
- X6: Toolchain table `docs/Build.md:15-29` matches the host exactly (cmake
  4.4.4, boost@1.85 1.85.0_3, qt@5 5.15.19, protobuf 36.2, abseil 20260817.0,
  taglib 2.3.2, rtaudio 6.0.1, util-linux 2.42.4, gpsd 3.27.5, openssl@3
  3.5.9, libusb 1.0.30, Python 3.14.8 + websockets 17.3, ffmpeg 9.0.2);
  `brew` default boost is 1.92.0 as claimed (`docs/Build.md:172`); artifact
  sizes 51,898,688 / 245,206,744 B as claimed (`docs/Build.md:112-113`).
  Source: `brew list --versions`, `ls -l`.
- X7: `AASDK_MAJOR`/`AASDK_MINOR` are at `aasdk-upstream/include/aasdk/Version.hpp:22-23`,
  not `:26-27` as the prior audit's D13 asserted. No doc now cites a line, so
  the finding is moot. Source: code.
- X8: `tools/aoa_probe.py` now falls back to `ioreg -p IOUSB -l -w 0`
  (`:47-52`), so prior B1/X7 (macOS `lsusb`) is fixed; `aoa_read.py` now has a
  timeout-errno set (`:20,76`) and a claim-failure message (`:37-40`), so prior
  B2/B3 are fixed. Source: code.
- X9: Only `ly-AutoLink-A512` / `ly_linktype_aa` / `videoInfo` / `btapp.db` are
  plausibly on the dongle; `btapp.bk` and `800x480-A512.h264` are both absent
  (`docs/AutoLink A512 dongle.md:88,93`), i.e. **six** populated slots. Source:
  doc table + doc statements.

## Doc and code inconsistencies
- D1 [high] `README.md:3-5,12-139` still presents a Raspberry Pi 3B host
  (`auriga-pi.local`, `192.168.2.2/24`, `dwc_otg` limits,
  `vcgencmd get_throttled`) as the system. `docs/Build.md:3` and
  `scripts/auriga.sh:184` are macOS-only; NFR-04 and Q1 dropped the Pi.
- D2 [high] `README.md:25,266-303,309,332` presents the dropped `capture/` app
  as a live component/basis for future work (FR-CAP-01..05 dropped, Q7);
  `README.md:324,342` presents dropped `PHONE-APP.md` (FR-PHONE-01..04, Q9);
  `README.md:94-95,132-135` presents the dropped Pi 4/5 forwarding path
  (FR-RUN-05).
- D3 [high] `README.md:90-91` says "Capture files are opened with truncation, so
  a new AA session overwrites the previous one. Per-session filenames are
  needed." Code mints `session-<id>/` per entity and never truncates a previous
  session (`AurigaSession.cpp:107-147`); same file contradicts itself at
  `README.md:69-71` and `docs/Android Auto head unit.md:164-166`.
- D4 [medium] `README.md:35-36` says the phone shows **Crankshaft-NG** and
  "should be renamed to Auriga". The identity patch sets `display_name`
  `Auriga` (`AndroidAutoEntity.cpp:182`); `docs/Android Auto head unit.md:266`
  and `DEVELOPING.md:45` state it as done.
- D5 [medium] `README.md:237-239` quotes AOA identity strings
  `Auriga`/`Auriga Pi Capture`/`Android Auto capture head unit`/`1.0`/empty
  URI/`auriga-pi`; the head unit sends aasdk's set
  (`AccessoryModeQueryFactory.cpp:43-64`) and the probe sends a third set
  (`tools/aoa_probe.py:32-39`, quoted correctly in
  `docs/AutoLink A512 dongle.md:58-60`).
- D6 [medium] `README.md:58-62` lists four OpenAuto patches (capture, macos,
  auriga-usb-filter, auriga-gps-guard) plus two aasdk patches; the tree has
  five OpenAuto patches (`openauto-auriga-identity.patch`, so 7 total —
  `patches/`, `docs/Build.md:44`, `DEVELOPING.md:87`).
- D7 [medium] `README.md:240-241` says the 1.6→1.7 bump lives in
  `aasdk/include/aasdk/Version.hpp`; the tree is
  `aasdk-upstream/include/aasdk/Version.hpp` and the edit lives in
  `patches/aasdk-version-absl.patch` (Q6/FR-BLD-07).
- D8 [medium] `docs/Android Auto head unit.md:383-386` and `AGENTS.md:24-26`
  call the lock the "one-pair-per-capture-dir guarantee" with `pgrep` as an
  "orphan fallback". `find_autoapp`/`find_stream` fall back to a host-wide
  `pgrep` (`scripts/auriga.sh:60-78`) and `cmd_start` refuses on either match
  (`:189-196`), so the guarantee is host-wide, not per capture dir; the lock is
  also written only after readiness (`:234`).
- D9 [medium] `docs/Android Auto head unit.md:295-302` says the first entity
  dies "before `Version Received`" and "before any Bluetooth pairing request
  can occur". `logs/openauto-mac-20261029-072459.log` shows Version Received at
  `:57`, a pairing request at `:130-136`, then Error 10 at `:139-148`. The
  stated cause-reasoning is refuted by the only stored log.
- D10 [medium] `DEVELOPING.md:152-153` attributes the first-entity reset to
  "the dongle's BT pairing request", which `docs/Android Auto head unit.md:299-300`
  explicitly rejects. The two docs contradict each other; the log (X4) supports
  DEVELOPING's ordering of events, not its cause.
- D11 [low] `DEVELOPING.md:42` lists `Service/ServiceFactory.cpp` under
  `patches/openauto-macos.patch`; that patch touches only `App.cpp` and
  `UI/SettingsWindow.cpp` — `ServiceFactory.cpp` belongs to
  `openauto-capture.patch`.
- D12 [low] `docs/AutoLink A512 dongle.md:146-148` says `car-trip` differs from
  `.orig` in "4 SPS bytes (`0x1e..0x21`)". Actual SPS diffs are
  `0x1f,0x20,0x21,0x22`. (Prior D18, unfixed.)
- D13 [low] `docs/AutoLink A512 dongle.md:252-254` tells the operator to check
  "PPS at `0x27`"; `0x27` is the second 4-byte start code, PPS is at `0x2b`
  per its own table (`:139`).
- D14 [low] `docs/AutoLink A512 dongle.md:81-82` says "seven slots are
  populated"; `btapp.bk` (`:88`) and `800x480-A512.h264` (`:93`) are both
  absent, so six are. (Prior D20, half-fixed.)
- D15 [low] `docs/AutoLink A512 dongle.md:156` says the `posttrip/videoInfo.post`
  duplicate "is deleted with `posttrip/`"; `posttrip/` and the tracked file are
  still present (`git ls-files posttrip`).
- D16 [low] `docs/AutoLink A512 dongle.md:15` cites `USBHub.cpp:84-87` for "claimed
  as the head-unit target"; `:84-87` is the ID match, the claim is
  `:134-136`. `:16` cites `:121-127`, the refusal is `:121-125`.
- D17 [low] `docs/Android Auto head unit.md:71-73` cites `USBHub.cpp:43-51` for
  the hotplug registration (actual `:47-52`) and `:52-66` for
  register-once/remove-in-`cancel()` (start ends `:55`, cancel `:57-72`).
  `docs/Build.md:214` cites `App.cpp:40-41` for the port-0 acceptor (the
  ternary is `:39-40`).
- D18 [medium] `README.md:118` still sends the reader to `stream/README.md` for
  the protocol; `AGENTS.md:124` was repointed to
  `docs/Stream protocol.md`, and `docs-plan.md:20` folds/deletes
  `stream/README.md`. `README.md:96,99,117,337,338,368` point at
  `openauto-plan.md`, `MAC-PORT.md`, `RUNBOOK.md`, `NEXT-SESSION.md`, all
  scheduled for deletion (`docs-plan.md:15-19`).
- D19 [low] `README.md:106` hardcodes `/Users/tomaszwerbicki/dev/auriga`
  (prior D25).
- D20 [low] `dongle-backup/README.md:38-39` lists `btapp.db.galaxy2` /
  `btapp.bk.galaxy2` as if stored in `dongle-backup/`; only the four root-level
  copies exist (`btapp.db.galaxy2`, `btapp.bk.galaxy2`). `:56` references
  `active-btapp.db` "on the Pi in `/tmp/auriga-db/`" — Pi dropped.
- D21 [low] `dongle-backup/README.md:114-116` says in the present tense that
  "the active Galaxy DB is the fix for the AA pairing request", contradicting
  its own reset section (`:47-52`) and `docs/AutoLink A512 dongle.md:119-122`
  (the current key is the 33-byte `btapp.db.galaxy-fresh`).
  `dongle-backup/README.md:23` calls `videoInfo.car-trip` "same 1280x720
  SPS/PPS" although 4 SPS bytes and the PPS level byte differ (X2).
- D22 [low] `.gitignore:1` still says pinned commits are "documented in
  README.md"; they are in `scripts/build.sh:29-37` and `docs/Build.md:39-45`
  (prior L5, unfixed).

## Assumptions to revalidate
- A1: "The prior doc drift was fixed by using symbols/anchors." True for the
  four topic docs, but the doc set now depends on GitHub heading slugs
  (`#usb-identity`, `#videoinfo-layout`, `#boost-must-be-185`,
  `#usb--phone-invariants`, …). All 14 slugs referenced by
  `requirements.md` and the docs resolve today; any heading rename silently
  breaks traceability with no check.
- A2: "`docs/requirements.md` will be the shipped requirements" (docs-plan:24):
  today the only copy is `.rearch/requirements.md`, which Stage 6 deletes; the
  dropped sections (`FR-CAP-*`, `FR-PHONE-*`) cite `capture/src/*`,
  `capture/CMakeLists.txt`, `PHONE-APP.md:88-334` — all deleted by the same
  stage, leaving unverifiable evidence in the "Dropped" record.
- A3: "`captures/` remains the fixture directory" (docs-plan:21 keeps the media,
  `docs/Android Auto head unit.md:203,344` cite
  `captures/2026-10-28-macos-session2-video.h264`). The file is untracked
  (`.gitignore:24-27`) while three `*-input.jsonl` and `captures/README.md`
  are tracked; a fresh clone cannot reproduce the measured NAL/frame numbers.
  docs-plan:21 promises a one-line provenance note; the AA doc has numbers but
  no provenance line.
- A4: "`AGENTS.md`/`README.md`/`DEVELOPING.md` rewrites are Stage 6 work" —
  correct by `docs-plan.md:12-14`, but `phases.md:246-248` asserts README's
  "factual contradictions are already fixed", which no longer holds (D1-D7).
- A5: "The verification blocks work on the rig." They do not today: both
  `AGENTS.md:54,75` and `docs/Android Auto head unit.md:413` read
  `captures-mac/current/video.h264` and the live `captures-mac/` has no
  `current` (X5). The AA doc adds the caveat (`:418-419`), AGENTS.md does not.

## Bugs
- B1 [high]: `README.md` is still the entry point a new reader hits first and it
  teaches a deleted host and deleted components (D1-D3, D5-D7, D18). Scenario:
  follow `README.md:25`/`:290` → `capture/README.md`, build a stack that
  "resets on every session" per `README.md:298-302`; follow
  `README.md:116-118` → `RUNBOOK.md` with deleted scripts.
- B2 [medium]: the `AASDK Error 10` runbook page is wrong about ordering and
  the cause premise (D9), and the sibling doc gives the opposite cause (D10).
  Scenario: an operator debugging the first-session reset reads "fails before
  `Version Received`, so BT cannot be involved" and rules out the one code path
  the log shows active immediately before the failure.
- B3 [medium]: dongle validation recipe names the wrong PPS offset (D13).
  Scenario: an operator validates a hand-built `videoInfo` against `0x27`,
  passes a file whose PPS is missing, uploads it, and the dongle fails later at
  video setup — the exact failure the section exists to prevent.
- B4 [low]: `README.md:200-215` states in the present tense that the active
  `btapp.db`/`btapp.bk` are the patched two-Galaxy 207-byte pair, one screen
  above `README.md:217-229` describing the 33-byte reset DB. Scenario: a reader
  restores `btapp.db.galaxy` believing it matches `README.md`'s "active" claim,
  overwriting the only current link key.

## Dead code, leftovers, stale comments
- L1: `README.md:12-52,120-139,159-233,266-303,305-328,330-368` — the Pi-era
  narrative, the `capture/` and `PHONE-APP.md` sections, the `posttrip/` and
  `NEXT-SESSION.md` file-map rows (rewrite target `docs-plan.md:12`).
- L2: `DEVELOPING.md:23` still names the dropped `capture/` app.
- L3: `.gitignore:45-50` ignores `/posttrip/*` and `/btapp.*` while
  `posttrip/{videoInfo.post,ly-AutoLink-A512.post,ly_linktype_aa.post}` are
  tracked; the four root `btapp.db.galaxy*`/`btapp.bk.galaxy2` credential DBs
  are still in the working tree and mentioned by no doc (prior L2).
- L4: `.gitignore:1` stale comment (D22).
- L5: `scripts/auriga.sh:276-277` still deletes `/tmp/auriga-mac-*.pid` and
  `/tmp/auriga-fifo-writer.pid`, which nothing creates (prior B5/L5).
- L6: `docs/Build.md:44-47` names `diff -r` against a patched pristine clone as
  "the reliable check" but gives no command anywhere in the doc set.
- L7: `captures/README.md` (tracked) still describes the flat `captures/`
  layout; `docs-plan.md:21` folds it into the AA doc.

## Improvement areas
- I1: Rewrite `README.md` to `docs-plan.md:30` (what it is, quick start,
  build/run/test, doc pointers). It is the only file that still references
  every dropped path; deleting those references resolves D1-D3, D5-D7, D18,
  D19 in one edit.
- I2: Cut `AGENTS.md` from 166 to the planned <60 lines (`docs-plan.md:13`) and
  fold `DEVELOPING.md` per `docs-plan.md:14`; `AGENTS.md:99-125` duplicates
  `docs/Stream protocol.md` verbatim in substance.
- I3: Add the `current` caveat to `AGENTS.md:54,75` (the AA doc has it at
  `:418-419`) or make the verify block tolerate "no session yet"
  (`./scripts/auriga.sh status` already prints `session: none yet`).
- I4: Add one provenance line for `captures/2026-10-28-macos-session2-video.h264`
  (device, date, build, dongle, session) to `docs/Android Auto head unit.md`,
  or track the file; every measured number in `:342-358` depends on it.
- I5: Correct the `AASDK Error 10` section to match
  `logs/openauto-mac-20261029-072459.log` and delete the duplicated claim in
  `DEVELOPING.md:152-153`, or move the log excerpt into the doc as the
  evidence its "unverified" status needs.
- I6: Give `scripts/auriga.sh` a `--capture-dir`-scoped check (lock first,
  `pgrep` only as a last resort behind a flag) so the D8 guarantee matches its
  wording, or reword both docs to "host-wide".
- I7: Turn the `videoInfo` byte checks (`docs/AutoLink A512 dongle.md:252-254`)
  into a scripted check with correct offsets (magic `0x00`, `0x04`, `0x08`,
  start code `0x12`, PPS `0x2b`, address `0x54`); the recipe is the only
  safeguard against restoring the zeroed `.galaxy` snapshot.

## Interfaces
- Exposes: the four topic docs as the citable fact base (USB IDs, `videoInfo`
  and `btapp.db` layouts, MTP procedure and recovery; capture + manifest
  contract; wire protocol and browser behaviour; toolchain + patch order); the
  doc anchors that `requirements.md` cites (`#usb-identity`,
  `#videoinfo-layout`, `#btappdb-layout`, `#recovery`, `#carplay-latch`,
  `#idle-re-enumeration`, `#bluetooth-and-wi-fi-identity`,
  `#aa-protocol-version`, `#aa-stream-format`, `#boost-must-be-185`,
  `#cmake-policy-minimum`, `#one-command-build`, `#verification`,
  `AGENTS.md#safety`, `#usb--phone-invariants`, `#integration-contract`);
  `AGENTS.md` as the operator/agent contract; `DEVELOPING.md` as the patch
  workflow; `dongle-backup/*` as the only restorable dongle state.
- Consumes: `patches/*.patch` (patch order, attribution), the nested
  `openauto/`/`aasdk-upstream/` symbols, `captures-mac/current` +
  `manifest.json` + `session-<id>/`, `logs/openauto-mac-*.log`, the stream
  server's wire format, `scripts/{auriga,build}.sh` behaviour, byte-level
  `dongle-backup/` data, and `ioreg`/`adb`-observed USB IDs.
- Threading: none. Docs are static; `requirements.md` is static text. The only
  concurrency the docs describe is in code they cite (8 `io_service`/libusb
  threads + Qt main, one writer thread per sink, one asyncio loop + one HTTP
  thread in the stream server) — verified against
  `openauto/src/autoapp/autoapp.cpp:46-72,101-105` and
  `stream/server.py:541-570`.

## Open questions for the user
- Q1: Is `README.md`'s rewrite part of this rearchitecture or handed back as a
  separate task? It is the one file blocking "no doc references a dropped
  path", and Stage 6 assumes it.
- Q2: Should `captures/2026-10-28-macos-session2-video.h264` be committed as the
  fixture the measured numbers depend on, or should those numbers be marked
  `unverified`?
- Q3: Keep `dongle-backup/README.md` after the fold, or delete it? The topic doc
  now carries the MTP procedure, and only `AGENTS.md:145` still points at it.
- Q4: Is the `AASDK Error 10` first-entity reset still open for investigation
  with the BT pairing request as the suspect (log order) or dropped as
  `unverified`?
