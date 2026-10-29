# Phases

Ordered phase plan. One phase = one session, ≤ ~15 files touched. Every phase
leaves the build green (`cmake --build` for both targets, `py_compile`,
`bash -n`) and the working requirements functional. The manual checklist M1–M7
replaces the baseline M1–M8 (M8 Pi fallback is dropped).

Manual checklist (reused every phase after P2):

- M1: Cold start — dongle MTP `2717:ff40` → AOA `18d1:2d00`; phone projects.
- M2: Phone stays MTP+ADB `04e8:6860` during projection (`svc usb getFunctions` = `mtp`).
- M3: Brave at `http://localhost:8080` shows live 1280x720 AA UI.
- M4: Canvas taps + `echo 'tap 640 360' > /tmp/auriga-in` change the phone UI.
- M5: Audio audible after unmute (48 kHz/16-bit stereo).
- M6: `captures-mac/` session dir decodes with ffmpeg; WAV non-empty; `input.jsonl` records taps.
- M7: `auriga.sh stop` stops autoapp + stream; a second start refuses a duplicate.

Build-green commands (every phase):

```bash
cmake --build build-aasdk-mac --target aasdk -j8
cmake --build build-openauto-mac --target autoapp -j8
.venv/bin/python -m py_compile $(find stream scripts -name '*.py')
for f in scripts/*.sh openauto-config/*.sh; do bash -n "$f"; done
```

---

## Phase 1: topic docs from audit facts

Goal: write the external-system topic docs from the verified audit facts only.
No code changes.

Covers: FR-DGL-01..06, CON-DGL-01..03, CON-HU-01..02, CON-STR-01, CON-BLD-01.

Touches (new): `docs/AutoLink A512 dongle.md`, `docs/Android Auto head unit.md`,
`docs/Stream protocol.md`, `docs/Build.md`.

Deletes: none.

Verify: build-green commands (unchanged code); no behavioral test.

Manual: none (doc-only).

Exit: each doc has present-tense facts with source (code location / capture /
vendor doc) and `unverified` marks where the audit flagged them; no history, no
Pi/phone-app/capture exploratory prose; `videoInfo.galaxy` marked invalid,
`btapp.db.galaxy-fresh` marked current-but-unverified.

---

## Phase 2: test harness + pure lib extraction

Goal: add a runnable test harness and extract the pure logic out of
`auriga_stream.py` so it is testable without hardware. No behavior change.

Covers: NFR-02 (content clock foundation), FR-STR-03 (NAL split).

Touches: `stream/lib/h264.py` (new: `split_nals`, `extract_sps_pps`,
`build_avcc`, `find_last_idr` moved), `stream/lib/clock.py` (new: content
clock), `stream/lib/session.py` (new: session naming, retention prune, manifest
parse — pure), `stream/auriga_stream.py` (import from lib), `tests/__init__.py`,
`tests/test_h264.py`, `tests/test_clock.py`, `tests/test_session.py`,
`tests/fixtures/` (synthetic Annex-B + manifest samples).

Deletes: none.

Verify:
```bash
.venv/bin/python -m unittest discover -s tests -v
```
plus build-green commands.

Manual: M1, M3, M4, M5 (no behavior change; confirm still live).

Exit: `unittest` passes with no dependency beyond stdlib; `auriga_stream.py`
still runs and streams; no behavior regression.

---

## Phase 3: capture session model (the seam)

Goal: replace truncate-on-session with per-session dirs + `current` pointer +
`manifest.json`, and make the stream server follow them. This is one coupled
change: head-unit sinks and stream server must move together or the stream
breaks.

Covers: FR-STR-13, FR-STR-07 (reset via `current`), NFR-05 (retention), NFR-08
(lock foundation).

Touches: `patches/openauto-capture.patch` (add SessionManager: mint id, create
`session-<id>/`, atomic `current`, write `manifest.json`, retention prune; wire
video/audio/input sinks to the shared id; segment rotation; regenerate), nested
`openauto/` working tree, `stream/lib/session.py` (manifest follower),
`stream/server.py` (new; `Streamer` + `serve_http`, resolve `current`, reset on
pointer change, reopen on segment-count change), `stream/auriga_stream.py`
(thin CLI), `tests/test_session.py` (follower),
`scripts/mac-headunit-start.sh` + `scripts/mac-headunit-stop.sh`
(`--capture-dir`, pgrep/pkill), `docs/Stream protocol.md`
(session/`current`/manifest section), `docs/Android Auto head unit.md` (capture
file contract), `docs/Build.md` (patch-completeness quirk), `AGENTS.md` and
`stream/README.md` (capture paths, session reset).

Deletes: the `size < offset` truncation heuristic in the stream server.

Verify: build-green; `python -m unittest`; then
```bash
./scripts/auriga.sh status   # or existing start script until P6
```
Manual: M1, M6 (a reconnect creates a new `session-*` dir and preserves the
prior one), M3 (reset + hello on session change).

Exit: two consecutive AA sessions produce two `session-*` dirs; the stream
server switches on `current` with no stale replay; retention prunes beyond the
cap; no references to truncate-on-session remain in the sink.

---

## Phase 4: stream server rework + browser

Goal: single viewer with a bounded drop-oldest queue, content clock end-to-end,
bounded GOP replay + keyframe request, geometry from `manifest.json`.

Covers: FR-STR-14, FR-STR-05, FR-STR-09..12, NFR-02, NFR-03, FR-STR-07
(reset semantics), FR-STR-01/02/04/06/08 (refactored).

Touches: `stream/server.py` (per-viewer queue, single viewer, content clock,
keyframe request, manifest geometry in `hello`), `stream/web/app.js` (re-anchor
on backward jump, queue-aware decode, `{"type":"keyframe"}`, single-socket
handling), `stream/web/index.html` (canvas sized from `hello`),
`stream/lib/clock.py`, `stream/lib/h264.py`, `tests/test_clock.py`,
`tests/test_h264.py`, `docs/Stream protocol.md`
(single-viewer, keyframe request, content clock, `hello` geometry).

Deletes: `max_gop`/`VIDEO_FRAME_US` dead branches, the multi-client broadcast
under lock.

Verify: `python -m unittest`; build-green; open two tabs → second replaces the
first (single viewer).

Manual: M3, M4, M5, M6; reconnect mid-GOP decodes a clean picture quickly.

Exit: exactly one viewer; capture loop never awaits a socket; backward
timestamp jumps recover without silence; A/V sync derives from content clock.

---

## Phase 5: head-unit behavior fixes

Goal: take file I/O out of the AA flow-control path, separate codec config from
media, publish geometry, rename AA identity, single capture-mode switch.

Covers: NFR-01, NFR-02, FR-HU-10, FR-STR-02 (geometry), FR-HU-02 (one env read).

Touches: `patches/openauto-capture.patch` (buffered writer + immediate ACK in
`VideoMediaSinkService`/`AudioMediaSinkService`; cache codec config, prepend
SPS/PPS once per segment; emit width/height/fps into `manifest.json`), new
`patches/openauto-auriga-identity.patch` (display_name/make/model → `Auriga`),
`patches/openauto-macos.patch` (one `AURIGA_CAPTURE_DIR` read shared by `App`
and `ServiceFactory`), `stream/server.py` (use manifest geometry in `hello`),
`docs/Android Auto head unit.md` (ACK-before-write, codec-config separation,
identity, geometry), `docs/Stream protocol.md` (`hello` geometry source).

Deletes: the two independent `getenv` capture-mode definitions (one stays).

Verify: build-green (clean re-apply of all patches, see P7); `python -m unittest`.

Manual: M1, M2, M6 (ffprobe: WAV has no config bytes; video head is SPS/PPS only);
sustained load shows no AA stall.

Exit: media ACK is sent before disk write; the channel strand performs no file
I/O; WAV contains only PCM after the 44-byte header; `hello` reports the
configured geometry.

---

## Phase 6: runtime orchestration consolidation

Goal: one `auriga.sh` start/stop/status for macOS, single-instance lock,
readiness poll, single source for FIFO + capture dir.

Covers: FR-RUN-01..04, FR-RUN-06, NFR-03, NFR-04, NFR-07, NFR-08.

Touches: `scripts/auriga.sh` (new), `openauto-config/run.sh` (new macOS-only,
consolidated from `run-mac.sh`), `AGENTS.md` (start/stop commands).

Deletes: `scripts/mac-headunit-start.sh`, `scripts/mac-headunit-stop.sh`,
`scripts/pi-start.sh`, `scripts/pi-stop.sh`, `scripts/mac-start.sh`,
`scripts/mac-stop.sh`, `scripts/aa-tap.sh`, `openauto-config/run-mac.sh`, and the
old Pi contents of `openauto-config/run.sh` (replaced in place).

Verify: `bash -n scripts/auriga.sh openauto-config/run.sh`; build-green;
`./scripts/auriga.sh start` then `status` then `stop`.

Manual: M1–M7 full pass; readiness waits for the 8080 socket (not `sleep 1`);
exporting `AURIGA_INPUT_FIFO=/tmp/x` taps still land in the file autoapp reads.

Exit: no `sleep 1` readiness; one lock file guards the dongle/capture dir; no
Pi/`aa-tap` scripts remain; FIFO path resolved once.

---

## Phase 7: build from patches

Goal: make `patches/` the complete, self-verifying source of truth and add a
one-command rebuild.

Covers: FR-BLD-01..04, FR-BLD-06, FR-BLD-07, FR-BLD-02.

Touches: new `scripts/build.sh` (clone upstreams to a temp dir, apply all
patches in order, configure, build), new `patches/aasdk-version-absl.patch`
(`Version.hpp` 6→7 + protobuf absl include), `docs/Build.md` (patch order),
`tools/` move for `aoa_probe.py`/`aoa_read.py`. No `openauto-capture.patch`
change: P3's regenerated patch already includes the
`IInputDeviceEventHandler.hpp` include.

Deletes: none. Dropped-file cleanup happens in Stage 6 per `docs-plan.md`.

Verify:
```bash
./scripts/build.sh            # clean, from patches only
cmake --build build-aasdk-mac --target aasdk -j8
cmake --build build-openauto-mac --target autoapp -j8
.venv/bin/python -m py_compile tools/*.py
```
and `git -C openauto apply --check --reverse <patch>` for every patch (absolute
paths).

Manual: M1 (projection works from a clean-patches build).

Exit: a fresh clone + `scripts/build.sh` produces a working `autoapp` with no
manual aasdk edits; every patch reverse-applies; `patches/` fully describes the
nested trees.

---

## Stage 6 (not a code phase): cleanup + traceability

Stage 6 owns every deletion listed in `docs-plan.md`: delete `capture/`,
`PHONE-APP.md`, the exploratory docs and `.rearch/`; drop the `rearch-base` tag
and `rearch/*` branches after the final traceability audit; move
`requirements.md` and `architecture.md` into `docs/`; update `README.md` /
`AGENTS.md`; run the full baseline and M1–M7. No code phase follows P7.
