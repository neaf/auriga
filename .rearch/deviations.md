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
