# Audit: runtime orchestration + build tooling (final module audit)

Scope: RUN (`scripts/auriga.sh`, `openauto-config/run.sh`, `openauto-config/*.ini`),
BLD (`scripts/build.sh`, `docs/Build.md`, `.gitignore`), NFR-03/04/07/08.
Checked against `.rearch/requirements.md` (kept FRs only). Tree is at `9b957fd`
(phases 1-7 applied, Stage 6 cleanup not started). Working tree clean.

## Coverage
| File | Lines | Read fully |
| --- | --- | --- |
| scripts/auriga.sh | 302 | yes |
| scripts/build.sh | 213 | yes |
| openauto-config/run.sh | 38 | yes |
| openauto-config/openauto.ini | 29 | yes |
| openauto-config/openauto-logs.ini | 17 | yes |
| .gitignore | 53 | yes |
| docs/Build.md | 293 | yes |
| .rearch/requirements.md | 320 | yes (input) |
| docs/Android Auto head unit.md | 400+ | sections cited (Runtime 363-400, config 233-246, verification 389+) |
| stream/auriga_stream.py | 51 | yes (CLI contract) |
| stream/server.py | 500+ | lines 488-499 only (bind) |
| openauto sources | - | greps only (Configuration.cpp, ServiceFactory.cpp, AndroidAutoEntity.cpp) |

Verification commands run (all read-only):
`sh -n` on the three scripts (OK); `git -C {openauto,aasdk-upstream} apply --check
--reverse` for all 7 patches (all OK); `./scripts/build.sh -h`; `./scripts/auriga.sh`
(exit 2); `./scripts/auriga.sh status` (exit 0); `./scripts/auriga.sh start`
(refused, exit 0); `brew list --versions` for the 11 formulae; `.venv` python and
`websockets` version; `ps`/`pgrep` of the running pair.

## Functional behavior

RUN
- F1 (FR-RUN-01, kept): `start` creates FIFO+writer, starts `autoapp` via
  `openauto-config/run.sh` (offscreen), starts the stream server, polls
  `127.0.0.1:8080`, starts `caffeinate`, writes the lock, opens Brave, falls back
  to the default browser. Evidence `scripts/auriga.sh:176-226,167-174`. Status:
  active.
- F2 (FR-RUN-02, kept): single-pair idempotency. Code refuses **both** components
  when either one runs; it does not skip a running component and start the other.
  Evidence `scripts/auriga.sh:182-189` (`find_autoapp`/`find_stream` 58-76).
  Status: active, behavior differs from the FR wording (see D2).
- F3 (FR-RUN-03, kept): one FIFO, `rm -f` + `mkfifo`, one background writer
  holding the write side. Evidence `scripts/auriga.sh:110-115`; the reader is
  `< "$AURIGA_INPUT_FIFO"` in `openauto-config/run.sh:38`. Status: active.
- F4 (FR-RUN-04, kept): stop = cmdline-checked SIGTERM from the lock, 10 s grace,
  SIGKILL, then `pkill -f` for orphans; no graceful shutdown, no client notice.
  Evidence `scripts/auriga.sh:229-267`. Status: active.
- F5 (FR-RUN-06, kept): both listeners bind `127.0.0.1` (stream side, out of this
  file set): `stream/server.py:496`, `stream/auriga_stream.py:45`. `auriga.sh`
  opens no socket. Status: active. No auth (NFR-03) — nothing in the scripts
  exposes the ports.
- F6 (FR-RUN-05, dropped): no Pi/`mac-start`/`mac-stop` scripts remain in
  `scripts/` (only `auriga.sh`, `build.sh`). Status: deleted, but docs still
  describe them (D13-D15).
- F7 (NFR-04, kept): host guard `uname -s = Darwin` in both entry points
  (`auriga.sh:177`, `build.sh:80`); `run.sh` has no OS assumption beyond macOS
  paths. Status: active.

BLD
- F8 (FR-BLD-01/06/07, kept): one script clones aasdk `9bf6adf9` and openauto
  `4cc739b8` at pinned commits, resets an earlier clone, applies 2 + 5 patches in
  the documented order, configures with the documented lines, builds
  `aasdk`→`autoapp`, asserts both artifacts, prints `build: ok: 7 patches`.
  Evidence `scripts/build.sh:29-37,95-122,165-210`. Status: active (7 patches
  reverse-apply cleanly on the nested trees).
- F9 (FR-BLD-02, kept): `patches/` completeness is enforced — every `*.patch` in
  `patches/` must be in an ordered list or the build dies. Evidence
  `scripts/build.sh:85-92,130`. Status: active.
- F10 (FR-BLD-03/04, kept): Boost 1.85 pin (`-DBoost_DIR=.../Boost-1.85.0`,
  `build.sh:180,195`) and `-DCMAKE_POLICY_VERSION_MINIMUM=3.5` on both configure
  lines (`build.sh:176,189`). Status: active. Installed versions match the
  `docs/Build.md` toolchain table exactly (cmake 4.4.4, boost@1.85 1.85.0_3,
  protobuf 36.2, abseil 20260817.0, qt@5 5.15.19, gpsd 3.27.5, libusb 1.0.30,
  openssl@3 3.5.9, taglib 2.3.2, rtaudio 6.0.1, util-linux 2.42.4, Python 3.14.8
  + websockets 17.3, ffmpeg 9.0.2).
- F11 (FR-BLD-07, kept): `patches/aasdk-version-absl.patch` carries
  `AASDK_MINOR 6→7` and the Darwin `absl::base` include block; verified
  reverse-applies on `aasdk-upstream`. Status: active.
- F12 (FR-BLD-05, dropped): `capture/` still on disk (Stage 6 owns deletion).
  Status: leftover, see L7.
- F13 (NFR-07, kept): readiness is a socket poll, not `sleep 1`:
  `wait_port` + `nc -z`, 20 s default, `AURIGA_READY_TIMEOUT`
  (`scripts/auriga.sh:99-108,205-209,23`). Satisfied for the stream server; the
  head unit itself is checked only by `kill -0` (`:210-219`), so a dongle stuck
  at `Waiting for device...` still yields "Auriga head unit up." (B4).
- F14 (NFR-08, kept, partial): lock file `<capture>/.auriga.lock` with one
  `role pid` line per component (`scripts/auriga.sh:52-56,137-144`), plus a
  `<capture>/.auriga.start/pid` start guard (`:78-90`). Gaps: the lock is written
  only after readiness (`:222`), `find_autoapp`/`find_stream` fall back to global
  `pgrep` (`:65,75`) so the guarantee is host-wide, not per capture dir, and the
  live pair right now has no lock at all (B1).
- F15 (NFR-06-adjacent, observed): `logs/` holds 26 files, two per start, never
  pruned (`scripts/auriga.sh:25-26`). Capture retention (NFR-05) is a head-unit
  concern, not this module's.

Config inputs
- F16: `openauto-config/openauto.ini` is load-bearing only in capture mode via
  `configuredVideoGeometry`: `Video.Resolution=2` → 1280x720 and `Video.FPS=2` →
  30 fps, which also set the touch geometry and the manifest geometry
  (`ServiceFactory.cpp:69-94,130-135`; enum values confirmed
  `VideoFrameRateType.proto:6-7`, `VideoCodecResolutionType.proto:6-8`). Status:
  active, undeclared coupling: editing the ini silently changes manifest geometry,
  touch space and browser canvas.
- F17: `Bluetooth.WirelessProjectionEnabled=true` gates creation of the
  **Bluetooth** service (`ServiceFactory.cpp:142-146`); empty
  `Bluetooth.AdapterAddress` selects `DummyBluetoothDevice`
  (`ServiceFactory.cpp:153-157`). Status: active; the key name misdescribes the
  branch.
- F18: `openauto-logs.ini` writes a second, synchronously autoflushed log to
  `openauto-config/openauto.log` (relative to CWD, gitignored) while `auriga.sh`
  captures the same console sink to `logs/openauto-mac-<stamp>.log`. Status:
  active duplication.

## External facts and quirks
- X1: `nc -z` is the readiness probe (`scripts/auriga.sh:49`); there is no
  fallback if `nc` is absent and no connect timeout, so a firewalled localhost
  would hang instead of timing out. Source: code.
- X2: macOS `open -a "Brave Browser"` is the primary browser open; the fallback
  runs `open <url> 2>/dev/null || true` and prints success either way
  (`scripts/auriga.sh:167-174`). Source: code.
- X3: Homebrew formula prefixes are resolved at build time for 11 formulae;
  `boost@1.85` is deprecated upstream but still installs (`docs/Build.md:172-173`).
  Source: code + doc.
- X4: `scripts/build.sh` never touches `openauto/`, `aasdk-upstream/`,
  `build-*-mac/`; it builds `build-openauto/bin/autoapp` in its own work root,
  which is **not** the binary `run.sh` starts (`build-openauto-mac/bin/autoapp`).
  A from-patches build therefore proves buildability, not that the head unit runs
  it. Source: code `scripts/build.sh:187-206` vs `openauto-config/run.sh:20-23`.
- X5: FIFO semantics — `autoapp` opens stdin blocking, EOF ends the input reader
  for the rest of the run, so the writer must outlive the session
  (`scripts/auriga.sh:39-42`; `run.sh:38`). Observed consequence: four orphan
  `sleep 86400` writers from the pre-rework scripts still hold old FIFO inodes
  (pids 27002, 27151, 29086, 91778). Source: code + `ps`.

## Doc and code inconsistencies
- D1: `requirements.md:115,119,123,127,130` cite `scripts/mac-headunit-start.sh`,
  `scripts/mac-headunit-stop.sh`, `openauto-config/run-mac.sh`; those files do not
  exist. Code is `scripts/auriga.sh` (`:176-302`) and `openauto-config/run.sh`.
- D2: `requirements.md:117-120` (FR-RUN-02) says start "skips running components
  instead of failing"; code refuses the whole start when either component runs
  (`scripts/auriga.sh:184-189`).
- D3: `requirements.md:121-123` (FR-RUN-03) says the FIFO writer is
  `sleep 86400`; code uses `FIFO_WRITER_SECONDS=31536000` (`auriga.sh:42,113`).
- D4: `requirements.md:205-210` (FR-BLD-01) says "four patches (`capture ->
  macos -> auriga-usb-filter -> auriga-gps-guard`)" plus two aasdk edits; code has
  five OpenAuto patches (adds `openauto-auriga-identity.patch`) and one combined
  `aasdk-version-absl.patch` (`scripts/build.sh:31,35-37`).
- D5: `requirements.md:250-252` (NFR-07) cites the missing
  `scripts/mac-headunit-start.sh:69` for "not a fixed `sleep 1`"; the behavior is
  in `scripts/auriga.sh:99-108,205`.
- D6: `docs/Build.md:236-237` lists
  `build-openauto-mac/bin/autoapp-2026.10.28+git.4cc739b.dirty`; the symlink
  points at `autoapp-2026.10.29+git.4cc739b.dirty` (both binaries exist).
- D7: `docs/Android Auto head unit.md:~397` verifies
  `captures-mac/video.h264` (flat layout, pre-phase-3); `docs/Build.md:277-282`
  verifies `captures-mac/current/video.h264` (session layout). Both docs are
  present-tense; only the session path is correct, and neither works today because
  `captures-mac/current` does not exist (B1).
- D8: `docs/Android Auto head unit.md:374-381` says start "refuses ... a running
  `autoapp` of the same build" and calls it "the one-pair-per-capture-dir
  guarantee"; code also refuses when only a stream server runs anywhere on the
  host, via `pgrep` (`scripts/auriga.sh:65,75,182-189`), so the guarantee is
  host-wide.
- D9: `docs/Android Auto head unit.md:372-373` orders start as "starts caffeinate,
  polls 8080, writes the lock"; code polls (`:205`), then starts caffeinate
  (`:221`), then writes the lock (`:222`).
- D10: `.gitignore:1` says pinned commits are documented in `README.md`; they are
  in `scripts/build.sh:29-37` and `docs/Build.md:39-45`. `README.md:68` still
  names the deleted `mac-headunit-start.sh`.
- D11: `MAC-PORT.md:25-26,262,278,294` and `RUNBOOK.md:38,45,116,129,145,304`
  document `mac-headunit-start.sh`, `run-mac.sh`, `pi-start.sh`, `mac-start.sh`,
  `pi-stop.sh`, `mac-stop.sh` — all deleted in phase 6 (`phases.md:188-191`).
  Leftovers pending Stage 6.
- D12: `docs/Build.md:44` "reproduces the nested trees byte for byte" — no step
  compares trees; the reproducible check is the seven reverse-applies
  (`docs/Build.md:154-162`), which do pass.

## Assumptions to revalidate
- A1: That the head unit currently running is the reworked stack. It is not: pids
  29079/29090 started `07:41:01` with the old CLI
  (`auriga_stream.py --video ... --audio ... --fifo ...,` which
  `stream/auriga_stream.py:30-36` no longer accepts), the lock file is absent, and
  `captures-mac/` holds flat `video.h264`/`audio-*.wav` with no `session-*` dir and
  no `current` symlink. If false (as here), every session-model FR (FR-STR-13/07,
  NFR-08) is unverified on hardware and M6/M7 evidence is for the old build.
- A2: That `build-openauto-mac/bin/autoapp` matches `patches/`. The binary carries
  `.dirty` (built 09:37 from the nested tree, patches touched 09:31); the tree
  reverse-applies all patches, so the assumption holds today but is not enforced
  by any script.
- A3: That `openauto-config/openauto.ini` stays at `Resolution=2`/`FPS=2`. Anything
  else changes touch coordinates (browser sends 1280x720 space,
  FR-STR-11) and the manifest geometry silently.
- A4: That `.auriga.lock`/`.auriga.start` inside the capture dir are safe. They are
  ignored by the session scanner (only `session-*` names,
  `stream/lib/session.py:19,126`), but they do land in a directory whose contents
  are otherwise pure capture data.
- A5: That a `pgrep`-matched process is ours. `find_autoapp` matches any process
  whose cmdline contains `build-openauto-mac/bin/autoapp`; a background
  `git`/editor/tail on that path could be killed by `stop` (the cmdline check in
  `stop_pid` only verifies the same substring, `auriga.sh:235-240`).

## Bugs
- B1 [high]: the live pair is a pre-rework stack with no lock, no session dirs and
  an obsolete stream CLI; `status` reports `session: none yet` and `lock: (none)`
  while a live pair owns the dongle, and `docs/Build.md:277-282` verification
  commands fail (`captures-mac/current` missing). `scripts/auriga.sh:283-289`
  (status), `ps` evidence, `captures-mac/` listing. Scenario: start the head unit
  with the old scripts, rework the tree, run `status` → green ports, wrong
  evidence, and nothing flags the stale components.
- B2 [medium]: HTTP/WS ports are duplicated — `auriga.sh:21-22` uses 8080/8081 for
  the readiness poll and the Brave URL but never passes `--http-port`/`--ws-port`
  to the server, which defaults to the same values (`auriga_stream.py:33-34,38,45`).
  Scenario: change `HTTP_PORT` to 8090 → the server still binds 8080, the poll
  waits 20 s on 8090 and start fails with "did not listen".
- B3 [medium]: FIFO writer survives `stop` when the lock is missing or was never
  written; `cmd_stop` kills only `lock_pid fifo` and `pkill`s only autoapp/stream
  (`auriga.sh:256,260-261`). Observed: four orphan `sleep 86400` writers. Scenario:
  pre-rework start (no lock) → `stop` → writers keep old FIFO inodes alive;
  `start` then `rm -f`+`mkfifo` (`:111-112`) so those writers can never service the
  new FIFO.
- B4 [medium]: readiness checks only that the stream server listens and that
  `autoapp` is alive (`auriga.sh:205-219`); a dongle stuck at `Waiting for
  device...` prints "Auriga head unit up." and opens Brave on an empty canvas.
  Scenario: dongle in AOA with a stale TLS session (documented recovery) → start
  succeeds, no AA session, no capture file.
- B5 [low]: stop gives clients no notice — `auriga_stream.py` installs no signal
  handler (`:29-47`), so SIGTERM drops the socket and Brave's 2 s reconnect loop
  (FR-STR-12) spins forever. FR-RUN-04 accepts "no reset", but no
  `reset`/`status` frame or close code is sent either.
- B6 [low]: `open_browser` prints "opened the default browser" even when `open`
  failed (`auriga.sh:171-173`, `|| true`).
- B7 [low]: `take_guard` is check-then-`mkdir` (`auriga.sh:78-87`); two concurrent
  starts make one die with a raw `mkdir: File exists` under `set -e` instead of the
  guard message.
- B8 [low]: `logs/` and `openauto-config/openauto.log` grow without bound (26 log
  files, `auriga.sh:25-26`, `openauto-logs.ini:12-17`), and log names use
  1-second stamps, so two starts in the same second overwrite (`auriga.sh:24`).
- B9 [low]: `check_complete` with an empty/missing `patches/` dir leaves the glob
  literal and dies with "patches/\*.patch is not applied by this script"
  (`build.sh:87-91`) instead of "no patches found".
- B10 [low]: `die` inside `$(formula ...)` (`build.sh:43,124-142`) exits only the
  substitution's subshell, so `FAILED` stays 0 there and the "failed step keeps the
  scratch tree" contract (`build.sh:59-67`) is not guaranteed for that path.
- B11 [low]: the WS port is never probed before Brave opens (`auriga.sh:205,224`);
  the server binds HTTP (`auriga_stream.py:38`) before WS (`:45`), so the first
  page load can race the WS listener.
- B12 [low]: `-d ~/x` is not expanded and `-j` is not validated (`build.sh:71-74`);
  `-jabc` fails deep inside cmake.

## Dead code, leftovers, stale comments
- L1: `scripts/auriga.sh:263-264` deletes `/tmp/auriga-mac-autoapp.pid`,
  `-stream.pid`, `-caffeinate.pid`, `/tmp/auriga-fifo-writer.pid` — nothing in the
  repo writes those files.
- L2: `.gitignore:53` ignores `*.pid`; the runtime uses a lock file, not pid files.
- L3: `.gitignore:29-31` keeps `logs/*.log` ignored but whitelists
  `logs/run-baseline-114525.filtered.log`, which is committed (baseline artefact).
- L4: `.gitignore:23-27` ignores media under `/captures/`, yet `captures/` still
  holds three tracked `*-input.jsonl` files and `captures/README.md` — a second
  capture layout that FR-STR-13 replaced.
- L5: `.gitignore:1` stale comment (pinned commits "in README.md").
- L6: `openauto-config/run.sh:35-37` re-exports `AURIGA_CAPTURE_DIR` that
  `auriga.sh:31-32` already exported; only `QT_QPA_PLATFORM` is new.
- L7: `capture/`, `PHONE-APP.md`, `MAC-PORT.md`, `openauto-plan.md`,
  `NEXT-SESSION.md`, `RUNBOOK.md` remain though FR-CAP-*/FR-PHONE-*/FR-RUN-05 are
  dropped; `phases.md:238-244` assigns the deletion to Stage 6.
- L8: `openauto-config/openauto.log` (35 KB, untracked, gitignored) plus 26
  `logs/*.log` from pre- and post-rework runs.
- L9: `captures-mac/` flat `video.h264` (5.3 MB, 09:56) and stale empty-leadership
  `audio-*.wav` (44 B) — superseded layout, kept on disk.
- L10: inert config keys in `openauto.ini` (`ScreenDPI`, `MarginWidth/Height`,
  `HandednessOfTrafficType`, `Audio.OutputBackendType`, `Input.*`,
  `Bluetooth.AdapterType`) have no reader outside `SettingsWindow.cpp`
  (grep: `getEnableTouchscreen`/`getEnablePlayerControl` have no consumers).
  Documented as inert at `docs/Android Auto head unit.md:238`, so intentional.

## Improvement areas
- I1: `auriga.sh` should pass its own ports (`--http-port "$HTTP_PORT" --ws-port
  "$WS_PORT"`) so there is one source for them, as it already does for
  `--capture-dir`/`--fifo` (B2).
- I2: Write the lock (or a `starting` marker) before launching components, and
  reconcile it on the next start, so a crash mid-start cannot leave unowned
  components (B1/B3).
- I3: Add a readiness gate on the head-unit log (`Version Received`) or on the
  first `session-*` dir, bounded by the same timeout, before printing the "up"
  banner (B4).
- I4: Have `stop` reap every FIFO writer it can identify (`pkill -f 'sleep
  31536000'`, minus its own) and optionally send a `status`/close frame before
  exit (B3/B5).
- I5: Prune `logs/` to N recent pairs and include the pid in the log name (B8).
- I6: `.auriga.lock` could record the capture dir, FIFO path and the autoapp
  binary path so `status` can show what the pair is actually running — the current
  field set cannot distinguish the stale pre-rework pair from a current one (B1).
- I7: `build.sh` could print the produced binary's mtime/version and compare it
  with `build-openauto-mac/bin/autoapp`, so "from patches" and "what runs" are
  visibly the same build (X4, A2).
- I8: Resolve both configure-line duplicates once (a shared flag array) instead of
  keeping `docs/Build.md:96-137` and `build.sh:173-200` in sync by hand; the two
  blocks currently agree, and only the doc updated on the next flag will drift.

## Interfaces
- Exposes:
  - CLI `scripts/auriga.sh {start|stop|status}`; `status` exit 0 only when FIFO,
    autoapp, stream, both ports and the session pointer are all present
    (`auriga.sh:269-292`); `start` exits 0 on a refused duplicate (`:184-189`).
  - Env contract for children: `AURIGA_CAPTURE_DIR`, `AURIGA_INPUT_FIFO` exported
    (`:31-32`); `AURIGA_PYTHON`, `AURIGA_READY_TIMEOUT`, `AURIGA_DIR` as inputs
    (`:11,17,23`).
  - Files: `<capture>/.auriga.lock` (`role pid` lines: autoapp, stream, fifo,
    caffeinate), `<capture>/.auriga.start/pid`, `<fifo>` = `/tmp/auriga-in`,
    `logs/openauto-mac-<YYYYmmdd-HHMMSS>.log`, `logs/stream-mac-<stamp>.log`.
  - `scripts/build.sh` contract: `-d DIR|-t`, `-j N`, `-h`; work root
    `.build-from-patches/` with `build-aasdk/lib/libaasdk.a`,
    `build-openauto/bin/autoapp`, `build.log`; stdout line
    `build: ok: <n> patches -> aasdk + autoapp`.
- Consumes:
  - `stream/auriga_stream.py` flags `--capture-dir`, `--fifo` only (no port flags
    are passed); the server must bind 8080/8081 itself.
  - `<repo>/build-openauto-mac/bin/autoapp` (or a newer `autoapp-*` fallback),
    `openauto.ini`, `openauto-logs.ini`, cwd = `openauto-config`
    (`openauto-config/run.sh:12,20-27`).
  - `captures-mac/` `current` symlink + `session-*` dirs + `manifest.json`
    (head unit + stream side).
  - `brew` prefixes for 11 formulae, `git`, `cmake`, `nc`, `pgrep`/`pkill`/`ps`,
    `caffeinate`, `open`, `.venv/bin/python` with `websockets`.
- Threading:
  - `auriga.sh` is a single sequential POSIX-sh process; the only concur­rency is
    `&`-launched children plus the `nc -z`/`sleep 0.25` poll loop; it holds the
    start guard from `take_guard` to `release_guard` on an `EXIT` trap.
  - `openauto-config/run.sh` execs into `autoapp` (same pid as the launched
    subshell), so `AUTOAPP_PID` is the real head-unit pid.
  - The stream server is a separate process: asyncio loop for WS plus a daemon
    thread for `ThreadingHTTPServer`; no signal handling.
  - `build.sh` runs cmake steps serially, each redirected to one shared log file.

## Open questions for the user
- Q1: The pair running now is the pre-rework build (pids 29079/29090, started
  07:41). Stop it and restart on the 09:37 binary as the first Stage 6 step, or
  leave it until the final baseline?
- Q2: Should `start` fail (non-zero) when `autoapp` never reaches `Version
  Received`, or keep the current "port is up = success" contract?
- Q3: FR-RUN-02 as written (skip the running component) or as built (refuse the
  whole pair)? Pick one and fix the other.
- Q4: Pass `--http-port/--ws-port` from `auriga.sh`, or delete the script's port
  variables and read the server defaults?
