# Auriga next-session handoff

## Current state (2026-10-28, macOS port)

**Working:**

- Pi: full OpenAuto (`4cc739b8`) + aasdk 1.7 projects the Galaxy S25 through
  the AutoLink dongle; captures 1280x720 H.264, 48 kHz stereo WAV, JSONL input.
- Pi stream server + Brave client works; late clients get the cached GOP.
- Pi start/stop: `scripts/pi-start.sh`, `pi-stop.sh`; remote UI:
  `scripts/mac-start.sh`, `mac-stop.sh`.
- **macOS build works**: aasdk 1.7 static + OpenAuto `4cc739b8` + capture patch
  + `patches/openauto-macos.patch` produce `build-openauto-mac/bin/autoapp`.
- **macOS projection works**: dongle direct to the Mac, MTP `2717:ff40` ->
  AOA `18d1:2d00`, AA 1.7/TLS/service discovery, 1280x720 H.264 + 48 kHz
  stereo audio, browser/FIFO touch input. Artifacts:
  `captures/2026-10-28-macos-session2-*` (3057 frames / 122 s, 68.6 s audio).
- macOS local run/stop: `scripts/mac-headunit-start.sh`,
  `mac-headunit-stop.sh`. Capture dir `captures-mac/`; stream server runs on
  localhost (no Pi, hub, or SSH tunnel).

**Recovery caveat on macOS:** if the first AA entity fails before the phone is
associated, the dongle stays in AOA and `autoapp` waits at
`Waiting for device...`. Unplug/replug the dongle (cold boot to MTP) with the
phone's BT/Wi-Fi on; the next AOA switch projects. With the phone already
associated, the normal first-session reset reconnects automatically.

**Next:** long-run stability on macOS, per-session capture filenames, and the
headless emulator work. No physical dongle test remains blocking.

**Minimal app status: rejected for now.** It completes AA 1.7/TLS/service
discovery and captures real video, but resets every session and does not
recover. We tested removing WPP, telephony, BT auth data, the whole BT service,
and a reconnect loop; it still reset. OpenAuto is the working stack.

## macOS build/run summary

Full commands are in [`MAC-PORT.md`](MAC-PORT.md). Key points:

- `brew install boost@1.85 qt@5 taglib rtaudio util-linux gpsd protobuf abseil
  libusb openssl@3 pkg-config`; Boost 1.85 is mandatory (`io_service`).
- aasdk: `aasdk-upstream` + `AASDK_MINOR = 7`; build dir `build-aasdk-mac`;
  force `Boost_DIR` to 1.85 (`'-UBoost_.*'` when reconfiguring a cached tree).
- OpenAuto: `4cc739b8`, apply `patches/openauto-capture.patch` and
  `patches/openauto-macos.patch`; configure with the extra absl/taglib/gps
  includes and OpenSSL link flags from MAC-PORT.
- Python: `.venv/bin/python` with `websockets` (repo-local venv).

## Useful values

- Dongle: MTP `2717:ff40`, AOA `18d1:2d00`; BT/Wi-Fi `AutoLink-A512`;
  Wi-Fi password `12345678`; BT `ED:A2:A4:94:4F:B8`.
- Galaxy S25 BT `5C:D3:3D:56:71:F4`; AA 17.9; ADB `RFGL329J04J`.
- Pi: `auriga-pi.local` / `192.168.2.2`; builds `~/auriga/build-openauto`,
  `~/auriga/build-aasdk`; captures `~/auriga/captures-openauto`.
- Mac builds: `build-aasdk-mac`, `build-openauto-mac`; captures
  `captures-mac`.

## Important files

- `README.md` — project state, quick start.
- `MAC-PORT.md` — exact macOS build/run path, fixes and status.
- `RUNBOOK.md` — operational steps, BT recovery, streaming, Mac local mode.
- `openauto-plan.md` — full build/run/patch history on the Pi.
- `stream/` — WebSocket server + Brave client (GOP cache for new clients).
- `patches/openauto-capture.patch` — file sinks applied to OpenAuto.
- `patches/openauto-macos.patch` — macOS Bluetooth lister + AirPlay/TCP-5000
  fixes.
- `openauto-config/` — config, `run.sh` (Pi), `run-mac.sh` (macOS).
- `scripts/` — Pi/Mac start-stop, `aa-tap.sh`.
- `dongle-backup/` — BT DB backups/restore rules.
- `captures/`, `captures-mac/` — local media artifacts (not in git).
