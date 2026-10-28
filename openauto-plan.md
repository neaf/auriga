# Full OpenAuto stack — inspection and build plan (2026-10-28)

This is the next phase after the minimal `capture/` app plateaued at service
discovery / channel opens with the phone showing "Communication error 2".
The full stack is now built and working: the phone projects, and video, audio
and input are captured.

## Result (2026-10-28 12:52)

- Full OpenAuto (`4cc739b8`) + aasdk 1.7 completed AA 1.7, TLS, service
  discovery, video focus/start and media setup.
- Phone projection confirmed from captured frames: full AA UI with Google Maps
  and Spotify at 1280x720.
- Captured media audio: 48 kHz/16-bit stereo WAV, 30.9 s validated, mean
  volume -18.9 dB / peak -5.0 dB (Spotify routed to "Android Auto").
- Touch input injection confirmed: `aa-tap.sh` -> FIFO -> `input.jsonl` ->
  AA input report.
- The dongle's BT advertising returned after deleting `btapp.db`/`btapp.bk`
  and re-pairing the Galaxy. The dongle recreated a 33-byte DB; see
  `dongle-backup/README.md`.
- Model correction: the dongle terminates the phone-side Wi-Fi/WPP/BT link but
  relays AA messages between phone and head unit. The phone sees OpenAuto's
  `display_name` "Crankshaft-NG" and service set. It is not a full AA-layer
  terminator.
- Artifacts: `captures/2026-10-28-session2-video.h264`,
  `2026-10-28-session2-audio-media.wav`, extracted frames, input JSONL.
- Live testing: `ffplay` over SSH for video and live PCM audio;
  `scripts/aa-tap.sh` for touches.

Finalization (2026-10-28):

- Launch scripts: `scripts/pi-start.sh` / `pi-stop.sh` and
  `scripts/mac-start.sh` / `mac-stop.sh`.
- Mac client: `stream/auriga_stream.py` + `stream/web/` (Brave/Chrome,
  WebCodecs + WebAudio, taps back to `/tmp/auriga-in`).
- Runbook: `RUNBOOK.md`. Handoff: `NEXT-SESSION.md`.
- The working capture is the OpenAuto file-sink prototype; the next
  architecture is a headless aasdk emulator feeding the stream directly with
  AA timestamps and per-session files.

Remaining issues:

- First AA session reset on the dongle's AA Bluetooth pairing request
  (`AASDK Error 10`, USB transfer); OpenAuto reconnected automatically and the
  second session was stable. The Bluetooth service / DummyBluetoothDevice needs
  investigation.
- `AurigaVideoOutput`/`AurigaAudioOutput` open with truncation, so a new AA
  session overwrites the previous capture. Per-session filenames are needed.
- The file sinks ignore AA timestamps, so streamed audio/video are not
  sample-synced.
- The AA display name is OpenAuto's hardcoded "Crankshaft-NG"; rename to Auriga.

## Stack correction

There is **no `opencardev/openauto2` repository**. The current full stack is:

| Component | Repo / ref | Commit | Date |
| --- | --- | --- | --- |
| Head unit | `opencardev/openauto` `main` | `4cc739b8` | 2026-02-08 |
| AA library | `opencardev/aasdk` `newdev` | `9bf6adf9` | 2026-06-11 |

The Pi's `~/auriga/aasdk` tree is **byte-identical to `aasdk` `newdev`** except
`include/aasdk/Version.hpp`, which was bumped from 1.6 to 1.7. 447 files were
compared by SHA-256. Therefore:

- the existing `~/auriga/build-aasdk` is the correct library for OpenAuto;
- no aasdk re-clone or replacement is needed;
- OpenAuto must link this 1.7 build, not a fresh upstream 1.6 build.

## Read-only state check (Pi, 2026-10-28 ~11:00)

- `auriga-pi`, kernel `6.18.50+rpt-rpi-v7`, `throttled=0x0`, 763 MB available,
  53 GB free.
- Dongle at `1-1.4.4.2`, currently `2717:ff40` (MTP). It re-enumerates as MTP
  every ~22.0 s (device numbers 44 -> ... -> 76). It never enters AOA on its
  own. The period is very regular, and it persists after cleanup with no host
  process holding any `/dev/bus/usb` node (`fuser` empty, no `mtp-probe`, no
  `gvfsd`). This looks like a dongle idle-MTP watchdog or the phone's wireless
  retry, not a hub/power fault. The AOA switch during the OpenAuto run should
  stop it; verify with `dmesg`.
- **Stale process (fixed):** `auriga_capture` PID 3744, started 10:45 with
  `--duration 90`, was still alive with 2 threads, 0 CPU, and a deleted
  `/dev/bus/usb/001/124` fd after its log said `session finished`. It was
  killed at 11:04. The dongle re-enumeration continued afterwards, so the
  process was not the (only) cause.
- Build dependencies are now installed: Qt 5.15.15 (`qtbase5-dev`,
  `qtmultimedia5-dev`, `qtconnectivity5-dev`), Boost log/system, RtAudio,
  TagLib, blkid, libgps, GStreamer plugins, Xvfb. Disk is 4.5 GB used of 58 GB.
- `--duration` only bounds the session timer, not the pre-AOA retry loop or the
  exit path; this is a bug in the minimal app, not a Pi problem.
- Pi Wi-Fi (`wlan0`) is down. This is fine: the phone talks to the dongle's AP.
- Missing build packages: Qt5, Boost, RtAudio, TagLib, blkid, GPS, Xvfb.
  Present: OpenSSL, protobuf 3.21.12, libusb, cmake 3.31.6, g++ 14.2.
- Qt 5.15.15 is available in trixie; `libqoffscreen.so` is in
  `libqt5gui5t64`, so `QT_QPA_PLATFORM=offscreen` is viable without X.

## Why full OpenAuto is materially different from `capture/`

OpenAuto's `ServiceFactory` advertises:

- video sink (H.264 baseline),
- media / guidance audio sinks,
- system audio sink,
- microphone source,
- sensor source,
- input source,
- Bluetooth service (when wireless projection is enabled).

It deliberately **does not advertise**:

- the Wi-Fi Projection (WPP) service — the call is commented out in
  `ServiceFactory.cpp`;
- telephony audio — also commented out.

The minimal app advertised WPP with the dongle's own AP BSSID and password,
plus telephony audio and a Bluetooth service using the dongle's address. A
plausible (unproven) explanation of the phone's failure is that advertising WPP
to a phone already associated with the dongle's AP makes the phone/dongle
restart the Wi-Fi projection link, producing `PROTOCOL_IO_ERROR` /
`READER_CLOSE`. A wired-car head unit does not advertise WPP, and the dongle
presents itself as a wired phone over AOA. This is the main reason to test the
full stack before changing anything else.

Other differences that matter:

- OpenAuto's default video mode is 800x480; the dongle's `videoInfo` SPS/PPS is
  1280x720. The run config must request **1280x720**.
- OpenAuto's `QtVideoOutput::init()` returns `true` even when Qt Multimedia has
  no display, so offscreen mode will not by itself block projection. Decoding
  may fail, but the AA handshake can proceed.
- aasdk's `sendVersionRequest()` uses `AASDK_MINOR`; the Pi build reports 1.7.
- OpenAuto's Bluetooth default (adapter `NONE`) advertises `car_address=""` and
  pairing `UNAVAILABLE`. That is a variant to test; the baseline keeps it.

## Minimal app retest (2026-10-28 evening)

After the BT DB reset, the minimal `capture/` app completes AA 1.7, TLS,
service discovery, channel setup and video setup, and captures real H.264
(75–150 KB), then hits the dongle's USB reset (`AASDK Error 10`). Tested
changes that did **not** fix it:

- removed WPP service;
- removed telephony audio;
- Bluetooth `already_paired=true`, no auth data;
- removed the Bluetooth service entirely;
- restarted the app in a session loop.

It resets every session. OpenAuto, by contrast, auto-reconnects after the first
reset and its next session stays stable for minutes. Therefore OpenAuto is the
working stack; the minimal app is not the current target (it remains the basis
for a future headless emulator).

Stream fix: OpenAuto's H.264 stream may have its IDR only at session start, so
late browser clients received only delta frames and showed nothing. The stream
server now caches the current GOP and, when no recent IDR exists, starts at
offset 0; a new client gets the keyframe + deltas and catches up. Verified with
a raw WebSocket client: 1 keyframe + 199 deltas.

## Build status (2026-10-28 11:13)

- Dependencies installed; Qt 5.15.15 and the offscreen platform plugin present.
- `opencardev/openauto` cloned on the Pi and pinned to `4cc739b8`.
- CMake configure succeeded with `NOPI=ON`, using the existing aasdk/aap_protobuf
  build tree; the link line contains `libaasdk.so` and `libaap_protobuf.so` with
  rpath `/home/pi/auriga/build-aasdk/lib`.
- First build failed at 36%: `AndroidAutoEntity.hpp` includes the bare
  `<Transport/ITransport.hpp>`. OpenAuto expects `AASDK_INCLUDE_DIR` to be the
  `.../include/aasdk` directory (as a system install provides), while the rest
  of the code uses `<aasdk/...>`. Fixed without touching source by configuring
  `AASDK_INCLUDE_DIR=$HOME/auriga/aasdk/include/aasdk` and
  `CMAKE_CXX_FLAGS_INIT=-I$HOME/auriga/aasdk/include`; both include roots are
  now in `flags.make`. Clean reconfigure done; rebuild running, log
  `/tmp/build-openauto.log`.
- Build succeeded at 11:41 (`BUILD_RC=0`, 100%).
- Binary: `~/auriga/build-openauto/bin/autoapp-2026.10.28+git.4cc739b`, with a
  plain `autoapp` symlink. `ldd` resolves `libaasdk.so.2026` and
  `libaap_protobuf.so.2026` from `~/auriga/build-aasdk/lib`; RUNPATH is set.
- No stale `autoapp`/`auriga_capture` process; dongle is in MTP
  (`2717:ff40`); offscreen Qt plugin is present.
- Next: first baseline run (offscreen, 5 min), then phone radios on once the
  log shows OpenAuto waiting.
- Run configuration written to `~/auriga/openauto-run/openauto.ini` and
  `openauto-logs.ini` (1280x720/30, RtAudio, BT service enabled).
- No dongle or phone changes were made for the build.

## Baseline run (2026-10-28 11:45:25–11:50:25, 5 min)

Run from `~/auriga/openauto-run` with `QT_QPA_PLATFORM=offscreen`, config
1280x720/30. The dongle switched from `2717:ff40` to `18d1:2d00` and stayed in
AOA for the whole run.

Observed, in order:

- `[App] Waiting for device...`
- `[App] Device connected.`
- `[App] Devices enumeration result: true`
- `Version Received: 256.1792, with status: 0` (AA 1.7)
- SSL/TLS handshake completed
- service discovery request handled
- video channel 3: `STATUS_SUCCESS`, 1280x720/30, margins 0, DPI 140
- audio channels 4 (media), 5 (guidance), 6 (system): open requests received,
  but **all three `RtAudioOutput::open()` failed** with
  `pa_context_connect() failed: Connection refused` /
  `RtAudioOutput: No output devices found.` RtAudio selected the PulseAudio
  backend, and no PulseAudio daemon is running.
- media source channel 9: `STATUS_SUCCESS`
- input/sensor/Bluetooth services started
- no video setup request, no video focus, no media frames, no `Initial
  buffering complete`; the AA log is idle after the input channel open. The
  user confirmed the phone was not touched during the run: BT/Wi-Fi stayed off
  and AA stayed force-stopped. The dongle therefore ran the AA handshake with no
  phone behind it, which explains the missing video/focus/media activity. This
  run validates OpenAuto's USB/AOA/TLS/service-discovery path only; it is not
  yet a projection test.
- `SensorService` logs every polling tick at info: 2,212 of 2,332 lines are
  `sensorPolling()` / `is_file_exist()`. This needs to be quieted for usable
  logs.
- After the 5-minute timeout the dongle was still `18d1:2d00`; no `autoapp`
  process remained.

Artifacts: filtered log `logs/run-baseline-114525.filtered.log`; run config
copies in `openauto-config/`.

Next changes before another run:

1. File-based audio outputs (WAV) for media/guidance/system, so audio setup no
   longer depends on PulseAudio/ALSA and the PCM is captured.
2. File-based video output (H.264 Annex-B), which also removes the offscreen
   Qt Multimedia dependency.
3. File/FIFO input device (JSONL + injected touch), replacing the UI widget
   dependency.
4. Change the per-tick sensor logs to debug (or remove them).
5. Incremental rebuild (only a few objects), then rerun with the phone radios
   on only after OpenAuto is waiting in AOA.

## Capture patch (2026-10-28 12:20)

Applied to the pinned OpenAuto tree on the Pi and kept as
`patches/openauto-capture.patch`.

- New `AurigaVideoOutput`: writes raw H.264 Annex-B to
  `$AURIGA_CAPTURE_DIR/video.h264`; reports the configured resolution/FPS.
- New `AurigaAudioOutput`: writes PCM WAV per channel (`audio-media.wav`,
  `audio-guidance.wav`, `audio-system.wav`), with periodic header updates and
  finalization on stop.
- New `AurigaAudioInput`: paced 20 ms silent microphone source, no
  PulseAudio/ALSA dependency.
- New `AurigaInputDevice`: reads `tap/down/move/up` from stdin/FIFO, logs JSONL
  to `input.jsonl` and forwards touch events; advertises a broad keycode set so
  AA key binding succeeds.
- `ServiceFactory` selects the Auriga backends only when `AURIGA_CAPTURE_DIR`
  is set; the normal OpenAuto path is unchanged.
- `SensorService` per-tick logs changed from info to debug.

Build succeeded after adding the missing `IInputDeviceEventHandler.hpp`
include. A 30 s smoke test with the dongle still in the previous AOA session
connected and started services, but the dongle did not restart AA (no
version/TLS), so no capture files were produced. Sensor log noise dropped from
2,212 lines to 3. A cold dongle boot is required before the real phone run.

`openauto-config/run.sh` now sets `AURIGA_CAPTURE_DIR`, creates
`/tmp/auriga-in`, and runs `autoapp` with that FIFO as stdin. Inject with
`echo 'tap 640 360' > /tmp/auriga-in`.

## Phone re-pairing (2026-10-28 12:40)

The user chose to start clean and forgot `AutoLink-A512` on the phone for both
Bluetooth and Wi-Fi. Notes:

- The Pi's own Bluetooth was powered off (`hci0`, `Powered: no`) to remove any
  chance of the phone auto-connecting to the Pi instead of the dongle. OpenAuto
  runs with `BluetoothAdapterType=NONE`, so this does not affect AA.
- While the dongle was in AOA, a 10 s Pi scan did not see `AutoLink-A512`, and
  the phone could not connect BT. Pairing must be done while the dongle is in
  MTP, after a cold boot.
- New sequence: physical replug to MTP -> pair BT `AutoLink-A512` -> join Wi-Fi
  `AutoLink-A512` with password `12345678` -> start OpenAuto.
- If the dongle rejects a new pairing because `btapp.db` still holds the old
  Galaxy link keys, the fallback is to clear/replace `btapp.db`/`btapp.bk` on
  the dongle. That is a dongle write and requires explicit approval.

## Build plan (Pi, native armv7)

### Step 0 — cleanup (needs OK)

```bash
kill -9 3744
# verify the dongle stops re-enumerating for ~30 s
watch -n 2 'lsusb -d 2717:ff40; lsusb -d 18d1:2d00'
```

Optionally cold-boot the dongle with a physical replug after the kill.

### Step 1 — install dependencies (needs OK)

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential cmake pkg-config git \
  qtbase5-dev qtmultimedia5-dev qtconnectivity5-dev qttools5-dev qttools5-dev-tools \
  libboost-dev libboost-system-dev libboost-log-dev \
  libprotobuf-dev protobuf-compiler libusb-1.0-0-dev libssl-dev \
  librtaudio-dev libtag1-dev libblkid-dev libgps-dev \
  libqt5multimedia5-plugins \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav gstreamer1.0-alsa \
  xvfb xauth
```

`xvfb` is only a fallback if the offscreen Qt platform fails.

### Step 2 — build OpenAuto against the existing aasdk (needs OK)

Pin the inspected commit. Do **not** install aasdk system-wide; point CMake at
the existing build tree.

```bash
git clone https://github.com/opencardev/openauto.git ~/auriga/openauto
git -C ~/auriga/openauto checkout 4cc739b8

cmake -S ~/auriga/openauto -B ~/auriga/build-openauto \
  -DCMAKE_BUILD_TYPE=Release -DNOPI=ON \
  -DAASDK_INCLUDE_DIR="$HOME/auriga/aasdk/include" \
  -DAASDK_LIB_DIR="$HOME/auriga/build-aasdk/lib/libaasdk.so" \
  -DAAP_PROTOBUF_INCLUDE_DIR="$HOME/auriga/build-aasdk/protobuf" \
  -DAAP_PROTOBUF_LIB_DIR="$HOME/auriga/build-aasdk/lib/libaap_protobuf.so" \
  -DCMAKE_BUILD_RPATH="$HOME/auriga/build-aasdk/lib"

cmake --build ~/auriga/build-openauto --target autoapp -j2
```

`autoapp` only at first; `btservice` is not needed for projection and is a
separate target. Expected build time on the Pi 3: roughly 15-40 min.

Binary: `~/auriga/build-openauto/bin/autoapp`.

### Step 3 — run configuration

Create `~/auriga/openauto-run/openauto.ini`:

```ini
[General]
HandednessOfTrafficType=0
ShowClock=false
HideWarning=true

[Video]
FPS=2
Resolution=2
ScreenDPI=140
MarginWidth=0
MarginHeight=0

[Audio]
OutputBackendType=0

[AudioChannel]
MediaEnabled=true
GuidanceEnabled=true
SystemEnabled=true
TelephonyEnabled=false

[Bluetooth]
AdapterType=0
AdapterAddress=
WirelessProjectionEnabled=true

[Input]
EnableTouchscreen=true
EnablePlayerControl=false
```

`Video.Resolution=2` is `VIDEO_1280x720`, `Video.FPS=2` is 30 fps,
`Audio.OutputBackendType=0` is RtAudio, `Bluetooth.AdapterType=0` is `NONE`.

Create `openauto-logs.ini` (OpenAuto only installs a sink if this file exists):

```ini
[Core]
DisableLogging=false

[Sinks.Console]
Destination=Console
Filter="%Severity% >= info"
Asynchronous=false
AutoFlush=true
Format="%TimeStamp% [%Severity%] %Message%"

[Sinks.File]
Destination=TextFile
FileName=openauto.log
Filter="%Severity% >= info"
Asynchronous=false
AutoFlush=true
Format="%TimeStamp% [%Severity%] %Message%"
```

### Step 4 — baseline headless run

Phone prep (user): iPhone/OPPO BT and Wi-Fi off; Galaxy BT on, Wi-Fi on,
wireless AA enabled. Best sequence: start OpenAuto first, let it switch the
dongle to AOA and wait, then let the phone connect. If the phone is already
retrying, toggle its Wi-Fi/BT once after OpenAuto is up.

```bash
cd ~/auriga/openauto-run
sudo env QT_QPA_PLATFORM=offscreen \
  ~/auriga/build-openauto/bin/autoapp
```

Watch for, in order:

1. `Waiting for device...`
2. AOA switch / `Device connected`
3. `Version Received: 1.7`
4. service discovery + channel opens
5. `[QtVideoOutput] Initial buffering complete` (proves actual media arrives)
6. phone shows projection instead of "Communication error 2"

If Qt offscreen fails, fall back to `xvfb-run -a` (X11 platform).

### Step 5 — capture patches (after projection works)

Keep the patch in this repo (`patches/`), not only on the Pi:

- `AurigaVideoOutput` (`IVideoOutput`): write H.264 Annex-B to
  `captures/video.h264`; report 1280x720/30 and zero margins. Hook in
  `ServiceFactory` when `AURIGA_CAPTURE_DIR` is set.
- `AurigaAudioOutput` (`IAudioOutput`): write per-channel PCM/WAV to
  `captures/audio-<channel>.wav`.
- `AurigaInputDevice` (`IInputDevice`): log touch/button events to
  `captures/input.jsonl`; read `tap/down/move/up` from stdin or a FIFO.
- Optional silent `IAudioInput` if the Qt mic source fails without a capture
  device.

This also removes the need for Qt Multimedia decode and RtAudio during capture.

### Step 6 — fallbacks if WPP still fails

In order, only after the baseline log is captured:

1. Enable OpenAuto's WPP service (uncomment in `ServiceFactory`) with the
   dongle AP `AutoLink-A512` / `12345678` / BSSID `e8:5c:b1:b5:c6:41`; compare.
2. Try Bluetooth `WirelessProjectionEnabled=false` (no BT service) and
   `AdapterType=LOCAL` (Pi BT address) as variants.
3. Compare OpenAuto's exact service-discovery response and timing against the
   minimal app's captured session.
4. Only then consider OpenAutoCore or a real-car capture.

## Mac build note

`brew` has bottles for `qt@5` 5.15.19, `boost` 1.92, `protobuf` 36.2,
`taglib`, `rtaudio`, `util-linux`, `gpsd`, and `abseil` on this Mac. A native
Mac build is possible, but it produces an **arm64 macOS binary**, not a binary
for the Pi. It is useful only as:

- a fast compile check, or
- a live test if the dongle is physically moved to the Mac (the phone/dongle
  radios do not care which host is on USB).

There is no Docker/podman on the Mac, so there is no armv7 cross-build path.
The Pi build remains authoritative. Recommendation: build on the Pi; use the
Mac only if a fast pre-check is worth the extra dependency install and moving
the dongle.

## Open questions / risks

- Dongle re-enumeration every ~22.0 s as MTP, with no host process holding the
  device. Most likely an idle-MTP watchdog or the phone's wireless retry. A
  clean test needs OpenAuto running and the dongle in AOA before the phone
  connects; confirm the re-enumeration stops when AOA is established.
- Offscreen Qt + QVideoWidget may log GStreamer errors; `init()` still returns
  true, so judge by media arrival and the phone UI, not by on-screen video.
- RtAudio default output on the Pi is likely `bcm2835 Headphones` (card 0), not
  the Komplete Audio 6 (card 1). Audio may be inaudible but should still open.
- OpenAuto's Bluetooth default advertises "unavailable"; this is intentional
  for the baseline but is a variable if the phone refuses to proceed.
