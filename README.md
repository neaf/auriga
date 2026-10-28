# Auriga

Raspberry Pi 3B acting as an Android Auto head unit for an **AutoLink** wireless
Android Auto / CarPlay USB dongle, with the goal of extracting the phone's
video, audio and input streams and later forwarding them to a real head unit.

> **Read this first:** the dongle has been **reconfigured via its MTP config
> files** (not firmware). Backups and restore instructions are in
> [`dongle-backup/`](dongle-backup/README.md). Do not flash firmware, factory
> reset, or restore the old config without explicit approval.

## Status (2026-10-28)

**What works**

- Pi hostname `auriga-pi.local`, address `192.168.2.2/24`, power clean
  (`vcgencmd get_throttled` = `0x0`).
- Dongle AOA switch works: `2717:ff40` -> `18d1:2d00`, AOA v2.
- The dongle's phone-facing radios work: Bluetooth Classic `AutoLink-A512`
  and 5 GHz Wi-Fi AP `AutoLink-A512` (password `12345678`).
- The Galaxy S25 is paired to the dongle (`5C:D3:3D:56:71:F4`) and is the only
  phone the dongle now targets.
- A real car trip with this dongle + Galaxy worked, including Google Maps. The
  dongle's AA side, phone pairing and car relay are therefore good.
- The minimal head-unit app in [`capture/`](capture/) reaches AA version, TLS,
  service discovery and channel opens; after the BT DB fix, one run stayed in
  AOA for the full 120 s without resetting.

**2026-10-28 result: full OpenAuto projects**

- The full stack (`opencardev/openauto` main @ `4cc739b8` + the Pi's aasdk 1.7)
  completes AA 1.7, TLS, service discovery, video focus/start and media setup.
- The phone projected: 1280x720 H.264 video, 48 kHz/16-bit stereo media audio
  (Spotify routed to "Android Auto"), and touch input injection all work.
- The phone shows the head unit as **Crankshaft-NG** because OpenAuto hardcodes
  `display_name`; this is cosmetic and should be renamed to Auriga.
- Wi-Fi credentials are exchanged by the **dongle**, not the Pi. OpenAuto
  deliberately does not advertise WPP; the dongle is the AP/WPP endpoint.
- The dongle is **not a full terminator at the AA layer**. It terminates the
  phone-side Wi-Fi/WPP/BT link but forwards AA service discovery and messages
  between phone and head unit: the phone displays OpenAuto's hardcoded
  `display_name` "Crankshaft-NG" and sees its service set. Head-unit service
  advertisement and behaviour therefore matter.
- The dongle's BT advertising returned only after deleting `btapp.db` and
  `btapp.bk` and re-pairing the Galaxy (6-digit numeric comparison). The dongle
  recreated a 33-byte `btapp.db`; `btapp.bk` is currently absent. Backup:
  `dongle-backup/btapp.db.galaxy-fresh`.
- Capture artifacts: `captures/2026-10-28-session2-video.h264`,
  `2026-10-28-session2-audio-media.wav`, extracted frames and
  `2026-10-28-session2-input.jsonl`. The stream can be viewed live with
  `ffplay` over SSH; `scripts/aa-tap.sh` injects touches.

**2026-10-28 macOS port: projection works**

- aasdk 1.7 (`newdev` + `AASDK_MINOR = 7`) builds static for macOS with
  Boost 1.85: `build-aasdk-mac/lib/libaasdk.a` and `libaap_protobuf.a`.
- OpenAuto `4cc739b8` + `patches/openauto-capture.patch` +
  `patches/openauto-macos.patch` builds `build-openauto-mac/bin/autoapp`.
- With the dongle direct to the Mac, the dongle switched MTP `2717:ff40` ->
  AOA `18d1:2d00`, completed AA 1.7/TLS/service discovery, and projected a full
  1280x720 AA UI (Google Maps + Spotify) with 48 kHz stereo media audio.
- Verified capture: 3057 H.264 frames over 122 s, 68.6 s media audio (mean
  -16.5 dB), browser/FIFO touch input (a Spotify pause/play tap changed the
  UI), and a WebSocket client receiving keyframes/deltas/audio on localhost.
- Run/stop: `scripts/mac-headunit-start.sh` / `mac-headunit-stop.sh`;
  captures go to `captures-mac/`; no Pi, hub or SSH tunnel.
- macOS-specific fixes: Boost 1.85 (`io_service`), absl/taglib/gps include
  roots, static-aasdk OpenSSL link symbols, a broken Bluetooth lister in
  `SettingsWindow.cpp`, and OpenAuto's TCP-5000 listener conflicting with
  macOS AirPlay Receiver.
- Recovery note: if the first AA entity fails before the phone associates, the
  dongle stays in AOA; replug it (cold boot to MTP) with phone BT/Wi-Fi on.
  With the phone already associated, OpenAuto reconnects after the dongle's
  first-session reset automatically.

**Remaining issues**

- The first AA session reset on the dongle's AA Bluetooth pairing request
  (`AASDK Error 10`, USB transfer). OpenAuto reconnected automatically and the
  second session was stable; this needs investigation (DummyBluetoothDevice /
  Bluetooth service behaviour).
- Capture files are opened with truncation, so a new AA session overwrites the
  previous one. Per-session filenames are needed.
- The file sinks ignore AA timestamps; streamed audio/video are not
  sample-synced. A timestamp-preserving mux/capture is the next improvement.
- Forwarding to a real head unit still needs a Pi 4/5 (host + OTG) or a
  two-device relay.
- Build/run/patch details are in [`openauto-plan.md`](openauto-plan.md).
- Next: long-run stability on macOS and per-session capture filenames. The
  physical Mac USB path is proven; build/run details and status are in
  [`MAC-PORT.md`](MAC-PORT.md).

## Quick start

macOS head unit (dongle direct to the Mac, no Pi):

```bash
cd /Users/tomaszwerbicki/dev/auriga
./scripts/mac-headunit-start.sh
```

Then open `http://localhost:8080` (Brave/Chrome), click the small 🔇 to enable
audio, and tap the canvas to drive AA. Stop with
`./scripts/mac-headunit-stop.sh`.

Pi head unit (fallback) with the Mac as remote UI:

```bash
# on the Pi
~/auriga/scripts/pi-start.sh
# on the Mac
cd /Users/tomaszwerbicki/dev/auriga
./scripts/mac-start.sh
```

Then open `http://localhost:8080` and click the 🔇 to enable audio. Stop with
`scripts/mac-stop.sh` and `~/auriga/scripts/pi-stop.sh`.

Full setup, pairing recovery, rebuild steps and known issues are in
[`RUNBOOK.md`](RUNBOOK.md). The remote UI protocol is documented in
[`stream/README.md`](stream/README.md).

## Hardware / network

| Item | Detail |
| --- | --- |
| Pi | Raspberry Pi 3 Model B Rev 1.2, 4 cores, 920 MiB RAM, 58 GB SD |
| OS | Raspbian GNU/Linux 13 (trixie), kernel `6.18.50+rpt-rpi-v7`, armv7l |
| Hostname | `auriga-pi.local` (renamed from `mevia-pi`) |
| Address | `192.168.2.2/24` on `eth0`; default route via `192.168.2.1` |
| Power | Powered USB hub; `throttled=0x0`; original undervoltage fixed |
| Hub | Realtek RTS5411; dongle on `1-1.4.4` port 2 (PPPS), plus Komplete Audio 6 and USB MIDI |
| Phone | Samsung Galaxy S25 (`SM-S931B`), AA `17.9.664044-release`, BT `5C:D3:3D:56:71:F4` |

Important: the Pi 3B has a single `dwc_otg` controller feeding the on-board USB
hub; its micro-USB is power-only. It **cannot be USB host (dongle) and USB
gadget (real head unit) at the same time**. Forwarding later needs a Pi 4/5
(separate host + OTG controllers) or a two-device relay.

Also: `uhubctl` port power switching may disable the data port without cutting
VBUS. A **physical replug** is the reliable full dongle power cycle. The iPad/
iPhone must be off during AA tests or the dongle will latch into CarPlay mode.

## Dongle identity

| Interface | Value |
| --- | --- |
| USB MTP / AA mode | `2717:ff40`, manufacturer `Android`, product `AutoLink`, serial `lyax1234a512` |
| USB AOA | `18d1:2d00`, 2 bulk endpoints `0x81` IN / `0x02` OUT, 512-byte packets |
| USB Apple / CarPlay mode | `05ac:12a8`, product `iPhone`, 4 configurations (PTP / iPod / Apple Mobile Device / Apple Ethernet) |
| AOA protocol | version 2 (GET_PROTOCOL returns `[2,0]`) |
| Bluetooth | `AutoLink-A512`, `ED:A2:A4:94:4F:B8`, class `0x200420` (car audio), HFP |
| Wi-Fi AP | `AutoLink-A512`, BSSID `e8:5c:b1:b5:c6:41`, 5180 MHz (5 GHz, ch 36), WPA2-PSK, password `12345678` |
| AA version reported by dongle | `256.1792` (0x0100/0x0700 = protocol 1.7) |
| MTP friendly name | `smartlinkBox` |

Mode selection is phone-driven: an iPhone connecting flips the dongle to
`05ac:12a8` (CarPlay); connecting the Android phone to `AutoLink-A512` flips it
back to `2717:ff40` (AA). In CarPlay mode the device rejects AOA
(`Pipe error`).

## Dongle config files (MTP, not firmware)

Original MTP root listing (before any edits):

| File | Size | Meaning |
| --- | ---: | --- |
| `800x480-A512.h264` | 34,134 | AA boot splash/animation; **now missing**, no exact backup; car works without it |
| `carplay.key` | 1,433 | AirPlay/CarPlay pairing identity; present, not backed up |
| `ly_linktype_aa` | 1 | `0x01` = AA mode |
| `btapp.bk` | 207 | Bluetooth pairing DB backup |
| `btapp.db` | 207 | Bluetooth pairing DB |
| `ly-AutoLink-A512` | 8 | ASCII `OPPO A72` (last phone name cache; still OPPO) |
| `bt.mac` | 12 | ASCII `EDA2A4944FB8` |
| `videoInfo` | 364 | AA video SPS/PPS + phone address + head-unit name + session tag |

### `videoInfo` layout

- `0x00..0x31`: config header + H.264 SPS/PPS for the **AA stream**, which
  decodes to **1280x720 Baseline level 3.2** (not the 800x480 splash).
- `0x50`: `02 00 00 00`
- `0x54`: phone Bluetooth address, 17 ASCII chars + NUL
- then: head-unit name (NUL-terminated)
- then: session tag `1493 _0`
- trailing 4 bytes change between sessions.

Versions of this file:

| File | Phone address | Head-unit name | Notes |
| --- | --- | --- | --- |
| `dongle-backup/videoInfo.orig` | `14:47:2D:4C:20:1A` (OPPO) | `auriga-pi` | original bench config |
| `dongle-backup/videoInfo.car-trip` | `14:47:2D:4C:20:1A` (OPPO) | `T  M91850...` | written by the real car trip |
| `dongle-backup/videoInfo.galaxy` | `5C:D3:3D:56:71:F4` (Galaxy) | `auriga-pi` | current active config |

### `btapp.db` / `btapp.bk`

Original DB contained two devices:

- Galaxy `5C:D3:3D:56:71:F4` (stored reversed `f4 71 56 3d d3 5c`) — first record
- OPPO `14:47:2D:4C:20:1A` (reversed `1a 20 4c 2d 47 14`) — second record

The dongle kept sending the **OPPO** address in its AA Bluetooth pairing
request. The active DB and backup have been patched to:

- two Galaxy addresses,
- the Galaxy's two 16-byte link keys in **both** records:
  - key1 `ed4528010fa1e8514c7b33e3ff43beff`
  - key2 `901226b5aba81300010435811ac9c286`
- zero OPPO occurrences.

The patch changes only the 6-byte address and the 32 key bytes in the second
record; all other bytes/size (207) are unchanged. Backups:
`btapp.db.orig`, `btapp.bk.orig`, and the active patched
`btapp.db.galaxy`, `btapp.bk.galaxy`.

**Effect:** the dongle now sends its AA pairing request for the Galaxy
(`5C:D3:3D:56:71:F4`), not the OPPO. This is what stopped the dongle resetting
in the long AOA run.

### 2026-10-28 BT reset (current state)

BT advertising later stopped entirely while the 207-byte duplicate-Galaxy DB
was active. The phone was told to forget `AutoLink-A512` on both BT and Wi-Fi,
then **both `btapp.db` and `btapp.bk` were deleted from the dongle** via MTP.
No DB file was uploaded.

After a cold boot, `AutoLink-A512` advertised again immediately. The Galaxy
paired with a 6-digit numeric-comparison code (BT "for calls") and the dongle
recreated a **33-byte** `btapp.db`: one Galaxy record with the new link key.
`btapp.bk` was not recreated. Backup: `dongle-backup/btapp.db.galaxy-fresh`
(33 bytes, sha256 `f6b4b7e6...`). The 207-byte `galaxy2` DB is historical and
its keys are stale after the re-pair.

Deleting the DB is what restored BT advertising and allowed the successful
OpenAuto projection run. The dongle's Wi-Fi AP stayed visible throughout; only
the BT stack was affected.

## Protocol / failure findings

1. The dongle implements AOA v2. AOA switch works; identity strings are
   `Auriga` / `Auriga Pi Capture` / `Android Auto capture head unit` / `1.0` /
   empty URI / `auriga-pi`.
2. The dongle reports AA protocol **1.7**. aasdk was hardcoded to **1.6**;
   it was bumped to 1.7 in `aasdk/include/aasdk/Version.hpp` and rebuilt.
3. The minimal app completes version, TLS, service discovery and channel opens.
   The dongle asks for sensor start data (driving status, location, night mode)
   and opens video/audio/mic/sensor/Wi-Fi-projection/input/Bluetooth channels.
4. Without the DB fix the dongle reset with `AASDK Error 10` (`USB_TRANSFER`,
   native `LIBUSB_ERROR_IO`) after the idle video stream start. After the DB fix,
   one run stayed in AOA for 120 s and reached channel opens without resetting.
5. The phone still errors:
   `CAR.SETUP.LITE: ProjectionErrorCode = PROTOCOL_IO_ERROR(3)`,
   `ProjectionErrorDetail = READER_CLOSE(52)`, then
   `GH.WPP.CONN: Stopping Wifi Projection Protocol read and write threads`.
   The phone UI shows "Communication error 2 - incompatible software".
6. The car trip with the same dongle/phone worked, so the dongle's car-side AA
   stack and the phone are fine. The remaining gap is the Pi head-unit/WPP
   behavior, not the dongle hardware.
7. The dongle's idle screen (captured as H.264) says:
   "Drive with Wireless Android Auto — Please keep your Phone's WLAN turned on
   and not occupied. Please turn on Bluetooth to pair with the AutoLink-A512."
   This is the dongle waiting for the phone-side connection, not projection.
8. The phone's AA settings showed
   `Connection -> AutoLink-A512 -> Wireless Android Auto available`.
   Its WPP RFCOMM connects to the dongle and then closes.
9. The minimal app has a 2 s control-channel pinger and replies to incoming
   pings; it did not fix the WPP close. The full OpenAuto stack is the next step.

## Minimal app (`capture/`)

Built on `opencardev/aasdk` (modern fork, commit `9bf6adf`), with aasdk protocol
1.7. It is headless and writes raw files:

| Channel | Output |
| --- | --- |
| Video | `captures/video.h264` (H.264 Annex-B, 1280x720 requested) |
| Media / system / guidance / telephony audio | `captures/audio-*.wav` (48 kHz, 16-bit, stereo) |
| Input | `captures/input.jsonl` + stdin touch injection |
| Control / Bluetooth / sensor / microphone / Wi-Fi projection | logged, protocol handling |

Notable app features:

- AOA retry loop (dongle may cycle between MTP/AOA).
- Advertises video, 4 audio sinks, Bluetooth, input, sensor, microphone and
  Wi-Fi projection services.
- Sensor: driving status unrestricted, night mode, empty location (Pi has no GPS).
- Microphone: advertises PCM input; accepts open/close without real mic data.
- Wi-Fi projection: advertises `AutoLink-A512` BSSID and returns SSID/password.
- Pinger: `PingRequest` immediately after service discovery, then every 2 s;
  replies to incoming pings.
- Video focus indication after video setup.

Build/run is documented in [`capture/README.md`](capture/README.md).

## Why the minimal app was the wrong first choice

The minimal app was chosen to avoid a Qt/OpenAuto build and to get raw channels
quickly. That was the wrong first risk trade-off: the car's head unit behavior
(full service set, timing, focus/keepalive, UI) is the known-good reference,
and the minimal app never matched it. Full OpenAuto was built and now works
(see above). The minimal app was retested after the BT DB fix: it completes
AA/TLS/service discovery and captures some video, but resets on every session
and does not recover. Removing WPP, telephony, BT auth, the whole BT service,
and adding a reconnect loop did not fix it, so it is **not** the current working
stack; OpenAuto is. The minimal app remains the basis for a future headless
emulator.

## Next plan: headless emulator + streaming

Full OpenAuto now works as the reference/capture host. Next:

1. Build `auriga-headunit` from `capture/` + aasdk 1.7, matching OpenAuto's
   working service set (no WPP/telephony; test the Bluetooth variants) and
   running headless without Qt.
2. Feed the `stream/` WebSocket protocol directly from aasdk callbacks with AA
   timestamps, fixing A/V sync and per-session capture files.
3. Fix the first-session Bluetooth pairing reset (AA Bluetooth service /
   DummyBluetoothDevice).
4. Forward to a real head unit (Pi 4/5 or two-device relay) once the capture
   host is stable.

Secondary: keep OpenAuto as the capture host and use the `stream/` Mac client.

## File map

- `capture/` — minimal headless aasdk capture app (reference; basis for the
  custom emulator).
- `openauto/` — upstream `opencardev/openauto` main clone (pinned `4cc739b8`)
  with the Auriga capture patch applied on the Pi.
- `aasdk-upstream/` — upstream `opencardev/aasdk` newdev clone for comparison.
- `openauto-plan.md` — full OpenAuto build/run/patch plan and open questions.
- `MAC-PORT.md` — macOS port plan (dongle direct to Mac, no Pi).
- `patches/openauto-capture.patch` — file-sink/video/audio/input patch applied
  to OpenAuto on the Pi.
- `patches/openauto-macos.patch` — macOS build fixes (Bluetooth lister,
  AirPlay/TCP-5000 conflict in capture mode).
- `openauto-config/` — `openauto.ini`, `openauto-logs.ini`, `run.sh` (Pi),
  `run-mac.sh` (macOS).
- `stream/` — Pi WebSocket server + Brave/Chrome client for live video/audio
  and taps.
- `captures/` — captured H.264/WAV/JSONL samples and extracted frames.
- `logs/` — filtered OpenAuto run logs.
- `scripts/aa-tap.sh` — send a tap to the live capture from the Mac.
- `scripts/mac-headunit-start.sh`, `mac-headunit-stop.sh` — local macOS head
  unit (no Pi); `mac-start.sh`, `mac-stop.sh` are the Pi remote-UI tunnel.
- `aasdk/`, `build-aasdk/` — aasdk source/build on the Pi (not in this repo).
- `scripts/aoa_probe.py` — standalone AOA switch/read.
- `scripts/aoa_read.py` — passive bulk-IN reader.
- `dongle-backup/` — original and current dongle config files + restore notes.
- `posttrip/` — post-car-trip dongle config snapshots.
- `README.md` — this file.
- `NEXT-SESSION.md` — new-session prompt and handoff.

## Working rules

- No firmware flashing, factory reset, or dongle/phone writes without explicit
  approval.
- Before each batch of commands, state the next 1-2 steps and wait for OK.
- Keep the iPhone and OPPO Bluetooth/Wi-Fi off during AA tests.
- Never assume `uhubctl` cuts VBUS; use a physical replug when a true cold boot
  is needed.
- The splash `800x480-A512.h264` is missing and not boot-critical (car proved
  it). Do not upload a fake splash without approval.
