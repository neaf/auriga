# Deviations

- **P1: topic docs document present behaviour only.** `architecture.md` and
  `docs-plan.md` assign the topic docs the target interfaces (per-session dirs +
  `manifest.json`, single viewer + keyframe request, `scripts/auriga.sh`,
  `scripts/build.sh`, `Auriga` identity) that P3-P7 implement, but `phases.md`
  gives a doc touch only to P7. Writing those as present-tense facts at P1 would
  be false and unsourced.
  Change: P1 docs state verified present behaviour; target-only contracts are
  not described. Added the doc files to the phases that change them: P3 gets
  `docs/Stream protocol.md` and `docs/Android Auto head unit.md`, P4 gets
  `docs/Stream protocol.md`, P5 gets `docs/Android Auto head unit.md` and
  `docs/Stream protocol.md`. Each phase adds its contract section when the code
  lands.

- **P1: build-green command block corrected.** The block named
  `stream/server.py` and `stream/lib/*.py`, which do not exist before P2, and
  passed `scripts/*.sh` to `py_compile`. Replaced with
  `py_compile $(find stream scripts -name '*.py')`; P7 adds `tools/*.py` after
  the move.

- **P1: audit facts corrected against the tree.** Recorded so later phases do not
  copy the audit text:
  - `patches/openauto-capture.patch` does not touch `App.cpp`. Patches 2
    (`openauto-macos`) and 3 (`openauto-auriga-usb-filter`) do.
  - AA identity block (`AndroidAutoEntity.cpp:181-202`): `display_name`
    `Crankshaft-NG`; `headunit_info` make `Crankshaft`, model `Universal`, year
    `2018`, vehicle_id `2024110822150988`; `head_unit_make` `f1x`,
    `head_unit_model` `Crankshaft-NG Autoapp`, build `1`, version `1.0`. FR-HU-10
    quotes only the `head_unit_*` pair.
  - TLS certificate and key are compiled-in PEM constants
    (`aasdk-upstream/src/Messenger/Cryptor.cpp:253,273`).
    `aasdk-upstream/cert/headunit.crt|key` is installed by CMake but not read by
    `Cryptor`.
  - `scripts/aoa_probe.py` sends `Auriga`, `Auriga Pi Headunit`,
    `Auriga AA capture`, `1.0`, `https://auriga.invalid`, `auriga-pi`, not the
    set quoted in `audit/dongle-hardware.md#D5`.
  - `btapp.db` 207-byte form: 8-byte prefix, then seven 29-byte blocks
    `13 00 01 04` + 16-byte key (+ 6 bytes) starting at `0x08, 0x25, ...`,
    trailer `00 42 54 4c f3`. The audit's one-record description does not cover
    the repeated blocks, so the doc states only the verified 29-byte stride and
    the two prefixes at `0x00`/`0x3a`. The 33-byte form is one block plus
    trailer `00 42 54 0a 53`.
  - `videoInfo.galaxy`/`.active` are invalid (zero width, height, SPS, PPS, tag);
    `btapp.db.galaxy-fresh` is 33 B, gitignored/untracked, current but
    `unverified`.

- **P2: package marker and doc updates not in the touch list.** `stream/lib/`
  needs `stream/lib/__init__.py` to import as a package from
  `stream/auriga_stream.py` and from `tests/`; it is added. Moving
  `split_nals`/`extract_sps_pps`/`build_avcc`/`find_last_idr` into
  `stream/lib/h264.py` invalidated every `auriga_stream.py:<line>` code location
  in `docs/Stream protocol.md`; repointed those to `stream/lib/h264.py` or the
  shifted `auriga_stream.py` lines. `docs/Build.md` gains
  `python -m unittest discover -s tests -v` and loses the "no automated test
  suite" sentence. The `AUDIO_CHUNK` comment is corrected 20 ms -> 40 ms (audit
  D1); no code change.

- **P2: `stream/server.py` had no creating phase.** P3 and P4 both list
  `stream/server.py` as an existing file, but no phase ever splits it out of
  `stream/auriga_stream.py`. Change: P3 now also moves `Streamer`/`serve_http`
  into `stream/server.py` and leaves `auriga_stream.py` as the CLI, plus the
  `tests/test_session.py` follower coverage. P4 gains `tests/test_clock.py` and
  `tests/test_h264.py` for the code it changes.

- **P3: touch-list additions.** Moving `Streamer`/`serve_http` into
  `stream/server.py` changed the CLI from `--video`/`--audio` to
  `--capture-dir`, and the server now follows `<capture-dir>/current`. Files that
  spell out the old layout had to move with it:
  `scripts/mac-headunit-start.sh` and `scripts/mac-headunit-stop.sh` (invocation,
  `pgrep`/`pkill` patterns), `AGENTS.md` (capture table, session bullet, `reset`
  bullet, ffmpeg paths), `stream/README.md` (manual command, `reset` lines) and
  `docs/Build.md` (the "`patches/` is incomplete" quirk: the OpenAuto side is now
  complete). The full `AGENTS.md`/`README.md` rewrites stay with P6/Stage 6.

- **P3: regenerated capture patch is complete for OpenAuto.** Regenerating
  `patches/openauto-capture.patch` from the tree also picks up the
  `IInputDeviceEventHandler.hpp` include in `AurigaInputDevice.cpp`, which P7
  listed as a fix. P7 keeps only the aasdk patch work. Verified: applying
  `openauto-capture` -> `openauto-macos` -> `openauto-auriga-usb-filter` ->
  `openauto-auriga-gps-guard` to a pristine `4cc739b8` clone reproduces
  `openauto/include` and `openauto/src` byte for byte.

- **P3: rotation is a same-name restart.** "Rotate before 4 GiB" follows the
  architecture's error-handling section: the sink truncates its file, restarts
  at offset 0 and bumps that stream's `manifest.json` count. There are no
  numbered segment files; the older segment is discarded, so a session directory
  stays under 4 GiB per stream (`SEGMENT_LIMIT` = 4 GiB - 16 MiB).
  `KEEP_SESSIONS` = 5 prunes older session directories at session start.
  `manifest.json` carries `session` plus the four segment counts only; geometry
  stays a P5 item, and `parse_manifest` defaults to 1280x720/30 until then.

- **P3: `stream/server.py` imports both ways.** `auriga_stream.py` runs as a
  script (`from lib...`) and later phases may import `stream.server` from
  `tests/` (`from .lib...`), so the module branches on `__package__` instead of
  assuming one sys.path layout.

- **P3: `stream/auriga_stream.py` was committed at its pre-P2 state.** The P2
  refactor of that file (imports from `stream/lib/h264.py`, `AUDIO_CHUNK`
  comment) was in the working tree but not in the P2 commit. P3 rewrites the file
  as the CLI, so the P2 intent lands here.

- **P4: `tests/test_server.py` added.** The phase changes the viewer model
  (single viewer, bounded queue, replay, keyframe request) and the wire
  timestamps; none of that is reachable from the pure-lib tests P4 names. The
  new file drives `Streamer.handle`, `video_loop` and `Viewer` on a temporary
  capture directory with a fake socket: replacement close code, drop order,
  unsync-on-drop, GOP replay, keyframe request, manifest geometry and
  content-clock timestamps.

- **P4: docs touched outside `docs/Stream protocol.md`.** `stream/README.md`
  and `AGENTS.md` restate the wire protocol, so a stale copy there would
  contradict the server: both gain the `keyframe` request, the `status` message,
  the single-viewer rule, the manifest geometry and the `40 ms` PCM chunk size
  (the `20 ms` text was already wrong, audit D1). Their full rewrites stay with
  P5/P6.

- **P4: replay bound and drop policy chosen.** `GOP_MAX_FRAMES = 2400` (~80 s at
  30 fps) covers the measured ~1800-frame AA GOP; on overflow the cache is
  cleared rather than truncated, because a mid-GOP replay does not decode. The
  viewer queue is 240 messages and drops audio first, then the oldest video: a
  dropped video frame marks the viewer unsynced and its deltas are skipped until
  the next keyframe (`Viewer.synced`), instead of sending frames with no
  reference. `self.synced` is the only state the queue adds.

- **P4: `{"type":"status"}` message added.** `architecture.md#Error handling`
  requires a FIFO failure to surface as status text when a viewer is connected;
  the page shows it instead of failing silently (audit B10). Client-side, a
  content-timestamp gap over 250 ms (`GAP_US`) or a decoder error triggers the
  keyframe request, which is how a reconnecting or lagging tab resyncs.

- **P4: `stream/lib/clock.py` accepts fractional fps.** `parse_manifest`
  returns fps as a float and the head unit may publish 29.97; the server rounds
  to an int for the clock and reports the same int in `hello`.

- **P4: P5's `stream/server.py` touch is now a no-op.** P4 already takes
  `hello` geometry from `manifest.json`; P5 keeps only the head-unit side that
  publishes width/height/fps. `phases.md` P5 says so.


- **P5: capture mode lives in `AurigaSession.cpp`, not an `App` static.** One
  read of `AURIGA_CAPTURE_DIR`: `captureDirectory()` (function-local static,
  creates the dir, empty value = off) plus `captureModeEnabled()`, both declared
  in `AurigaSession.hpp`. `App.cpp` and `ServiceFactory.cpp` were changed to call
  them, so `patches/openauto-macos.patch` and
  `patches/openauto-auriga-usb-filter.patch` were regenerated: the old local
  `static bool aurigaCaptureMode()` (and its `<cstdlib>`) is gone, patch 2 uses
  `projection::captureModeEnabled()` from patch 1, and patch 3 keeps only the
  `waitForUSBDevice()` guard. `openauto-auriga-identity.patch` is added as
  patch 5 (last). Verified: a pristine `4cc739b8` clone + the five patches
  reproduces the nested `openauto/` tree byte for byte (`diff -r`).

- **P5: writer queue lives in the sink, ACK order in the service.** New
  header-only `AurigaWriter` (bounded queue, 240 chunks / 64 MiB, drop-oldest
  with a counter, one writer thread per sink) is owned by
  `AurigaVideoOutput`/`AurigaAudioOutput`; the media services send the ACK
  before calling `write()`, which only copies into the queue. Rotation, the
  WAV header rewrite and `noteRotation` all run on the writer thread. The
  sinks' per-file `std::mutex` is gone; a mutex now guards only the cached
  codec-config buffer. `open()`/`stop()` still open/truncate/close the file on
  the strand (once per channel, outside the `max_unacked=1` window); only the
  per-frame path is fully off-strand.

- **P5: codec-config ACK kept.** `onMediaIndication` now calls
  `setCodecConfig()` instead of funnelling into the media writer, but still
  sends the same single media ACK and re-arms `receive()` for both video and
  audio, so the wire behaviour is unchanged and only the disk write moved. Video
  writes the cached SPS/PPS in front of the first access unit of each segment;
  audio ignores the payload. `IVideoOutput`/`IAudioOutput` gained a
  non-pure `setCodecConfig()` default no-op so the Qt/OMX/RtAudio backends are
  untouched.

- **P5: files touched outside the phase list.** `docs/Build.md` (patch count
  4→5, apply/verify lists, `App.cpp` line refs), `stream/README.md` (the
  "until the head unit publishes it" parenthetical is now false),
  `stream/server.py` (`hello` docstring only, no code change),
  `docs/AutoLink A512 dongle.md` (one `App.cpp` line ref), `tests/test_session.py`
  (head-unit manifest shape now carries geometry, plus a 1920x1080/60 and a
  29.97 fps case). `openauto-auriga-gps-guard.patch` is unchanged: the
  regenerated byte stream differs only in its `index` line and hunk header.

- **P5: stale "rename to Auriga" prose left for P6/Stage 6.** `README.md`,
  `MAC-PORT.md`, `RUNBOOK.md` and `DEVELOPING.md` still say the AA display name
  is `Crankshaft-NG` and the rename is outstanding. Those files are folded or
  deleted by P6/Stage 6; editing them now would only be churn.

- **P6: `start` refuses the pair, not one component.** FR-RUN-02 described a
  per-component `pgrep` skip. NFR-08 and `architecture.md#Interfaces` require one
  `autoapp`/stream pair per capture dir, and half a pair is useless. `start`
  checks both first and exits 0 with the `status` block when either is alive,
  instead of starting the missing one. The single-instance check is
  `<capture-dir>/.auriga.lock` (`role pid` lines, cmdline-verified); `pgrep` is
  only the fallback that finds a pair started before the lock existed.

- **P6: FIFO writer sleeps a year.** The old wrappers parked `sleep 86400`,
  which silently disabled touch after 24 h (audit B7). `auriga.sh` parks
  `sleep 31536000`: same single-writer mechanism, no expiry in a realistic run.
  The FIFO is created by `auriga.sh`; `openauto-config/run.sh` only opens it, so
  `AURIGA_CAPTURE_DIR` and `AURIGA_INPUT_FIFO` are defaulted once (audit B4/B5).

- **P6: `stop` is cmdline-checked and port preflight is new.** `stop` SIGTERMs a
  lock pid only while `ps -p <pid> -o command=` still names `autoapp` or
  `auriga_stream.py` (audit B6), waits up to 10 s for the SIGTERM/`App::stop()`
  path, then SIGKILLs, then runs the `pkill` orphan fallback and removes the
  FIFO. `start` refuses when 8080/8081 are already bound and reports a stream
  server that dies during startup with its log tail (audit B1/X2) instead of
  printing "started".

- **P6: docs outside the phase list.** Deleting the six start/stop scripts,
  `aa-tap.sh` and `run-mac.sh` invalidated instructions in `README.md`,
  `DEVELOPING.md`, `stream/README.md`, `docs/Build.md` and
  `docs/Android Auto head unit.md`; all are repointed at `scripts/auriga.sh` and
  the Pi/tunnel sections are gone. `docs/Android Auto head unit.md` gains the
  `## Runtime` section (lock, readiness, single env source). `MAC-PORT.md`,
  `RUNBOOK.md`, `NEXT-SESSION.md` and `openauto-plan.md` keep the old script
  names in their 2026-10-28 history; Stage 6 deletes them.

- **P6: no start/stop cycle run in-phase.** A live pair (autoapp 29079, stream
  29090) held the dongle for the whole phase, so `start` was exercised only on
  its refuse path and `stop` was not run at all. Ran: `bash -n`, `py_compile`,
  `unittest` (94), both builds, `status` against the live pair, `start`
  refusal, `usage` exit 2, and the `run.sh` missing-env guard. The
  `start`→`status`→`stop` cycle is M7, run when the dongle is free.

- **P7: `scripts/build.sh` keeps its artifacts by default.** A script that
  built into a throwaway directory could not satisfy the phase exit criterion
  ("a fresh clone + `scripts/build.sh` produces a working `autoapp`"). Default
  work root is `.build-from-patches/` (gitignored; sources, build dirs,
  `build.log`); `-t` is the disposable variant (mktemp, removed on success, kept
  on failure so the log survives); `-d DIR` chooses another root. Both modes run
  the same clone -> apply -> configure -> build path, and neither reads or
  writes the nested `openauto/`/`aasdk-upstream/` clones or `build-*-mac`, so it
  is safe while the head unit is up. The script also refuses to run when
  `patches/` holds a patch that its ordered lists do not apply (the FR-BLD-02
  self-check).

- **P7: verification built into `/tmp/auriga-p7-check`, not the repo.** The live
  pair (autoapp 29079, stream 29090) and the existing build dirs were left
  alone: `./scripts/build.sh -d /tmp/auriga-p7-check -j8` (full clone + 7
  patches + both targets), then the same command again on the existing tree to
  exercise `prepare_tree`'s reset branch and the cmake incremental path. The
  temp variants (`-t` success/cleanup, `-t` failure/keep, the unapplied-patch
  guard, `-h`, unknown option) were exercised with a stub `cmake` on `PATH` so
  no second cold build was needed.

- **P7: docs and files outside the phase touch list.**
  `docs/AutoLink A512 dongle.md` (six `scripts/aoa_*` -> `tools/aoa_*`; the AA
  1.7 paragraph now names `patches/aasdk-version-absl.patch` instead of saying
  no patch carries the bump), `README.md` (the two `tools/` entries),
  `DEVELOPING.md` (aasdk patch row, apply list, reverse check, regeneration
  command), `.gitignore` (`/.build-from-patches/`), and `docs/Build.md` capture
  verification paths (`captures-mac/current/...`, stale since P3).

- **P7: `patches/` completeness re-verified, not just reverse-applied.** A
  pristine aasdk `9bf6adf` + `aasdk-usb-filter` + `aasdk-version-absl` is
  byte-identical to `aasdk-upstream/` (`diff -r`, no `.git`), and a pristine
  openauto `4cc739b8` + the five OpenAuto patches is byte-identical to
  `openauto/`. All seven patches also `--check --reverse` clean against the live
  trees.
