# AGENTS.md — using Auriga

Auriga is a working Android Auto head unit and capture rig: an AutoLink A512
dongle, OpenAuto, and a local H.264/PCM stream shown in Brave. Use this
directory to run the head unit, mirror the phone's AA screen, capture
video/audio/input, and feed a live project from the stream.

You do **not** need to build or modify OpenAuto/aasdk to use it. For changing
the head-unit package itself, see [`DEVELOPING.md`](DEVELOPING.md).

## Quick start (macOS, dongle direct)

Prerequisites: dongle in MTP (`2717:ff40`), phone BT + Wi-Fi on and associated
with `AutoLink-A512`, Brave installed.

```bash
./scripts/auriga.sh start
./scripts/auriga.sh status
./scripts/auriga.sh stop
```

`start` brings up `autoapp` (offscreen capture), the local stream server,
`caffeinate`, waits for `127.0.0.1:8080`, then opens Brave. `status` reports the
pids, both ports and the current session. One pair per capture directory: a lock
file in the capture dir makes a second `start` refuse instead of starting a
duplicate.

Then open `http://localhost:8080` in Brave. The page auto-connects to
`ws://127.0.0.1:8081`; audio starts muted, click the small 🔇 button to enable
it.

The Galaxy S25 can stay on the Mac's USB for `adb` while AA runs. The script
only AOA-switches the dongle; the phone should remain in MTP+ADB
(`04e8:6860`). See USB invariants below.

## What the package provides

| Surface | Address / path | Use |
| --- | --- | --- |
| Browser UI | `http://127.0.0.1:8080` | Live AA mirror + touch input |
| WebSocket | `ws://127.0.0.1:8081` | H.264/PCM stream + input |
| Captures | `captures-mac/current/` | one `session-<id>/` per AA session with `video.h264`, `audio-*.wav`, `input.jsonl`, `manifest.json` |
| Input FIFO | `/tmp/auriga-in` (`$AURIGA_INPUT_FIFO`) | `tap X Y`, `down X Y`, `move X Y`, `up X Y`, `quit` |
| Logs | `logs/openauto-mac-*.log`, `logs/stream-mac-*.log` | Runtime diagnostics |

## Verify it is working

```bash
./scripts/auriga.sh status
ioreg -p IOUSB -l -w 0 | grep -E 'o (AutoLink|SAMSUNG_Android)@|"idProduct" = (26720|11520|11521|65344)'
adb devices -l
adb -s RFGL329J04J shell svc usb getFunctions   # expect: mtp
tail -20 "$(ls -t logs/openauto-mac-*.log | head -1)"   # Version Received + pings
ffmpeg -loglevel info -i captures-mac/current/video.h264 -f null - 2>&1 | tail -1
```

Expected USB IDs:

| Device | Mode | VID:PID |
| --- | --- | --- |
| AutoLink dongle | MTP before AOA switch | `2717:ff40` |
| AutoLink dongle | AOA / projecting | `18d1:2d00` |
| Galaxy S25 | MTP + ADB (correct) | `04e8:6860` |
| Galaxy S25 | AOA + ADB (bad; don't grab it) | `18d1:2d01` |

The dongle LED is **not** an AA-link indicator. It is lit/blinking while the
dongle is in MTP/advertising and goes dark once the dongle is in AOA and
projection is active. A dark LED plus `18d1:2d00` in `ioreg` and a live
`Version Received` log means it is working.

To inspect the current frame without Brave:

```bash
mkdir -p /tmp/auriga-frames
ffmpeg -loglevel error -i captures-mac/current/video.h264 \
  -vf "select='eq(n,300)'" -fps_mode passthrough -frames:v 1 \
  -update 1 -q:v 2 /tmp/auriga-frames/frame.jpg
```

If an emulator is attached, always target the phone explicitly:
`adb -s RFGL329J04J ...`. Bare `adb` fails with
"more than one device/emulator".

## Interacting with the live head unit

- **Touch:** tap/drag the Brave canvas, or write to the FIFO:
  `echo 'tap 640 360' > /tmp/auriga-in` (or `$AURIGA_INPUT_FIFO`). Coordinates
  are in 1280x720 space.
- **Audio:** muted until the 🔇 button is clicked; it is 48 kHz/16-bit stereo.
- **New clients:** the stream server replays its cached GOP (the most recent
  H.264 IDR plus the following deltas, bounded), so a late client can start
  decoding immediately. One viewer at a time: a second tab takes over and the
  first stops reconnecting.
- **Sessions:** each AA session gets its own `session-<id>/` directory and the
  `current` symlink repoints to it; the server sends a `reset` on the change.
  The five newest sessions are kept.
- **Logs:** the newest `logs/openauto-mac-*.log` is the current `autoapp` log.

## Integration contract

The stream is designed to be consumed by another local process:

- HTTP `http://127.0.0.1:8080` serves the Brave client from `stream/web/`.
- WebSocket `ws://127.0.0.1:8081`:
  - text `hello`: `{type:"hello", width, height, fps, codec, description}`,
    geometry from the session's `manifest.json` (1280x720/30 by default), where
    `description` is base64 avcC (SPS/PPS) and `codec` is e.g. `avc1.42801f`.
  - binary: `type:u8 | timestamp_us:u64 BE | payload`.
    - `1` = H.264 keyframe (AVCC), `3` = H.264 delta (AVCC),
    - `2` = PCM s16le, 48 kHz, stereo, 40 ms chunks.
  - text `reset` when `current` moves to a new session; text `status` for a
    server-side condition (today: a failed input-FIFO write).
  - client → server text: `{type:"tap"|"down"|"move"|"up", x, y}` in 1280x720
    space; the server writes `tap X Y` etc. to `/tmp/auriga-in`. Or
    `{type:"keyframe"}` to replay the cached GOP.
  - one viewer: a second connection replaces the first (close code `4001`).
- The server binds **localhost only** and has no authentication. WebCodecs
  requires a secure context; use `localhost` or front it with HTTPS. Do not
  expose 8080/8081 publicly.
- Prefer consuming this stream over adding another AA stack. If you need
  offline work, the capture files are the same H.264/WAV data.
- Only one `autoapp`/stream pair should own the dongle and capture directory.

See [`docs/Stream protocol.md`](docs/Stream%20protocol.md) for the full protocol
and client behavior.

## USB / phone invariants

- `autoapp` must only AOA-switch the AutoLink dongle (`2717:ff40`). Never
  reintroduce an all-device AOA probe: it switches development phones into
  accessory mode and triggers Android Auto's USB preflight error on the phone.
- Do not accept `18d1:2d01` as the dongle; that is an AOA+ADB phone. The
  AutoLink dongle is `18d1:2d00`.
- If the phone is already `18d1:2d01` from an older run, reset it before
  starting: `adb -s RFGL329J04J shell svc usb setFunctions mtp` (or replug the
  phone).
- **Dongle recovery:** if the dongle is stuck in AOA with a stale TLS session,
  `autoapp` waits at `Waiting for device...`. A `libusb` reset does not restore
  MTP; the dongle needs a physical unplug/replug (cold boot to MTP). Ask the
  user before replugging; it interrupts the live session.

## Safety

- Do not run `mtp-delfile` or restore dongle config/DB files without explicit
  permission. The `dongle-backup/` README has the rules; the 207-byte DBs are
  stale and must not be restored with the current phone.
- Do not expose the stream server beyond localhost.
- Do not commit `captures-mac/`, `logs/`, `.venv/`, `.serena/`, or any dongle
  credential DB.
- If `autoapp` exits unexpectedly, check
  `~/Library/Logs/DiagnosticReports/autoapp*.ips`; a `gps_shm_read` stack
  points at the GPSD guard.

## Package development

Building, patching, and changing the USB filter/GPS guard: see
[`DEVELOPING.md`](DEVELOPING.md). The short version: `openauto/` and
`aasdk-upstream/` are separate git clones and `patches/` is the source of
truth; don't edit build outputs.

## Docs

[`docs/Android Auto head unit.md`](docs/Android%20Auto%20head%20unit.md),
[`docs/Stream protocol.md`](docs/Stream%20protocol.md),
[`docs/AutoLink A512 dongle.md`](docs/AutoLink%20A512%20dongle.md),
[`docs/Build.md`](docs/Build.md).
