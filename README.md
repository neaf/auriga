# Auriga

A working Android Auto head unit and capture rig for macOS: an AutoLink A512
dongle, patched OpenAuto, and a local H.264/PCM stream shown in Brave.

The phone projects through the dongle; `autoapp` captures video, audio, and
touch input into per-session directories; `auriga_stream.py` serves the live
session to the browser and forwards taps back to the phone.

## Quick start

Prerequisites: dongle in MTP (`2717:ff40`), phone Bluetooth + Wi-Fi on and
associated with `AutoLink-A512`, Brave installed. Python dependencies live in
`.venv` (`websockets`).

```bash
./scripts/auriga.sh start
./scripts/auriga.sh status
./scripts/auriga.sh stop
```

`start` brings up `autoapp` (offscreen capture), the stream server, and
`caffeinate`, waits for `127.0.0.1:8080`, then opens Brave. A second `start`
refuses to duplicate a running pair.

Open `http://localhost:8080`, then click the small 🔇 button to enable audio.
Tap or drag the canvas to drive the phone; drag sends `down`/`move`/`up`.

On the first connect after a cold boot, accept the phone's `Enable after unlock`
prompt. If it times out, the dongle resets and `autoapp` reconnects; enable
`Start Android Auto while locked` on the phone to avoid the prompt.

## What works

- Dongle MTP `2717:ff40` → AOA `18d1:2d00`; the phone stays MTP+ADB
  (`04e8:6860`) for `adb`.
- AA 1.7 / TLS / service discovery through patched OpenAuto `4cc739b8` and
  aasdk `9bf6adf`.
- 1280x720 H.264 Baseline video, 48 kHz/16-bit stereo media audio, touch input.
- Browser mirror with WebCodecs/WebAudio; one viewer at a time.
- Per-session captures under `captures-mac/current/session-<id>/` with
  `video.h264`, `audio-*.wav`, `input.jsonl`, and `manifest.json`; the five
  newest sessions are kept.

## Verify it is working

```bash
./scripts/auriga.sh status
ioreg -p IOUSB -l -w 0 | grep -E 'o (AutoLink|SAMSUNG_Android)@|"idProduct" = (26720|11520|11521|65344)'
adb devices -l
adb -s RFGL329J04J shell svc usb getFunctions   # expect: mtp
tail -20 "$(ls -t logs/openauto-mac-*.log | head -1)"   # Version Received + pings
ffmpeg -loglevel info -i captures-mac/current/video.h264 -f null - 2>&1 | tail -1
```

`current` exists only after the first AA session; `status` prints
`session: none yet` until then. The dongle LED is not an AA-link indicator: a
dark LED plus `18d1:2d00` and `Version Received` in the log means it is working.

## Build and test

From-patches build (clones upstreams, applies all seven patches, builds aasdk
then `autoapp`):

```bash
./scripts/build.sh          # artifacts in .build-from-patches/
./scripts/build.sh -t       # scratch build, removed on exit
```

Incremental builds, after the nested clones are configured:

```bash
cmake --build build-aasdk-mac --target aasdk -j8
cmake --build build-openauto-mac --target autoapp -j8
```

Tests and static checks:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m py_compile $(find stream scripts tools -name '*.py')
node --check stream/web/app.js
for f in scripts/*.sh openauto-config/*.sh; do bash -n "$f"; done
```

`patches/` is the source of truth for the nested `openauto/` and
`aasdk-upstream/` clones; see `docs/Build.md` for patch order, regeneration,
and the macOS toolchain.

## Docs

- [`docs/Android Auto head unit.md`](docs/Android%20Auto%20head%20unit.md) — AA
  protocol, patches, capture contract, runtime, recovery.
- [`docs/Stream protocol.md`](docs/Stream%20protocol.md) — WebSocket framing,
  sessions/manifest, browser behavior.
- [`docs/AutoLink A512 dongle.md`](docs/AutoLink%20A512%20dongle.md) — USB IDs,
  `videoInfo`/`btapp.db`, Bluetooth/Wi-Fi, recovery.
- [`docs/Build.md`](docs/Build.md) — toolchain, build order, editing workflow.
- [`docs/requirements.md`](docs/requirements.md) — kept/dropped requirements.
- [`docs/architecture.md`](docs/architecture.md) — modules, data flow,
  threading, interfaces.

`AGENTS.md` is the short operator guide for agents running the rig.

## Hardware

| Item | Detail |
| --- | --- |
| Dongle | AutoLink A512; MTP `2717:ff40`, AOA `18d1:2d00`; BT/Wi-Fi `AutoLink-A512` |
| Phone | Samsung Galaxy S25 (`SM-S931B`), AA 17.9, ADB `RFGL329J04J` |
| Host | macOS (Apple Silicon) |
| Stream | HTTP `127.0.0.1:8080`, WebSocket `127.0.0.1:8081` |

## Safety

- Do not flash firmware, factory reset, or restore dongle config/DB files
  without explicit approval; see `docs/AutoLink A512 dongle.md`.
- Do not expose `8080`/`8081` beyond localhost; the stream server has no auth.
- One `autoapp`/stream pair owns the dongle and capture directory.
- If the dongle stays in AOA with a stale TLS session, a physical unplug/replug
  (cold boot to MTP) is the reliable recovery; ask before interrupting a live
  session.
