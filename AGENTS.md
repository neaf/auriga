# AGENTS.md — Auriga

Auriga is a working Android Auto head-unit and capture rig built around an
AutoLink A512 wireless dongle, OpenAuto, and aasdk 1.7. A Galaxy S25 projects
1280x720 H.264 + 48 kHz stereo PCM, captured to files and streamed to Brave
with WebCodecs/WebAudio. Do not treat this as a greenfield AA implementation:
the proven stack is OpenAuto on the Mac or Pi, with the dongle as the AA relay.

## Current proven state (2026-10-29)

- macOS head unit works: `build-openauto-mac/bin/autoapp` + local stream server,
  dongle direct to the Mac, no Pi or tunnel.
- The phone can stay on the Mac's USB for `adb`/app development. `autoapp` only
  AOA-switches the dongle (`2717:ff40`), so the Galaxy S25 stays in MTP+ADB
  (`04e8:6860`); AA still projects over the dongle's BT/Wi-Fi link.
- Capture mode skips `ConnectedAccessoriesEnumerator`, which used to run the
  AOA query chain against every USB device.
- `SensorService` guards `gps_read()` when GPSD is absent; without that guard
  `autoapp` segfaults intermittently in `gps_shm_read`.
- The dongle LED is a boot/advertising indicator, not an AA-link indicator. It
  is lit/blinking in MTP and goes dark once the dongle is in AOA
  (`18d1:2d00`) and projection is active.

## Read these first

- `MAC-PORT.md` — exact macOS build, patches, configure flags, status.
- `RUNBOOK.md` — operations, BT recovery, phone-on-USB, stream, Mac local mode.
- `NEXT-SESSION.md` — current handoff and known next steps.
- `PHONE-APP.md` — separate design branch (phone-side AA app + Pi car server;
  not implemented).
- `stream/README.md` — WebSocket/HTTP protocol and client behavior.

## Layout

```
scripts/            mac-headunit-start/stop, pi-start/stop, mac-start/stop, aa-tap
stream/             auriga_stream.py + web/ Brave client
patches/            source-of-truth diffs for OpenAuto and aasdk
openauto/           separate git clone, pinned 4cc739b8; patched working tree
aasdk-upstream/     separate git clone, newdev; AASDK_MINOR=7 + USB filter
build-aasdk-mac/    static libaasdk.a / libaap_protobuf.a
build-openauto-mac/ offscreen autoapp binary
captures-mac/       live capture files (gitignored)
logs/               runtime logs (gitignored)
openauto-config/    autoapp config + run.sh (Pi) / run-mac.sh (Mac)
dongle-backup/      MTP config backups; DBs contain link keys (gitignored)
```

`openauto/` and `aasdk-upstream/` are ignored by the root repo and are separate
git clones. **The patches in `patches/` are the source of truth** for changes
to them, not the nested working trees.

## Start / stop (macOS)

```bash
./scripts/mac-headunit-start.sh   # autoapp + stream + caffeinate + Brave
./scripts/mac-headunit-stop.sh
```

Open `http://localhost:8080` in Brave. Audio is muted until the small 🔇 button
is clicked. Taps/drags on the canvas go through `/tmp/auriga-in` into
`captures-mac/input.jsonl`.

## Verify a live session

```bash
pgrep -fl "autoapp|auriga_stream"
ioreg -p IOUSB -l -w 0 | grep -E 'o (AutoLink|SAMSUNG_Android)@|"idProduct" = (26720|11520|11521|65344)'
adb devices -l
adb -s RFGL329J04J shell svc usb getFunctions   # expect: mtp
tail -20 "$(ls -t logs/openauto-mac-*.log | head -1)"   # Version Received + pings
ffmpeg -loglevel info -i captures-mac/video.h264 -f null - 2>&1 | tail -1
```

Expected USB IDs:

| Device | Mode | VID:PID |
| --- | --- | --- |
| AutoLink dongle | MTP before AOA switch | `2717:ff40` |
| AutoLink dongle | AOA / projecting | `18d1:2d00` |
| Galaxy S25 | MTP + ADB (correct) | `04e8:6860` |
| Galaxy S25 | AOA + ADB (bad; don't grab it) | `18d1:2d01` |

To inspect the current frame without Brave:

```bash
mkdir -p /tmp/auriga-frames
ffmpeg -loglevel error -i captures-mac/video.h264 \
  -vf "select='eq(n,300)'" -fps_mode passthrough -frames:v 1 \
  -update 1 -q:v 2 /tmp/auriga-frames/frame.jpg
```

If an emulator is attached, always use `adb -s RFGL329J04J`; bare `adb` fails
with "more than one device/emulator".

## USB invariants (critical)

- `autoapp` must only AOA-switch the AutoLink dongle. Never reintroduce
  `LIBUSB_HOTPLUG_MATCH_ANY` or an all-device AOA query chain: it switches
  development phones into accessory mode, launches Android Auto's USB
  preflight error on the phone, and can disturb the wireless session.
- In capture mode (`AURIGA_CAPTURE_DIR` set), do not run
  `ConnectedAccessoriesEnumerator`; it queries every USB device.
- Do not accept `18d1:2d01` as the dongle when a source filter is configured;
  that is an AOA+ADB phone (the AutoLink is `18d1:2d00`).
- If the phone is already `18d1:2d01` from an older run, reset it before
  starting: `adb -s RFGL329J04J shell svc usb setFunctions mtp` (or replug the
  phone). Do not switch the phone back by hand otherwise.
- Dongle recovery: if the dongle is stuck in AOA with a stale TLS session,
  `autoapp` waits at `Waiting for device...`. A `libusb` reset does not restore
  MTP; the dongle needs a physical unplug/replug (cold boot to MTP). Ask the
  user before replugging; it interrupts the live session.

## Build after code changes

```bash
cmake --build build-aasdk-mac --target aasdk -j8
cmake --build build-openauto-mac --target autoapp -j8
```

Patch order for a clean rebuild:

```bash
# aasdk-upstream (plus the Version.hpp / protobuf CMake edits in MAC-PORT.md)
git -C aasdk-upstream apply patches/aasdk-usb-filter.patch

# openauto at 4cc739b8
git -C openauto apply patches/openauto-capture.patch
git -C openauto apply patches/openauto-macos.patch
git -C openauto apply patches/openauto-auriga-usb-filter.patch
git -C openauto apply patches/openauto-auriga-gps-guard.patch
```

If you edit a nested tree, regenerate its patch and update the docs:

```bash
git -C openauto diff -- <paths> > patches/<name>.patch
```

Do not commit build outputs, `captures-mac/`, `logs/`, `.venv/`, `.serena/`,
or dongle credential databases.

## Integration points for a live project

- HTTP UI: `http://127.0.0.1:8080` (serves `stream/web/`).
- WebSocket: `ws://127.0.0.1:8081`.
- Server → client text `hello`:
  `{type:"hello", width, height, fps, codec, description}`, where
  `description` is base64 avcC (SPS/PPS) and `codec` is e.g. `avc1.42801f`.
- Server → client binary: `type:u8 | timestamp_us:u64 BE | payload`.
  - `1` = H.264 keyframe (AVCC), `3` = H.264 delta (AVCC),
  - `2` = PCM s16le, 48 kHz, stereo, 20 ms chunks.
- Server text `reset` on a new AA session / capture truncation.
- Client → server text: `{type:"tap"|"down"|"move"|"up", x, y}` in 1280x720
  space; the server writes `tap X Y` etc. to `/tmp/auriga-in`.
- Capture files: `captures-mac/video.h264`, `audio-media.wav`,
  `audio-guidance.wav`, `audio-system.wav`, `input.jsonl`.
- The server binds localhost only and has no auth. WebCodecs needs a secure
  context; use `localhost` or front it with HTTPS. Do not expose 8080/8081
  publicly.

For a live app integration, prefer consuming the WebSocket (or the capture
files during development) over adding another AA stack. The file sinks do not
preserve AA timestamps and truncate on a new session; per-session filenames
and timestamp-preserving sinks are known next steps.

## Known issues / next steps

- The first AA entity can reset on the dongle's BT pairing request
  (`AASDK Error 10`); OpenAuto reconnects, and the second session is stable.
- Capture files truncate on a new AA session; per-session filenames are needed.
- File sinks ignore AA timestamps; streamed A/V is not sample-synced.
- AA display name is OpenAuto's hardcoded `Crankshaft-NG`.
- Long runs grow the H.264 capture; rotate/limit files.
- `PHONE-APP.md` is a design branch, not part of the working capture stack.
