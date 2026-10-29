# Audit: runtime-orchestration

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| README.md | 389 | yes |
| AGENTS.md | 162 | yes |
| RUNBOOK.md | 306 | yes |
| NEXT-SESSION.md | 89 | yes |
| scripts/aa-tap.sh | 12 | yes |
| scripts/mac-headunit-start.sh | 91 | yes |
| scripts/mac-headunit-stop.sh | 24 | yes |
| scripts/mac-start.sh | 27 | yes |
| scripts/mac-stop.sh | 11 | yes |
| scripts/pi-start.sh | 60 | yes |
| scripts/pi-stop.sh | 21 | yes |
| openauto-config/run-mac.sh | 36 | yes |
| openauto-config/run.sh | 32 | yes |

Cross-checked (read, not assigned): `stream/auriga_stream.py` (all 423 lines), `stream/web/app.js` (grep), `openauto/src/autoapp/Projection/Auriga{InputDevice,VideoOutput,AudioOutput}.cpp`, `openauto/src/autoapp/Service/ServiceFactory.cpp`, `openauto/src/autoapp/Service/MediaSink/{Audio,Video}MediaSinkService.cpp`, `openauto/src/autoapp/{App.cpp,autoapp.cpp}`, `openauto/src/autoapp/Configuration/Configuration.cpp`, `openauto/src/autoapp/Service/AndroidAutoEntity.cpp`, `patches/*.patch`, `.gitignore`, live state (`pgrep`, `ioreg`, `adb`, pid files, `logs/`, `captures*/`).

## Functional behavior
- F1: One start script brings up the whole macOS head unit: `autoapp` (offscreen, capture mode) + stream server + `caffeinate`, then opens Brave at `http://localhost:8080`. Evidence: scripts/mac-headunit-start.sh:68-91. Status: active (live now: pids 29079/29090/29093).
- F2: Capture mode is opt-in via the `AURIGA_CAPTURE_DIR` env var; without it OpenAuto uses its Qt/RtAudio path and no capture files exist. Evidence: scripts/mac-headunit-start.sh:11, openauto-config/run-mac.sh:19,33-36; openauto/src/autoapp/Service/ServiceFactory.cpp:61-67,83-88. Status: active.
- F3: The start script is idempotent per component via `pgrep -f` on the binary/script path; it skips an already-running component instead of failing. Evidence: scripts/mac-headunit-start.sh:31-34,48-51; scripts/pi-start.sh:16-19,33-36. Status: active.
- F4: Exactly one FIFO per host at `/tmp/auriga-in` is recreated (`rm`+`mkfifo`) by the run wrapper before `autoapp` starts, with a background `sleep 86400 > FIFO` writer so the stdin open does not block. Evidence: openauto-config/run-mac.sh:22-27; openauto-config/run.sh:17-22. Status: active.
- F5: Touch input path: browser → WS `{type,x,y}` → stream server writes `tap X Y\n` to the FIFO (fresh `O_WRONLY|O_NONBLOCK` open per event) → `autoapp` stdin reader → AA input channel + `input.jsonl`. Evidence: stream/auriga_stream.py:364-381; openauto/src/autoapp/Projection/AurigaInputDevice.cpp:122-198. Status: active (8 taps in logs/stream-mac-*.log, matching captures/2026-10-28-macos-session2-input.jsonl).
- F6: A new AA session truncates every capture file; the stream server detects `size < offset` and broadcasts `hello`+`reset`. Evidence: openauto/src/autoapp/Projection/AurigaVideoOutput.cpp:39, AurigaAudioOutput.cpp:70, AurigaInputDevice.cpp:50; stream/auriga_stream.py:218-238; observed twice in logs/stream-mac-20261029-074101.log. Status: active.
- F7: A late WS client gets `hello` plus the cached GOP (messages from the last keyframe on). Evidence: stream/auriga_stream.py:346-356,285-299. Status: active.
- F8: Stop is signal-based: pid-file kill plus `pkill -f` for `autoapp`/stream. No graceful shutdown, no `reset` for clients. Evidence: scripts/mac-headunit-stop.sh:6-22; scripts/pi-stop.sh:6-17. Status: active.
- F9: Pi mode is start-on-Pi + SSH tunnel-on-Mac (`-L 8080 -L 8081`), tunnel pid in `/tmp/auriga-tunnel.pid`. Evidence: scripts/pi-start.sh:1-60; scripts/mac-start.sh:8-20. Status: unclear (repo cannot prove the Pi side exists; see A1).
- F10: `scripts/aa-tap.sh` injects a touch by ssh-ing to `pi@auriga-pi.local` and echoing into the Pi FIFO. Evidence: scripts/aa-tap.sh:12. Status: active for Pi mode only (see D3).
- F11: The Pi side runs `autoapp` as root via `sudo env`, with `QT_QPA_PLATFORM=offscreen` and an explicit `LD_LIBRARY_PATH`. Evidence: openauto-config/run.sh:28-32. Status: unclear (Pi only).
- F12: The stream server binds only `127.0.0.1` for both HTTP and WS. Evidence: stream/auriga_stream.py:395,417. Status: active, matches AGENTS.md:119.

## External facts and quirks
- X1: Port numbers collide across the two operating modes and with macOS services: both modes use 8080/8081, and RUNBOOK.md:266 records that OpenAuto's AA-over-Wi-Fi listener on TCP 5000 is disabled in capture mode because macOS AirPlay Receiver owns 5000. Source: code (stream/auriga_stream.py:406-407, openauto/src/autoapp/App.cpp:30-32) + doc.
- X2: Binding 8080/8081 fails hard: `ThreadingHTTPServer(...)` at stream/auriga_stream.py:395 raises before the WS server exists, so the whole stream process dies under `nohup` and only the log records it. Source: code.
- X3: The venv interpreter is a Homebrew framework Python 3.14 (`/opt/homebrew/opt/python@3.14`), websockets 17.3; the script's fallback is bare `python3` (`/usr/bin/python3`), which has no `websockets` and is rejected by the import check. Source: code + shell (`ls .venv/bin`, `import websockets`).
- X4: `nohup`+`&` in a subshell detaches `autoapp` to PPID 1; pid files therefore survive the launching terminal, and so do orphans. Verified live: pid 29079 PPID 1, `/tmp/auriga-mac-autoapp.pid`=29079. Source: capture (ps).
- X5: The dongle is currently in AOA (`18d1:2d00` = idProduct 11520) while `autoapp` runs, and the phone stays MTP+ADB (`04e8:6860` = 26720, `svc usb getFunctions` = `mtp`). Confirms AGENTS.md:59-73. Source: capture (ioreg/adb).
- X6: `caffeinate` dedupe assumes the exact argv `-dimsu`; a pre-existing `/usr/bin/caffeinate -disu` (pid 1018) is not matched, so duplicates coexist. Source: code + capture (pgrep).
- X7: The runtime has no supervisor: no launchd/systemd unit anywhere; a component that dies is only replaced by a manual re-run. Source: code (grep of the tree).
- X8: `/tmp/auriga-tunnel.pid` is stale from 2026-10-28 (pid 76297). Source: capture.

## Doc and code inconsistencies
- D1: RUNBOOK.md:119-120 and scripts/pi-start.sh:7-8 use `~/auriga/openauto-run/run.sh`; the repo has `openauto-config/run.sh`, and README.md:363 / RUNBOOK.md:302 / NEXT-SESSION.md:86 name the directory `openauto-config`. One of the two names is wrong at run time.
- D2: AGENTS.md:43 lists `quit` as a FIFO command of the head unit; openauto/src/autoapp/Projection/AurigaInputDevice.cpp:190-193 only sets `running_=false`, which stops the reader thread. `app` keeps running and touch is dead for the rest of the session (no code path polls that flag for exit; openauto/src/autoapp/autoapp.cpp:161-162 only connect the Qt exit/reboot buttons).
- D3: README.md:369 says `scripts/aa-tap.sh` sends a tap "to the live capture from the Mac"; scripts/aa-tap.sh:12 always ssh-es to `pi@auriga-pi.local`, so it cannot drive the macOS-local head unit that README.md:101-110 makes the primary path.
- D4: AGENTS.md:29-30 "refuses to start a second copy if autoapp or the stream server is already running"; scripts/mac-headunit-start.sh:31-34,48-51 return early per component and the script continues, printing "Mac head unit up."
- D5: AGENTS.md:44 / AGENTS.md:102 present `logs/*.log` as the log surface; OpenAuto also writes `openauto-config/openauto.log` (`openauto-logs.ini`:13, relative path resolved against cwd set at openauto-config/run-mac.sh:7), currently 25 KB and gitignored (.gitignore:20). Two unbounded log sinks.
- D6: AGENTS.md:160-162, README.md:353 and NEXT-SESSION.md:50 say `patches/` is the source of truth for the build. `aasdk-upstream` carries two edits no patch covers: `AASDK_MINOR 6->7` in `include/aasdk/Version.hpp` and a Darwin absl include fix in `protobuf/CMakeLists.txt` (`git -C aasdk-upstream status`, `git -C aasdk-upstream diff`); `grep -rn "AASDK_MINOR\|Version.hpp" patches/` returns nothing. README.md:249-250 describes the Version bump as a manual edit, contradicting the "patches are truth" rule.
- D7: README.md:36 and RUNBOOK.md:289 list the display name rename as outstanding; openauto/src/autoapp/Service/AndroidAutoEntity.cpp:182,196 still hardcode `Crankshaft-NG` (also make `Crankshaft`, model `Crankshaft-NG Autoapp` at :197,202). Claim true, work not done.
- D8: README.md:51 says the stream "can be viewed live with `ffplay` over SSH"; the current consumer is the WebSocket+Browser path (AGENTS.md:104-127). Stale.
- D9: README.md:12 dates status "2026-10-28" while NEXT-SESSION.md:3 dates 2026-10-29; the README table omits the newer macOS verification (NEXT-SESSION.md:14-24). Stale footer.
- D10: scripts/mac-headunit-stop.sh:15 comments "run-mac.sh execs autoapp, so the pidfile may point at the shell wrapper"; measured, the pid file points at `autoapp` itself (pid 29079, PPID 1). Comment is wrong, behaviour is right.
- D11: README.md:65-67 (3057 frames / 122 s / 48 kHz stereo) verified true against `captures/2026-10-28-macos-session2-video.h264` (3057 frames, 1280x720 Baseline) and `...-audio-media.wav` (48 kHz, 2 ch, pcm_s16le, 68.608 s). RUNBOOK.md:292 ("grows large, hundreds of MB") confirmed: `captures-mac/` is 331 MB audio + 249 MB video after 38 min.
- D12: README.md:88-91 and RUNBOOK.md:285-288 say the file sinks ignore AA timestamps and captures truncate; confirmed in code (AurigaVideoOutput.cpp:55-56, AurigaAudioOutput.cpp:87-88 ignore the timestamp argument; trunc flags at :39/:70).

## Assumptions to revalidate
- A1: The Pi stack exists as documented (`~/auriga/openauto-run`, `~/auriga/build-openauto`, `~/auriga/aasdk`, `pi@auriga-pi.local` reachable). Nothing in the repo proves it; scripts/pi-start.sh:6-10, scripts/aa-tap.sh:12 and scripts/mac-start.sh:6-14 all fail if the paths or host differ. Breaks: entire Pi fallback plus `aa-tap.sh`.
- A2: `pgrep -f "[/]build-openauto/bin/autoapp"` (scripts/pi-start.sh:16) matches a process started as `../build-openauto/bin/autoapp` via `sudo env` (openauto-config/run.sh:28). True for cmdline substring matching, unverified under `sudo` on the Pi. If false, duplicate `autoapp` instances both grab the dongle.
- A3: The FIFO is created by the same user that later writes it. openauto-config/run.sh:19 creates it before `sudo`; if `pi-start.sh` itself is run under `sudo`, the FIFO is root-owned and browser taps fail with `EACCES` (logged as "stream: input fifo error", stream/auriga_stream.py:380-381). Baked into run.sh:17-22 / run-mac.sh:22-27.
- A4: `hello` geometry is a constant: width/height 1280x720 and `fps` 30 in stream/auriga_stream.py:27-28,168-180, while the real resolution comes from `openauto.ini` `Video.Resolution=2` (openauto-config/openauto.ini:8; enum maps 2 -> 1280x720, openauto/src/autoapp/Configuration/Configuration.cpp:127-128). Changing the ini silently lies to clients.
- A5: Nothing enforces "one autoapp/stream pair owns the dongle and capture dir" (AGENTS.md:124); enforcement is the `pgrep` heuristics. A second stream server started on other ports (stream/auriga_stream.py:406-407) would still write the same FIFO.
- A6: `openauto.ini` `WirelessProjectionEnabled=true` (openauto-config/openauto.ini:25) keeps the Bluetooth service registered (`createBluetoothService`, openauto/src/autoapp/Service/ServiceFactory.cpp:114-119, WPP itself commented out at :118). Docs blame the BT service for the first-session reset (README.md:84-87, RUNBOOK.md:281-284). If that diagnosis is right, the config flag is the smallest untested lever.
- A7: The built `autoapp` matches `patches/` plus the two unpatched aasdk edits. The openauto clone is dirty in exactly the 5 files the patches touch (App.cpp, SensorService.cpp, ServiceFactory.cpp, SettingsWindow.cpp, autoapp.cpp) plus the 8 untracked `Auriga*` files; line counts are in range, byte-equality not verified. Build stamp is `autoapp-2026.10.28+git.4cc739b.dirty`.

## Bugs
- B1 [medium] Cross-mode port collision is undetected and misreported. scripts/mac-headunit-start.sh:47-66 has no port check; stream/auriga_stream.py:395 dies on `EADDRINUSE` but the script still prints "stream server started". Scenario: Pi tunnel up on 8080/8081 (scripts/mac-start.sh:13-14) → `mac-headunit-start.sh` → stream process gone, browser silently shows the Pi stream. Reverse case: scripts/mac-start.sh:8 treats "port busy" as "tunnel already up" and never opens the tunnel.
- B2 [medium] FIFO `quit` permanently kills touch and never exits. openauto/src/autoapp/Projection/AurigaInputDevice.cpp:190-193 sets `running_=false`; readerLoop leaves at :124-141. Scenario: `echo quit > /tmp/auriga-in` → no shutdown, and every later `tap` is ignored until `autoapp` restarts.
- B3 [medium] Capture loss on any reconnect, with no rotation and no naming. openauto/src/autoapp/Projection/AurigaVideoOutput.cpp:39, AurigaAudioOutput.cpp:70, AurigaInputDevice.cpp:50 all open with `trunc`; a reconnect discards up to 580 MB of media. Docs state it (README.md:88) but the rig still runs unaudited long sessions.
- B4 [low] `AURIGA_INPUT_FIFO` override desynchronises input. openauto-config/run-mac.sh:22 honours it; scripts/mac-headunit-start.sh:61 hardcodes `--fifo /tmp/auriga-in` for the stream server. Scenario: `AURIGA_INPUT_FIFO=/tmp/x mac-headunit-start.sh` → taps land in a path `autoapp` does not read (stream/auriga_stream.py:374 `ENOENT`, logged only).
- B5 [low] `pi-start.sh` lies about the capture directory. scripts/pi-start.sh:10 sets `CAPTURE_DIR` from a hardcoded path, never exports it, and prints it at :57; openauto-config/run.sh:14 independently honours `AURIGA_CAPTURE_DIR`. Scenario: `AURIGA_CAPTURE_DIR=/mnt/cap pi-start.sh` → banner names `~/auriga/captures-openauto`, files land in `/mnt/cap`.
- B6 [low] Stale-PID kills can hit an unrelated process. scripts/mac-headunit-stop.sh:6-19 kills whatever pid is in the file, with no cmdline check; the `pkill` patterns at :21-22 already cover the real targets. Scenario: `autoapp` died, pid recycled by another app → `mac-headunit-stop.sh` kills it.
- B7 [low] The FIFO writer expires after 24 h and silently disables touch. openauto-config/run-mac.sh:26 / run.sh:21 run `sleep 86400`; when it ends, `autoapp`'s stdin hits EOF, AurigaInputDevice.cpp:138-141 breaks the reader loop. Scenario: head unit up >24 h → taps stop, no log line at the app level.
- B8 [low] `aa-tap.sh` cannot express `quit` and interpolates unquoted values into a remote single-quoted command. scripts/aa-tap.sh:9-12: `${2:?x coordinate required}` forces x/y, so `aa-tap.sh quit` aborts; `echo '$cmd $x $y'` breaks on a quote in `$cmd`. Also `set -eu` + no host override (`AURIGA_HOST` ignored, unlike scripts/mac-start.sh:6).
- B9 [low] One slow WS client stalls the video pipeline. stream/auriga_stream.py:285-299 awaits `broadcast` under `self.lock`, and `broadcast` (:156-166) awaits `ws.send` per client; `max_gop = 100000` (:125) means a client connecting mid-GOP can be sent ~55 min of frames inside that lock. Scenario: stale browser tab that stops reading → video loop blocked → all clients freeze.
- B10 [low] `mac-headunit-stop.sh` leaves the FIFO behind (no `rm -f /tmp/auriga-in`), unlike scripts/pi-stop.sh:19. Next `run-mac.sh` recreates it (:23-24), so the leftover is only cosmetic + a trap for `aa-tap.sh` writers between runs.
- B11 [low] `mac-headunit-start.sh` cannot see the FIFO writer for cleanup and stop relies on `/tmp/auriga-fifo-writer.pid`, written by a *different* script (openauto-config/run-mac.sh:27). If `autoapp` was started by hand, the writer leaks a `sleep 86400`.
- B12 [low] Audio truncation does not emit `reset`: stream/auriga_stream.py:316-324 resets `audio_offset` silently while video at :222 broadcasts. A client keeps its WebAudio clock from the dead stream and mixes pre/post-reset PCM in one timeline.

## Dead code, leftovers, stale comments
- L1: scripts/pi-start.sh:10, `CAPTURE_DIR` computed but used only in an echo; dead for behaviour (see B5).
- L2: scripts/mac-headunit-stop.sh:15, comment about the pidfile pointing at the shell wrapper; false (measured pid = autoapp).
- L3: scripts/mac-headunit-stop.sh:19, `/tmp/auriga-fifo-writer.pid` cleanup for a pid written by openauto-config/run-mac.sh:27 — asymmetric ownership between start/stop scripts.
- L4: README.md:51, `ffplay over SSH` live-view claim; superseded by the WebSocket client.
- L5: openauto-config/openauto.log, runtime log written into the config directory from a relative path in openauto-logs.ini:13; second log surface, gitignored at .gitignore:20, never mentioned in the docs' log table (AGENTS.md:44).
- L6: /tmp/auriga-tunnel.pid, stale since 2026-10-28 (pid 76297); scripts/mac-start.sh:9-12 kills it on next run.
- L7: aasdk-upstream unpatched edits (`include/aasdk/Version.hpp`, `protobuf/CMakeLists.txt`) — reproducibility leftovers, see D6.
- L8: scripts/__pycache__/ and stream/__pycache__/ present (gitignored via .gitignore:33).
- L9: `openauto/` clone is dirty by design (`git.4cc739b.dirty` in the binary name); the build artifact name encodes an uncommitted state, so "which build is running" needs a patch re-apply to answer.
- L10: scripts/pi-start.sh:33 uses pattern `[a]uriga_stream.py` while the Mac script uses `[a]uriga_stream.py --video`; two variants for the same process family.

## Improvement areas
- I1: No supervision or health signal. `nohup` + `pgrep` (scripts/mac-headunit-start.sh:39-66, scripts/pi-start.sh:24-47) means a dead `autoapp` or stream server is only noticed by the user. Mechanism: replace with a foreground supervisor or a pid+port check at start, and a `status` verb that verifies `Version Received` freshness.
- I2: Readiness is a `sleep 1` (scripts/mac-headunit-start.sh:69, scripts/pi-start.sh:50) instead of a wait for the capture file or the 8080 listen socket. Mechanism: poll `nc -z 127.0.0.1 8080` and the log line before starting the stream server.
- I3: `broadcast` is serialized with frame flushing (stream/auriga_stream.py:156-166,290-299); one stalled socket stalls capture-side streaming for everybody. Mechanism: per-client queue with drop-oldest for deltas.
- I4: Unbounded disk growth: `captures-mac/` at 580 MB after 38 min, no rotation, no per-session names (README.md:88-89, RUNBOOK.md:285). Mechanism: per-session filenames (`session-<ts>/`) plus a size cap; the streamer already handles offset resets.
- I5: Six start/stop scripts carry the same six blocks (pgrep, nohup redirect, pid file, echo banner) with divergent details (`--fifo` hardcoded vs env, CAPTURE_DIR hardcoded vs env, `python3` vs venv, `[a]uriga` pattern variants). Mechanism: one script with a `--mode mac|pi` flag and a shared `status/stop`.
- I6: Two log sinks, both unbounded (stdout redirect to `logs/openauto-mac-*.log` in scripts/mac-headunit-start.sh:41 plus the boost file sink writing `openauto-config/openauto.log`). Mechanism: single sink per run, absolute path, rotate.
- I7: Timestamps are fabricated in the streamer (`time.monotonic()` at stream/auriga_stream.py:153-154) while the sinks throw away the real AA timestamps (AurigaVideoOutput.cpp:55-56). Mechanism: write a timestamped sidecar or use the AA timestamp for the wire field; also fixes A/V drift on reset.
- I8: `openauto.ini:25 WirelessProjectionEnabled=true` still registers the Bluetooth service, the suspected cause of the first-session reset (README.md:84-87). Mechanism: flip the flag in a test run and compare `AASDK Error 10` frequency before any code change.

## Interfaces
- Exposes: `scripts/mac-headunit-start.sh`, `mac-headunit-stop.sh`, `mac-start.sh`, `mac-stop.sh`, `pi-start.sh`, `pi-stop.sh`, `aa-tap.sh`; FIFO `/tmp/auriga-in` line protocol `tap|down|move|up [X Y]` + `quit` (openauto/src/autoapp/Projection/AurigaInputDevice.cpp:156-198); env vars `AURIGA_DIR`, `AURIGA_CAPTURE_DIR`, `AURIGA_INPUT_FIFO`, `AURIGA_PYTHON`, `AURIGA_HOST` (scripts/mac-headunit-start.sh:7-13, scripts/mac-start.sh:6, openauto-config/run.sh:14-17); pid files `/tmp/auriga-{mac-autoapp,mac-stream,mac-caffeinate,fifo-writer,autoapp,stream,tunnel}.pid`; ports 8080 (HTTP, static `stream/web`) and 8081 (WS); capture dir layout `video.h264`, `audio-{media,guidance,system}.wav`, `input.jsonl`; log names `logs/openauto-mac-*.log`, `logs/stream-mac-*.log`, `openauto-config/openauto.log`.
- Consumes: `build-openauto-mac/bin/autoapp` (or `build-openauto/bin/autoapp` on the Pi) with `AURIGA_CAPTURE_DIR` set (openauto-config/run-mac.sh:10-19); `stream/auriga_stream.py` CLI `--video/--audio/--fifo/--http-port/--ws-port/--web` (stream/auriga_stream.py:402-409); `.venv` with `websockets` (scripts/mac-headunit-start.sh:13-26); `caffeinate`; `open -a "Brave Browser"`; for verification `pgrep`, `ioreg`, `adb`, `ffmpeg`.
- Threading: start/stop scripts are single-threaded POSIX `sh`, launch-and-exit. `autoapp` is detached (PPID 1) with a Qt main thread, 4 asio workers, a USB hotplug/pump thread, and 1 FIFO reader thread (`AurigaInputDevice.cpp:58`) that serializes commands and sleeps 80 ms inside `tap` (:172-173); capture writes happen on asio strands guarded by per-file mutexes (`AurigaVideoOutput.cpp:58`, `AurigaAudioOutput.cpp:89`). The stream server is one asyncio loop (`video_loop`, `audio_loop`, one task per WS client) plus one `ThreadingHTTPServer` thread (stream/auriga_stream.py:395-397). The FIFO is written concurrently by the WS handler (fresh fd per event), `aa-tap.sh` over ssh, and manual `echo`; the `sleep` writer holds it open permanently.

## Open questions for the user
- Q1: Is the Pi stack still alive, and is its run directory `~/auriga/openauto-run` or `~/auriga/openauto-config` (D1)?
- Q2: Should FIFO `quit` shut down `autoapp`, or be removed from the documented protocol (D2)?
- Q3: Are both host modes kept in the new architecture, or is macOS-local the only target?
- Q4: Do you want per-session capture directories and a size cap as a requirement (I4), or is overwrite-on-session acceptable?
- Q5: Should the aasdk `Version.hpp` bump and the protobuf absl fix be promoted into `patches/` (D6/A7)?
- Q6: Is a single-instance lock file wanted, given the `pgrep` heuristics are the only guard (A5)?
