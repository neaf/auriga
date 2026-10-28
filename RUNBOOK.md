# Auriga runbook

## What this is

A Raspberry Pi 3B acts as a wired Android Auto head unit for an AutoLink
wireless AA/CarPlay dongle. The phone connects to the dongle over BT + Wi-Fi;
the dongle presents an AOA USB device to the Pi; the Pi runs the full OpenAuto
head-unit stack and captures video, audio and input.

The dongle is a **relay at the AA layer**: it terminates the phone-side
Wi-Fi/WPP link but forwards AA service discovery/messages. The phone sees the
head unit's `display_name` and service set.

The Mac is a **remote UI**: Brave/Chrome displays live H.264 and PCM audio and
sends touches back through the Pi. The AA host stays on the Pi.

```
phone --BT/WiFi--> AutoLink dongle --USB AOA--> Pi OpenAuto capture
                                                   |
                                       video.h264 / audio-media.wav
                                                   |
                                        auriga_stream.py (WebSocket)
                                                   |
                                    SSH tunnel 8080/8081
                                                   |
                                      Brave (WebCodecs + WebAudio)
                                                   |
                                        tap JSON -> /tmp/auriga-in
```

## Prerequisites

- Pi: `auriga-pi.local` / `192.168.2.2`, Raspbian 13, `~/auriga` tree,
  `~/auriga/build-aasdk` (aasdk 1.7), `~/auriga/build-openauto` (OpenAuto
  `4cc739b8` + capture patch), `~/auriga/stream`.
- Mac: `ffmpeg`/`ffplay` optional, Brave or Chrome, SSH key access to the Pi.
- Dongle: AutoLink A512, MTP `2717:ff40`, AOA `18d1:2d00`; BT/Wi-Fi
  `AutoLink-A512`; Wi-Fi password `12345678`.
- Phone: Galaxy S25, AA 17.9; paired to the dongle; iPhone/OPPO off.

## Quick start

On the Pi:

```bash
~/auriga/scripts/pi-start.sh
```

This starts:
- `~/auriga/openauto-run/run.sh` (OpenAuto capture, offscreen, AURIGA_CAPTURE_DIR
  = `~/auriga/captures-openauto`), and
- `~/auriga/stream/auriga_stream.py` (HTTP 8080 / WebSocket 8081, bound to
  `127.0.0.1`).

On the Mac:

```bash
cd /Users/tomaszwerbicki/dev/auriga
./scripts/mac-start.sh
```

This opens an SSH tunnel for 8080/8081 and opens
`http://localhost:8080` in Brave. `localhost` is required for WebCodecs
(secure context).

In the page:
- video starts immediately;
- audio is **muted by default**; click the small 🔇 to enable;
- click/tap the canvas to send touches; drag sends down/move/up.

Stop:

```bash
# Mac
./scripts/mac-stop.sh
# Pi
~/auriga/scripts/pi-stop.sh
```

## Normal AA session sequence

1. Keep the dongle in MTP; phone BT + Wi-Fi off until the Pi is ready.
2. Start `pi-start.sh`; OpenAuto switches the dongle to AOA
   (`18d1:2d00`) and waits.
3. Start `mac-start.sh`; open the page.
4. Turn the phone's BT and Wi-Fi on. It connects to `AutoLink-A512`; the dongle
   performs the Wi-Fi credentials exchange itself.
5. The phone shows the AA UI; the Pi captures and the Mac displays it.

If the phone does not connect, see “BT recovery” below.

## BT recovery (dongle side)

The dongle's `btapp.db` can end up with duplicate/stale records and stop
advertising BT. The known-good reset is:

1. On the phone: forget `AutoLink-A512` for BT and Wi-Fi.
2. On the Pi, with the dongle in MTP:
   ```bash
   sudo mtp-delfile -f btapp.db
   sudo mtp-delfile -f btapp.bk
   ```
3. Physically replug the dongle (cold boot).
4. On the phone: pair `AutoLink-A512` (6-digit numeric comparison; 0000/1234
   fallback), then connect Wi-Fi `AutoLink-A512` / `12345678`.
5. The dongle recreates a **33-byte** `btapp.db` with the new link key. Back it
   up (`dongle-backup/btapp.db.galaxy-fresh` is the 2026-10-28 copy).
   `btapp.bk` may be absent.

Do **not** restore the old 207-byte `galaxy`/`galaxy2` DBs with the current
phone; their keys are stale. Restore notes and hashes are in
`dongle-backup/README.md`.

## Build (if rebuilding OpenAuto)

Dependencies (Pi):

```bash
sudo apt-get install -y build-essential cmake pkg-config git \
  qtbase5-dev qtmultimedia5-dev qtconnectivity5-dev \
  libboost-dev libboost-system-dev libboost-log-dev \
  libprotobuf-dev protobuf-compiler libusb-1.0-0-dev libssl-dev \
  librtaudio-dev libtag1-dev libblkid-dev libgps-dev \
  libqt5multimedia5-plugins gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly gstreamer1.0-libav \
  gstreamer1.0-alsa xvfb xauth python3-websockets
```

OpenAuto (pinned commit):

```bash
git clone https://github.com/opencardev/openauto.git ~/auriga/openauto
git -C ~/auriga/openauto checkout 4cc739b8

cmake -S ~/auriga/openauto -B ~/auriga/build-openauto \
  -DCMAKE_BUILD_TYPE=Release -DNOPI=ON \
  -DAASDK_INCLUDE_DIR="$HOME/auriga/aasdk/include/aasdk" \
  -DAASDK_LIB_DIR="$HOME/auriga/build-aasdk/lib/libaasdk.so" \
  -DAAP_PROTOBUF_INCLUDE_DIR="$HOME/auriga/build-aasdk/protobuf" \
  -DAAP_PROTOBUF_LIB_DIR="$HOME/auriga/build-aasdk/lib/libaap_protobuf.so" \
  -DCMAKE_CXX_FLAGS_INIT="-I$HOME/auriga/aasdk/include" \
  -DCMAKE_BUILD_RPATH="$HOME/auriga/build-aasdk/lib"

cmake --build ~/auriga/build-openauto --target autoapp -j2
```

The capture patch is `patches/openauto-capture.patch`; apply it to a clean
`~/auriga/openauto` before building:

```bash
git -C ~/auriga/openauto apply ~/auriga/patches/openauto-capture.patch
```

It adds file H.264/WAV sinks, a silent mic source, a FIFO/JSONL input device,
and the `AURIGA_CAPTURE_DIR` hooks. Without that env var, OpenAuto uses its
normal Qt/RtAudio path.

## Streaming server

`stream/auriga_stream.py` tails `~/auriga/captures-openauto/video.h264` and
`audio-media.wav`, parses Annex-B/AVCC, and serves:
- text `hello` with avcC description,
- binary `type:u8 | timestamp_us:u64 | payload` (1/3 video key/delta, 2 PCM),
- input JSON `tap/down/move/up` back to `/tmp/auriga-in`.

See `stream/README.md` for protocol details.

## Minimal app status

The minimal `capture/` app is **not** the working stack. After the BT DB reset it
completes AA/TLS/service discovery and captures some video, but resets on every
session. Removing WPP, telephony, BT auth, the whole BT service, and adding a
session loop did not fix it. OpenAuto auto-reconnects after the first reset and
is the stack to use. The minimal app remains the basis for a future headless
emulator.

## Mac port

The plan to move the proven stack to macOS (dongle direct to Mac, no Pi/hub) is
in [`MAC-PORT.md`](MAC-PORT.md). The main blocker is Boost 1.92 removing
`boost::asio::io_service`; use `boost@1.85`. macOS builds aasdk as static
libraries.

## Known issues / next steps

- First AA session can reset on the dongle's AA Bluetooth pairing request
  (`AASDK Error 10`, USB transfer). OpenAuto reconnects automatically; the
  second session is stable. Investigate the Bluetooth service /
  `DummyBluetoothDevice`.
- Capture files truncate on a new AA session; per-session filenames are needed.
- File sinks ignore AA timestamps; streamed audio/video are not sample-synced.
  The long-term fix is a headless emulator feeding the stream directly from
  aasdk callbacks with timestamps.
- AA display name is OpenAuto's hardcoded `Crankshaft-NG`; rename to Auriga.
- Forwarding to a real head unit needs a Pi 4/5 (host + OTG) or a two-device
  relay.
- The current capture file grows large (hundreds of MB); rotate/limit before
  long runs.

## Key files

- `README.md` — project state and findings.
- `RUNBOOK.md` — this file.
- `openauto-plan.md` — build/run/patch history and results.
- `stream/` — Pi server + Brave client.
- `patches/openauto-capture.patch` — capture patch.
- `openauto-config/` — `openauto.ini`, `openauto-logs.ini`, `run.sh`.
- `dongle-backup/` — dongle config backups and restore rules.
- `scripts/pi-start.sh`, `pi-stop.sh`, `mac-start.sh`, `mac-stop.sh`,
  `aa-tap.sh`.
- `captures/` — local media artifacts (large files not in git).
