# Next session handoff

## Current state (2026-10-28, end of session)

**Working on the Pi:**

- Full OpenAuto (`4cc739b8`) + aasdk 1.7 projects the Galaxy S25 through the
  AutoLink dongle.
- Captures 1280x720 H.264, 48 kHz/16-bit stereo media audio, JSONL touch input.
- Pi stream server + Brave/Chrome client works; late clients now receive the
  cached GOP (keyframe + deltas) so video decodes.
- Start/stop: `scripts/pi-start.sh`, `pi-stop.sh`, `mac-start.sh`, `mac-stop.sh`.
- BT reset: deleting `btapp.db`/`btapp.bk` and re-pairing restored advertising.
  Current DB is the fresh 33-byte one (`dongle-backup/btapp.db.galaxy-fresh`).

**Minimal app status: rejected for now.**

It completes AA 1.7/TLS/service discovery/channel setup and captures real video,
but resets every session and does not recover. We tested removing WPP,
telephony, BT auth data, the whole BT service, and a reconnect loop; it still
reset. Use OpenAuto for the working stack. The minimal app remains the basis for
a future headless emulator, but it is not the current target.

**Next: move the proven stack to macOS.**

The plan is in [`MAC-PORT.md`](MAC-PORT.md): dongle direct to Mac USB, OpenAuto
built natively (no Qt UI changes beyond NOPI/capture patch), stream server on
localhost, no Pi/hub/SSH.

## Prompt to paste into the new session

```text
We are continuing the Auriga project in /Users/tomaszwerbicki/dev/auriga.

Read, in this order:
1. README.md
2. MAC-PORT.md
3. RUNBOOK.md
4. openauto-plan.md
5. stream/README.md

Goal: move the proven Android Auto head unit from the Pi to macOS, with the
AutoLink dongle plugged directly into the Mac. No Pi, no powered hub, no SSH
tunnel. Keep the same behavior and capture pipeline.

Use OpenAuto, not the minimal capture/ app. The minimal app completes AA
1.7/TLS/service discovery and captures some video, but resets every session; we
already tested removing WPP, telephony, BT auth, the whole BT service, and
adding a reconnect loop without fixing it. OpenAuto projects end-to-end and
auto-reconnects after the dongle's first-session USB reset.

Mac port plan (details in MAC-PORT.md):
1. brew install boost@1.85 qt@5 taglib rtaudio util-linux gpsd protobuf abseil
   libusb openssl@3 pkg-config. boost@1.85 is required because aasdk/OpenAuto
   use boost::asio::io_service, removed in Boost 1.92.
2. Build aasdk 1.7 (newdev source, Version.hpp minor=7) for macOS:
   - CMAKE_POLICY_VERSION_MINIMUM=3.5
   - SKIP_BUILD_PROTOBUF=ON, SKIP_BUILD_ABSL=ON, AASDK_TEST=OFF
   - add absl include dirs to the generated aap_protobuf target (protobuf 36
     headers include absl)
   - macOS builds static libaasdk.a / libaap_protobuf.a.
3. Build OpenAuto 4cc739b8 with NOPI=ON + patches/openauto-capture.patch:
   - AASDK_INCLUDE_DIR=<aasdk>/include/aasdk and
     CMAKE_CXX_FLAGS_INIT=-I<aasdk>/include
   - AASDK_LIB_DIR=.../libaasdk.a
   - AAP_PROTOBUF_INCLUDE_DIR=.../build-aasdk-mac/protobuf
   - AAP_PROTOBUF_LIB_DIR=.../libaap_protobuf.a
   - CMAKE_PREFIX_PATH with qt@5, boost@1.85, protobuf, abseil, taglib,
     rtaudio, util-linux, gpsd, openssl@3, libusb.
4. Run autoapp with AURIGA_CAPTURE_DIR and QT_QPA_PLATFORM=offscreen; run
   stream/auriga_stream.py with the Mac capture paths; open
   http://localhost:8080 in Brave.
5. Move the dongle to the Mac; phone stays paired to AutoLink-A512. Test AOA,
   projection, video/audio/input. Expect one first-session reset; OpenAuto
   auto-reconnects.

Constraints:
- No firmware flashing, factory reset, or dongle/phone writes/deletes without
  explicit approval.
- Keep iPhone/OPPO BT/Wi-Fi off during AA tests.
- The dongle is a relay at the AA layer: the phone sees OpenAuto's display_name
  and service set.
- The Pi stack is the fallback and is committed; don't break it while porting.
- Persist findings and commit.

Useful current values:
- Dongle: MTP 2717:ff40, AOA 18d1:2d00; BT/Wi-Fi AutoLink-A512;
  Wi-Fi password 12345678; BT ED:A2:A4:94:4F:B8.
- Galaxy S25 BT 5C:D3:3D:56:71:F4; AA 17.9.
- Pi: auriga-pi.local / 192.168.2.2.
- Pi build: ~/auriga/build-openauto, ~/auriga/build-aasdk.
- Capture: ~/auriga/captures-openauto; stream: ~/auriga/stream.
- Mac ADB works: adb devices shows RFGL329J04J (SM-S931B).
```

## Important files

- `README.md` — project state, quick start.
- `MAC-PORT.md` — macOS build/run plan and known blockers.
- `RUNBOOK.md` — operational steps, BT recovery, streaming.
- `openauto-plan.md` — full build/run/patch history and results.
- `stream/` — Pi WebSocket server + Brave client (GOP cache for new clients).
- `patches/openauto-capture.patch` — file sinks applied to OpenAuto.
- `openauto-config/` — config + launch script.
- `scripts/` — Pi/Mac start-stop, `aa-tap.sh`.
- `dongle-backup/` — BT DB backups/restore rules.
- `captures/` — local media artifacts (large files not in git).
