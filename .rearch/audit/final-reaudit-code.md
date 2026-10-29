# Audit: final re-audit of phase 8 code fixes

Scope: `patches/*.patch`, the nested `openauto/` files they touch, `stream/`
(server, libs, web), `tests/`, `scripts/`, `tools/`. Re-audit of commit
`00b5be6` (`rearch(phase 8): fix final audit findings`) against the five final
module audits and the current `.rearch/requirements.md`.

Verification run (read-only): all 7 patches `git apply --check --reverse` OK;
a pristine `openauto` clone at `4cc739b8` + the 5 OpenAuto patches `diff -r`
equals `openauto/` exactly (empty diff); a pristine `aasdk-upstream` clone at
`9bf6adf` + the 2 aasdk patches `diff -r` equals `aasdk-upstream/` exactly;
`.venv/bin/python -m unittest discover -s tests` → **100 tests OK** (was 94);
`py_compile` on all 4 Python entry points OK; `sh -n` on both scripts OK;
`c++ -fsyntax-only` on `AurigaVideoOutput.cpp` and `AurigaInputDevice.cpp`
with the real build flags → OK (warnings only, from abseil).

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| `patches/openauto-capture.patch` | 2229 | phase-8 hunks (395 lines) + all 5 changed files read in full as applied sources; rest unchanged since the prior audit and covered by the pristine-clone `diff -r` |
| `patches/openauto-macos/usb-filter/gps-guard/identity`, 2 × `aasdk-*` | 313 | unchanged this commit; verified by reverse-apply + clone diff |
| `openauto/src/autoapp/Projection/AurigaVideoOutput.cpp` | 253 | yes |
| `openauto/include/.../AurigaVideoOutput.hpp` | 78 | yes |
| `openauto/include/.../AurigaWriter.hpp` | 234 | yes |
| `openauto/src/autoapp/Projection/AurigaInputDevice.cpp` | 273 | yes |
| `openauto/include/.../AurigaInputDevice.hpp` | 62 | yes |
| `openauto/src/autoapp/Projection/AurigaAudioOutput.cpp` | 237 | yes |
| `openauto/src/autoapp/Projection/AurigaSession.cpp` | 285 | yes |
| `openauto/include/.../AurigaSession.hpp` | 76 | yes |
| `openauto/src/autoapp/Service/ServiceFactory.cpp` | 282 | 60-282 (unchanged 1-59 from prior audit) |
| `openauto/src/autoapp/App.cpp` | 269 | excerpts 30-70, 215-269 |
| `openauto/src/autoapp/autoapp.cpp` | 314 | grep 239-248 |
| `openauto/.../MediaSink/VideoMediaSinkService.cpp` | 267 | excerpts 165-215 + `videoOutput_->` sites |
| `openauto/.../MediaSink/AudioMediaSinkService.cpp` | 248 | excerpts 195-235 |
| `openauto/.../Sensor/SensorService.cpp` | 296 | excerpts 25-60, 225-285 |
| `openauto/.../AndroidAutoEntity.cpp` | 375 | excerpts 170-205 |
| `openauto/.../InputSource/InputSourceService.cpp` | 207 | excerpts 95-135, 172-192 |
| `aasdk-upstream/src/USB/USBHub.cpp` | 165 | excerpts 80-145 |
| `stream/server.py` | 576 | yes |
| `stream/lib/h264.py` | 228 | yes |
| `stream/lib/session.py` | 214 | yes |
| `stream/lib/clock.py` | 62 | unchanged this commit (prior audit, full) |
| `stream/auriga_stream.py` | 64 | yes |
| `stream/web/app.js` | 398 | yes |
| `stream/web/index.html` | 39 | yes |
| `tests/test_server.py` | 359 | yes |
| `tests/test_h264.py` | 232 | diff (14 lines) + class list |
| `tests/test_session.py`, `tests/test_clock.py` | 341 / 83 | unchanged this commit |
| `scripts/auriga.sh` | 315 | yes |
| `scripts/build.sh` | 213 | 1-60, 80-145 (unchanged this commit) |
| `tools/aoa_probe.py` | 132 | yes |
| `tools/aoa_read.py` | 90 | yes |
| `.rearch/requirements.md` | 353 | yes |
| 5 prior final audits | 998 | yes |
| `.rearch/deviations.md` (P8 section) | 35 | yes |

## Prior findings: disposition
14 high/medium findings from the five final audits, 25 low ones.

| Prior | Sev | Disposition |
| --- | --- | --- |
| headunit B1 loss of codec config for a segment | med | **fixed**: `AurigaVideoOutput.cpp:186-194` appends the cached SPS/PPS at the current offset, `:207-227` `writeCachedCodecConfig`, `:179-184` warns when media precedes config |
| headunit B2 `start()` after `quit` → `std::terminate` | med | **fixed**: `AurigaInputDevice.cpp:55-59` clears `running_` and joins before spawning; `:71-74` reopens the log only when closed |
| headunit B3 sink reopened after `stop()` accepts, writes nothing | med | **not fixed**: `AurigaWriter::start()` still returns on `stopping_` (`AurigaWriter.hpp:69-72`) while `AurigaVideoOutput::open()`/`AurigaAudioOutput::open()` return `true` (`:43-69` / `:67-92`). Reachable only if `videoOutput_->stop()` (`VideoMediaSinkService.cpp:48`, entity shutdown) is followed by another channel open |
| headunit B8 dropped media invisible downstream | med | **fixed in substance**: `take_drop_flag` (`AurigaWriter.hpp:144-150`) + delta skip until the next IDR with SPS/PPS re-written (`AurigaVideoOutput.cpp:153-173`); the file no longer holds an undecodable reference chain. Residual: still no manifest marker, only a log line |
| stream B1 stale avcC after a rollover | med | **fixed**: `server.py:305-309` sets `codec_stale`, `:361-367` re-reads the segment head and sends a new `hello` when SPS/PPS differ; test `tests/test_server.py:239-273` |
| stream B2 `refresh_codec` IndexError killing `session_loop` | med | **fixed**: `usable_parameter_sets` (`server.py:60-66`), `build_avcc` raises instead of mis-building (`h264.py:72-79`), `sps_pps_from_bytes` rejects short SPS (`:56`), `session_loop` catches (`server.py:244-256`); tests `test_h264.py:84-90,110-115`, `test_server.py:275-286` |
| browser B1 queue overflow disables resync | med | **fixed**: `app.js:212-217` calls `requestKeyframe()` instead of only setting `needKey` |
| runtime B1 live pair is the pre-rework stack | **high** | **not fixed** (state, not code): `ps` still shows pid 29079 `build-openauto-mac/bin/autoapp` and pid 29090 `auriga_stream.py --video … --audio …`, both started 07:41; `captures-mac/` is still the flat layout with no `current`, no lock; the 10:02 binary and the new server have never run |
| runtime B2 ports duplicated / never passed to the server | med | **fixed**: `auriga.sh:23-24` (`AURIGA_HTTP_PORT`/`AURIGA_WS_PORT`), `:130-132` passes both, `server.py:541-576` serves `/config.json`, `app.js:42-53` reads it |
| runtime B3 FIFO writer orphans | med | **fixed**: `auriga.sh:115` reaps at start, `:274` at stop |
| runtime B4 readiness does not check the AA session | med | **not fixed**: `auriga.sh:212-231` still probes only the two sockets + `kill -0`; a dongle at `Waiting for device...` still prints "Auriga head unit up." |
| docs B1 `aoa_probe` shells out to `lsusb` on macOS | med | **fixed**: `aoa_probe.py:46-70` uses `ioreg` on Darwin, catches `FileNotFoundError/OSError/SubprocessError`; `:115-121` validates the mode |
| docs B2 `aoa_read` uncaught `claim_interface` | med | **fixed** (`aoa_read.py:36-46`) but the tool is now broken earlier by a **new** bug, see B1 below |
| docs B6 verification commands point at the flat capture path | med | **docs fixed**; the state is still wrong → same as runtime B1 |

Low findings: 15 fixed, 10 open (open: headunit B5 99-suffix mint, B6 busy-spin on `sink_`, B9 non-atomic WAV header rewrite; browser B4 `onerror` no reconnect, B5 permanent `4001` latch; runtime B5 stop gives clients no notice, B8 unbounded `logs/`, B9 empty-`patches/` glob, B10 `die` inside `$( )`, B12 `-d ~/x`, `-j` unvalidated).

## Functional behavior
Kept FRs mapped to live code: **36 of 36** (HU-01..11, STR-01..14, RUN-01/02/03/04/06, BLD-01/02/03/04/06/07). No kept FR is unimplemented and none is backed only by dropped files.

- F1 (FR-HU-01, FR-DGL-02): AOA switch restricted to `2717:ff40`; `autoapp.cpp:242-246` passes `0x2717, 0xFF40`; `USBHub.cpp:89-101` is the source filter, `:114-116` returns for any non-matching device, `:121-123` rejects `cAOAPWithAdbId` under a filter; `App.cpp:56-63` skips the all-device enumerator in capture mode. Active.
- F2 (FR-HU-02): one env read, `AurigaSession.cpp:38-64`; substitutes video `ServiceFactory.cpp:239-246`, 3 audio sinks `:197,205,231`, input `:177-187`, mic `:257-264`, TCP `App.cpp:39-40,182-184`. Active. Two predicates remain (`captureSession_ != nullptr` vs `captureModeEnabled()`), still consistent because both derive from the same env.
- F3 (FR-HU-03): Annex-B AU append, `flush()` per access unit (`AurigaVideoOutput.cpp:196-198`); the strand only copies (`:77-86`). Active.
- F4 (FR-HU-04): 48000/2/16, 16000/1/16, 16000/1/16 (`ServiceFactory.cpp:197,205,231`), 44-byte header rewritten every 1 s of audio (`AurigaAudioOutput.cpp:170-175,178-210`). Active.
- F5 (FR-HU-05): silent mic, `ServiceFactory.cpp:258-259`, 20 ms zero buffers (`AurigaAudioInput.cpp`). Active.
- F6 (FR-HU-06, FR-HU-07): stdin/FIFO line protocol + JSONL (`AurigaInputDevice.cpp:187-229,253-268`); the reader starts only on a `STATUS_SUCCESS` `KeyBindingRequest` (`InputSourceService.cpp:102-124`, `start()` at `:122`). Active.
- F8 (FR-HU-08): `UNRESTRICTED`, night mode re-read each 250 ms poll, `gps_read` guarded by `gpsEnabled_` (`SensorService.cpp:37-52,239-270`). Active.
- F9 (FR-HU-09): dummy Bluetooth, `STATUS_SUCCESS`, PIN `123456`, `BLUETOOTH_PAIRING_UNAVAILABLE` (`BluetoothService.cpp`, `DummyBluetoothDevice.cpp`; `ServiceFactory.cpp:141-150,155-169`). Active.
- F10 (FR-HU-10): `Auriga` ×5, `DRIVER_POSITION_RIGHT`, ping 1000/3000/5 (`AndroidAutoEntity.cpp:181,193-200`). Active; the requirement text is now correct.
- F11 (FR-HU-11): reconnect only via `onAndroidAutoQuit → waitForDevice` (`App.cpp:224-251`); the hub-error retry stays commented out (`:253-265`). Active.
- F13 (FR-STR-13, NFR-05): `SEGMENT_LIMIT = 4 GiB - 16 MiB`, `KEEP_SESSIONS = 5` (`AurigaSession.hpp:40,42`); rotate `AurigaVideoOutput.cpp:231-248`, `AurigaAudioOutput.cpp:215-232`; prune `AurigaSession.cpp:235-280`; manifest rename `:182-211`; `current` symlink rename `:215-233`. Active.
- F14 (FR-STR-01/02/07/14): `serve_http` + `/config.json` (`server.py:541-576`), `hello` (`:218-238`), session change = drop queue + `reset` + `hello` + clock restart (`:258-294`), single viewer with `4001` (`:469-490`). Active.
- F15 (FR-STR-03/04/05): `split_nals`/`FrameAssembler`/`avcc_sample` (`h264.py:15-41,90-92,128-188`), `find_last_idr` 8 MiB window (`:95-125`), `GopBuffer` 2400 frames (`:191-227`), replay (`server.py:459-467`). Active.
- F16 (FR-STR-06): byte-44 audio tail, 4-byte alignment, 7680-byte chunks, media-only (`server.py:409-457`). Active.
- F17 (FR-STR-08): `<cmd> <x> <y>\n` per event through a fresh `O_WRONLY|O_NONBLOCK` fd (`server.py:507-528`). Active.
- F18 (FR-STR-09/10/11/12): decode/draw/audio (`app.js:135-179,255-296`), muted default + gesture-created context (`:243-253,374-396`), gesture semantics incl. primary-pointer filter (`:320-372`), 2 s reconnect on close (`:64-77`). Active.
- F19 (FR-RUN-01/02/03/04/06): `auriga.sh:183-238` start (guard → FIFO → autoapp → stream → HTTP poll → WS poll → alive checks → caffeinate → lock → summary → browser), `:265-280` stop, `:282-305` status; FIFO `:112-120`; all-or-nothing `:189-196`. Active.
- F20 (BLD-01/02/03/04/06/07): `build.sh` clones `9bf6adf`/`4cc739b8`, applies 2+5 patches in order (`:29-37,95-122`), `check_complete` (`:85-92`), Boost 1.85 + `CMAKE_POLICY_VERSION_MINIMUM=3.5` (`:173-200`). `AASDK_MINOR = 7` at `aasdk-upstream/include/aasdk/Version.hpp:23`. Active, and the patch→tree reproduction now proven by `diff -r`.
- F21 (NFR-01): media ACK sent before `write()` (`VideoMediaSinkService.cpp:177-190`, `AudioMediaSinkService.cpp:209-221`); the write is a bounded queue push (`AurigaWriter.hpp:80-116`). Active, satisfied.
- F22 (NFR-02/07/08): 8 ms poll (`server.py:51`), per-AU flush, socket-level readiness poll + lock/guard (`auriga.sh:80-110,143-150`). Active.

## External facts and quirks
- X1: `build-openauto-mac/CMakeFiles/autoapp.dir/.../AurigaVideoOutput.cpp.o` and `AurigaInputDevice.cpp.o` are 10:02, i.e. newer than the 10:01-10:02 sources — the phase-8 C++ did compile into `bin/autoapp-2026.10.29+git.4cc739b.dirty`. The patch file was re-edited at 10:11, after that build, so the binary predates the final patch text (content unchanged per `diff -r`). Source: mtimes.
- X2: reverse-applying all 7 patches is not proof that `patches/` reproduces the trees (a duplicated hunk still reverse-applies). The authoritative check, now documented at `docs/Build.md:44-46`, is clone + apply + `diff -r`; both trees pass it today. Source: `deviations.md` P8 + this audit's run.
- X3: `brew --prefix` remains a hard dependency of `build.sh:143-152`; a missing formula aborts inside `$(formula …)`, so `FAILED` stays 0 and the "keep the scratch tree" contract (`:59-67`) is not guaranteed on that path. Source: code.
- X4: `nc -z` is still the only readiness probe (`auriga.sh:51`); no timeout beyond the shell loop. Source: code.
- X5: the FIFO writer is one `sleep 31536000`; `pkill -f "sleep 31536000"` (`auriga.sh:115,274`) matches every such writer on the host, not only this capture dir's. Source: code.
- X6: `serve_http` still uses `SimpleHTTPRequestHandler`, so `/config.json` is special-cased but directory listings and every file under `stream/web` are still served (`server.py:550-563`). Source: code.
- X7: `websockets.serve(..., max_size=None)` unchanged (`auriga_stream.py:49`); an unbounded text frame is accepted, loopback is the only boundary. Documented `docs/Stream protocol.md:251`. Source: code + doc.
- X8: `macOS` has no `lsusb`; `aoa_probe.py` handles that, `aoa_read.py` does not touch host tools. Source: code.

## Doc and code inconsistencies
- D1: `docs/Stream protocol.md:191` says "reconnect every 2 s after a close" — true — and no longer promises reconnect on error, matching `app.js:64-78` (`onerror` only rewrites the status). Prior D1 resolved.
- D2: `docs/Stream protocol.md:54` now says audio starts at end of file even when the WAV appears late (`open_when_ready(..., at_end=True)`) — matches `server.py:311-328,419-420`. Prior D4 resolved.
- D3: `docs/Stream protocol.md:194` says a decode queue over 2400 chunks triggers a keyframe request — matches `app.js:212-217`. Prior D2/D8 resolved.
- D4: `docs/Android Auto head unit.md:154` says `fps` is written as an integer and fractional rates are not produced — matches `AurigaSession.cpp:186` (default `double` formatting) and `configuredVideoGeometry` (`ServiceFactory.cpp:71-95`, only 30.0/60.0). Prior D6 resolved.
- D5: `docs/Build.md:44-46` names `diff -r` against a patched pristine clone as the reliable check and the 7 reverse-applies as a smoke check — matches the behaviour observed here. Prior D12 superseded.
- D6: `docs/Stream protocol.md:80` claims a rollover re-reads the segment head and sends `hello` when SPS/PPS differ — code matches (`server.py:305-309,361-367`) but see B2: the page is left without a keyframe.
- D7: `requirements.md:277-280` (NFR-07) says "polls HTTP then WS (`nc -z`, 20 s)" — matches `auriga.sh:212-221`. Prior D5 resolved.
- D8: `docs/Android Auto head unit.md:158` says "SPS/PPS once at the head of each segment"; with the late-config fix and the drop resync the file can carry a second parameter-set pair mid-segment (`AurigaVideoOutput.cpp:186-194,169-173`). Wording, not behaviour.
- D9: `docs/Build.md:240` now names `autoapp-2026.10.29+git.4cc739b.dirty` and flags the older build generically — matches `build-openauto-mac/bin/` (both binaries present, symlink → 10.29). Prior D7/D24 resolved.

## Assumptions to revalidate
- A1: the new binary is never exercised. Every HU fix (B1/B2/B8) and every stream fix is unproven on hardware: the running pair is the 07:41 stack (runtime B1). Revalidate by `scripts/auriga.sh stop && start` and one full AA session.
- A2: "any AOA device that is not `18d1:2d01` is the dongle" is unchanged (`USBHub.cpp:89-101,114-123`). A phone left in AOA with ADB off is still accepted. Baked into the filter; unchanged by phase 8.
- A3: codec-config ordering. The fix tolerates media-before-config, but if the phone *never* sends `MEDIA_MESSAGE_CODEC_CONFIG` the segment head stays SPS/PPS-free and the page shows "no avcC description from server" forever (`AurigaVideoOutput.cpp:179-184` logs it once).
- A4: one slice per VCL, 4-byte start codes (CON-HU-01). `containsIdr` (`AurigaVideoOutput.cpp:126-136`) and `FrameAssembler` both depend on it.
- A5: `AURIGA_CAPTURE_DIR` is on APFS (rename over symlink, >4 GiB files). `publishCurrent`/`writeManifest` unchanged.
- A6: Python ≥3.10 for the tests (`asyncio.Event()` in `Viewer.__init__`, `server.py:88`); `.venv` is 3.14.8, system 3.9 fails.
- A7: the browser can reconfigure `VideoDecoder` on every `hello` without a decoder flush race; `configureVideo` closes the old decoder first (`app.js:128-136`). Unverified for the mid-stream codec-change case (B2).
- A8: `AURIGA_HTTP_PORT`/`AURIGA_WS_PORT` are only honoured through `auriga.sh`; a direct `auriga_stream.py` run uses its own defaults (`--http-port 8080`, `--ws-port 8081`) and still tells the page via `config.json`, so direct runs are consistent.

## Bugs
- B1 [medium, **new**]: `tools/aoa_read.py:64-68` cannot run. `f"OUT={ep_out.bEndpointAddress:#x if ep_out else 'none'}"` puts a conditional in the *format spec*: with an OUT endpoint present the format spec is `#x if ep_out else 'none'` → `ValueError: Invalid format specifier`; with `ep_out is None` the field itself raises `AttributeError: 'NoneType' object has no attribute 'bEndpointAddress'`. Verified both paths in the venv. Scenario: dongle in AOA, run the tool → traceback at the endpoint banner, before any read. Regression from the phase-8 rewrite of the same lines that fixed prior docs-B2.
- B2 [medium, **new**]: a codec-change `hello` leaves the page waiting for an encoder IDR. `server.py:361-367` re-applies SPS/PPS and calls `send_hello()` without replaying the GOP; `app.js:102-104` → `configureVideo` (`:135-168`) tears the decoder down and sets `needKey = true`, and `app.js:205-206` returns on a delta *before* the gap check at `:207-209`, so no `keyframe` request is sent. Scenario: encoder reconfigures (SPS/PPS change) at a 4 GiB rollover → picture frozen until the next AA IDR (~60 s), although the server holds a decodable cache. Same shape as the fixed browser-B1, one branch over.
- B3 [medium, remaining]: sink reopened after `stop()` reports `STATUS_SUCCESS` and writes nothing (`AurigaWriter.hpp:69-72` vs `AurigaVideoOutput.cpp:43-69`, `AurigaAudioOutput.cpp:67-92`). Scenario: `VideoMediaSinkService` stop (`:48`) then a second channel open inside one entity → `video.h264` stays at 0 bytes, the queue grows to 64 MiB.
- B4 [medium, remaining]: readiness still accepts a head unit that has no AA session (`auriga.sh:222-231`); a dongle at `Waiting for device...` yields "Auriga head unit up." and a blank canvas.
- B5 [high, remaining, state]: the live rig is the pre-rework stack (pids 29079/29090, obsolete `--video/--audio` CLI, no lock, no `current`, flat `captures-mac/`). Nothing in the code detects it; `status` reports green ports.
- B6 [low, new]: `Viewer.dropped` is still only read by tests (`server.py:89,146,153`; `tests/test_server.py:115`), so queue-cap drops remain invisible in production, which is the mechanism behind B2's freeze.
- B7 [low, new]: `stream/server.py:20-45` still carries the duplicated `if __package__` import block (identical 13-name list twice); an import added on one side only is a `NameError` at call time.
- B8 [low, new]: `app.js:78` `socket.onerror` never schedules a reconnect; a browser that fires `error` without `close` stays dead until reload.
- B9 [low, remaining]: `app.js:70-74` latches `replaced` forever on `4001`; recovery needs a page reload.
- B10 [low, remaining]: `mintSessionId` caps the suffix search at 99 (`AurigaSession.cpp:92-100`) and can return a colliding id that shares an existing directory.
- B11 [low, remaining]: WAV header rewrite is an in-place 44-byte seek+write (`AurigaAudioOutput.cpp:178-210`) on the file the server tails; a concurrent reader can see a half-updated header.
- B12 [low, remaining]: `auriga.sh:276-277` still deletes `/tmp/auriga-mac-*.pid` and `/tmp/auriga-fifo-writer.pid`, which nothing creates.
- B13 [low, remaining]: the writer busy-spins when `sink_` is empty (`AurigaWriter.hpp:182-185`) — unreachable today, every sink passes a lambda.
- B14 [low, remaining]: `logs/` unbounded, 1-second stamps can collide (`auriga.sh:26-28`); `build.sh:87-91` dies with a literal glob message on an empty `patches/`.

## Dead code, leftovers, stale comments
- L1: `stream/lib/session.py:30-36` `mint_session_id`, `session_name`, `:20` `SESSION_TIME_FORMAT`, `:47-60` `plan_retention` — only `tests/test_session.py` calls them; production ids/pruning are `AurigaSession.cpp:87-103,235-280`.
- L2: `stream/lib/h264.py:176-180` `FrameAssembler.reset` — test-only; `video_loop` builds a new assembler (`server.py:342,356`).
- L3: `stream/lib/h264.py:206-217` `GopBuffer.add`'s bool is discarded (`server.py:405`); `clear()` is used (`:272`).
- L4: `stream/lib/clock.py:44-47` `ContentClock.reset` — only from `__init__`.
- L5: `stream/server.py:69-73,190-194` `stream_path` is called with a stream name but returns `video.h264` for `"video"` and `<name>.wav` otherwise; the two call sites (`:190-194`) are thin wrappers used only by the two loops.
- L6: `stream/server.py:49-50` `DEFAULT_FPS` here plus `DEFAULT_FPS` in `session.py:26` and `clock.py:10`; `DEFAULT_WS_PORT` here plus the argparse default 8081 (`auriga_stream.py:34`) plus `app.js:9`.
- L7: `stream/server.py:470` `getattr(ws, "remote_address", "?")` exists only for the test fake.
- L8: `app.js:121-122` `canvas.width || 1280` fallbacks are unreachable.
- L9: `openauto/src/autoapp/Service/ServiceFactory.cpp:143-149` `// TODO: What is WiFi Projection Service?` + the never-called `createWifiProjectionService` (`:274-277`); `:212-225` commented telephony sink.
- L10: `App.cpp:72-74,88-89,253-265` commented-out blocks; `VideoMediaSinkService.cpp:234-245` writes `/tmp/entityexit`.
- L11: `stream/README.md` still present with a Pi-era title while `AGENTS.md` now points at `docs/Stream protocol.md`.
- L12: `capture/`, `PHONE-APP.md`, `MAC-PORT.md`, `RUNBOOK.md`, `NEXT-SESSION.md`, `openauto-plan.md`, `posttrip/` and four root `btapp.*.galaxy*` credential DBs remain on disk though their FRs are dropped.

## Improvement areas
- I1: replay the GOP (or request a keyframe) when `send_hello` follows a codec change — B2 is one call away from fixed: `server.py:366-367`.
- I2: `aoa_read.py` should build the banner with an explicit branch (`… if ep_out else "none"` outside the f-string), and both tools need a smoke test — nothing imports them, so `py_compile` never catches a format-spec bug.
- I3: one capture predicate: `captureSession_ != nullptr` vs `captureModeEnabled()` (`ServiceFactory.cpp:178,240,258`) can only ever disagree through future edits.
- I4: `configuredVideoGeometry()` is still computed twice per entity (`ServiceFactory.cpp:131,173`); the second call can differ from the geometry already published in the manifest.
- I5: the video writer's drop response now discards ~60 s of video; bounding the delta skip by "until the IDR or 2 s" would trade decode-ability for latency. Alternatively report the gap as a manifest `dropped` counter.
- I6: `AurigaWriter` per-sink threads (4) and 64 MiB caps each; one writer with per-stream queues removes 3 threads without changing semantics.
- I7: rotation still throws away up to 4 GiB per stream (`AurigaVideoOutput.cpp:231-248`); segment files (`video-1.h264`) would keep the data and remove the size-vs-offset heuristic.
- I8: skip constructing the acceptor in capture mode instead of binding `0.0.0.0:0` (`App.cpp:39-40`), which is still the only listening socket outside loopback.
- I9: `session.py`'s Python mirrors (`mint_session_id`, `plan_retention`) diverge from `prune()` semantics (C++ maps `keep=0`→1 and skips `current`); delete them or make one side authoritative.
- I10: replace the 16 `print()` calls with `logging` (I2 of the stream audit) — queue drops, epoch stalls and the new `codec_stale` transitions are still only visible on stdout.
- I11: `VIDEO_READ_CAP`/`AUDIO_READ_CAP` bound per-poll reads but a stalled tail still reads 1 MiB per 8 ms poll; a `size - offset` backlog counter with a log line would make a stuck tail diagnosable.
- I12: `tools/` have zero coverage and are the only code that touches the dongle directly; a `--dry-run` that exercises argument parsing and the banner would have caught B1.

## Interfaces
- Exposes (unchanged except where noted): `AURIGA_CAPTURE_DIR` as the only capture switch (`AurigaSession.cpp:38-64`); `<capture-dir>/current -> session-<id>/` holding `video.h264`, `audio-{media,guidance,system}.wav`, `input.jsonl`, `manifest.json` `{session,width,height,fps,video,audio-media,audio-guidance,audio-system}` (`:182-211`), rotation signalled only by a segment count, 5 sessions retained; the FIFO line protocol `tap|down|move|up X Y` + `quit` (`AurigaInputDevice.cpp:187-229`); **new**: `AurigaWriter::take_drop_flag()` as the video resync signal (`AurigaWriter.hpp:144-150`); **new**: video segments may carry a second SPS/PPS pair mid-file after a late config or a drop resync.
- Stream side: `serve_http(web_dir, port, ws_port=8081)` now returns the `ThreadingHTTPServer` and answers `GET /config.json` → `{"wsPort": n}` (`server.py:541-576`); `Streamer` gained `usable_parameter_sets`, `apply_codec`, `_segment_codec`, `codec_stale` (`:60-66,196-216,188`); `open_when_ready(path, offset, at_end=False)` (`:311-328`); `Viewer` behaviour unchanged except `_make_room` guarding an empty queue (`:150-151`) and `run()` clearing `ready` before draining (`:156-166`). CLI unchanged except `--fifo` honouring `AURIGA_INPUT_FIFO` and `serve_http` receiving `--ws-port` (`auriga_stream.py:32,38`).
- Consumes: `<capture-dir>/current` + `manifest.json` (`session.py:167-214`), Annex-B `video.h264` with SPS/PPS at each segment head, `audio-media.wav` (44-byte header), the input FIFO, `websockets`; the page consumes `/config.json` before connecting (`app.js:42-53`).
- Threading: unchanged. HU: Qt main thread, 4 `io_service.run()` threads, one strand per service carrying receive/queue-copy/ACK, one writer thread per sink (4) that now also owns `writeChunk`, the drop flag, rotation and the WAV header rewrite; 1 stdin reader thread joined by a new `start()`; `noteRotation` on the writer thread under the session mutex. Stream: one asyncio loop for `session_loop`/`video_loop`/`audio_loop`/`handle`/`Viewer.run` (file reads still synchronous, now per-poll capped), `ThreadingHTTPServer` on a daemon thread.

## Open questions for the user
- Q1: does any AA entity reopen a media channel after shutdown (B3)? If not, `open()` should fail rather than return `true` once `stopping_` is set.
- Q2: close runtime B1 by restarting the pair on the 10:02 binary now, or leave the old stack running until the rearchitecture lands? Every HU/STR fix is unverified until then.
- Q3: should a codec-change `hello` also replay the GOP (B2), or is an encoder reconfigure considered out of scope (it never happens on the AA 1.7 Baseline stream you capture)?
- Q4: keep the two `tools/` at all (pyusb only in `.venv`, both break while `autoapp` owns the dongle), or fix `aoa_read.py` and add a smoke test?

## Result
Phase 8 fixed 9 of 14 prior high/medium findings and 15 of 25 low ones; the remaining high/medium are runtime-B1 (stale live pair, state), runtime-B4 (readiness), headunit-B3 (reopen after stop) and 2 new medium code bugs (`tools/aoa_read.py:66` f-string crash; codec-change `hello` without a keyframe). 100/100 tests pass, all 7 patches reproduce both nested trees byte for byte, 36/36 kept HU/STR/RUN/BLD FRs map to live code.
