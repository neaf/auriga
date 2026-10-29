# Audit: dongle-hardware

## Coverage

| File | Lines | Read fully |
| --- | --- | --- |
| README.md | 389 | yes |
| AGENTS.md | 162 | yes |
| RUNBOOK.md | 306 | yes |
| openauto-plan.md | 477 | yes |
| dongle-backup/README.md | 124 | yes |
| dongle-backup/bt.mac.txt | 1 | yes (12 bytes on dongle, `EDA2A4944FB8`) |
| dongle-backup/ly-AutoLink-A512.orig | 1 | yes (8 bytes, `OPPO A72`, no NUL) |
| dongle-backup/ly_linktype_aa | 1 byte bin | yes (`01`) |
| dongle-backup/videoInfo.orig | 364 B bin | yes (full hex) |
| dongle-backup/videoInfo.car-trip | 364 B bin | yes (full hex) |
| dongle-backup/videoInfo.galaxy | 364 B bin | yes (full hex) |
| dongle-backup/videoInfo.galaxy.active | 364 B bin | yes (full hex) |
| posttrip/videoInfo.post | 364 B bin | yes (full hex) |
| posttrip/ly-AutoLink-A512.post | 1 | yes (8 bytes, `OPPO A72`) |
| posttrip/ly_linktype_aa.post | 1 byte bin | yes (`01`) |
| scripts/aoa_probe.py | 96 | yes |
| scripts/aoa_read.py | 57 | yes |
| patches/aasdk-usb-filter.patch | 101 | yes |
| patches/openauto-auriga-usb-filter.patch | 42 | yes |

1759 text lines + 5 binary `videoInfo` snapshots (1820 bytes).

Cross-checked against files outside the assignment: `openauto/src/autoapp/{App.cpp,autoapp.cpp}`, `aasdk-upstream/src/USB/{USBHub.cpp,AccessoryModeQueryFactory.cpp,ConnectedAccessoriesEnumerator.cpp,AOAPDevice.cpp}`, `aasdk-upstream/include/aasdk/Version.hpp`, `capture/src/{Usb.cpp,WifiProjectionCapture.cpp}`, `.gitignore`, `logs/*.log`, `patches/*.patch`.

## Functional behavior

- F1: The dongle enumerates as MTP `2717:ff40` (product `AutoLink`) and re-enumerates as AOA `18d1:2d00` after the host's AOA switch. Evidence: README.md:154-155, README.md:18, openauto-plan.md:189. Status: active (19 `Version Received` lines in `logs/*.log` confirm sessions past the switch).
- F2: The host AOA-switches only VID/PID `2717:ff40`; all other non-AOA devices are ignored. Evidence: patches/openauto-auriga-usb-filter.patch:38-39 → openauto/src/autoapp/autoapp.cpp:245-246; enforcement in patches/aasdk-usb-filter.patch:55-80 → aasdk-upstream/src/USB/USBHub.cpp:109-135. Status: active.
- F3: The all-device AOA probe (`ConnectedAccessoriesEnumerator`) runs the *full* AOA chain (GET_PROTOCOL, 6× SEND_STRING, START) against **every** openable USB device, and is skipped only when `AURIGA_CAPTURE_DIR` is set. Evidence: openauto/src/autoapp/App.cpp:59; aasdk-upstream/src/USB/ConnectedAccessoriesEnumerator.cpp:76-83; aasdk-upstream/src/USB/AccessoryModeQueryChain.cpp:50-140. Status: active outside capture mode, dead inside it.
- F4: The dongle reports AA version `256.1792` (protocol 1.7: `0x0100`/`0x0700`). Evidence: README.md:160; `logs/openauto-mac-*.log` ×19. Status: active.
- F5: aasdk's advertised protocol minor was edited from 6 to 7 to match the dongle. Evidence: `aasdk-upstream/include/aasdk/Version.hpp:27` (`AASDK_MINOR = 7`). Status: active, unpatched (see D6).
- F6: `ly_linktype_aa` is 1 byte `0x01` and selects AA mode. Evidence: dongle-backup/ly_linktype_aa (hex `01`), posttrip/ly_linktype_aa.post (hex `01`), dongle-backup/README.md:13, README.md:176. Status: active.
- F7: `videoInfo` is a 364-byte little-endian struct, not just "header + SPS/PPS". Verified layout from all five snapshots: `0x00` magic `03 07 24 20`; `0x04` u32 width = 1280 (`00 05 00 00`); `0x08` u32 height = 720 (`d0 02 00 00`); `0x0c` u32 0 or 2; `0x10` `15 08 00 00`; `0x12` Annex-B start code; `0x16..0x26` 17-byte SPS (profile 0x42, constraint 0x80, level 0x20 = Baseline 3.2); `0x27` start code; `0x2b..0x2f` 5-byte PPS; `0x50` u32 = 2 (orig, car-trip) or 4 (galaxy); `0x54` phone BT address, 17 ASCII + NUL; `0x68..0x71` head-unit name, fixed 10 bytes, no NUL when full (`T  M918500`); `0x72..0x79` session tag, 8 bytes (`1493 _0`); `0x168` trailing u32. Status: active.
- F8: The dongle's BT pairing DB has two layouts: 207-byte, two records (header `02 01`, 6-byte address stored reversed, `13 00 01 04`, 16-byte key, `00 01 01`, 16-byte key2, `00 42 54 <u16>`), and 33-byte, one record with one key and no key2 block. Evidence: dongle-backup/btapp.db.orig (Galaxy `f4 71 56 3d d3 5c` at `0x02`, OPPO `1a 20 4c 2d 47 14` at `0x3D`), dongle-backup/btapp.db.galaxy-fresh (33 B); README.md:201-238, dongle-backup/README.md:30-55. Status: active.
- F9: The dongle is an AA-layer relay: it terminates phone-side BT/Wi-Fi/WPP but forwards AA service discovery, so the phone displays the head unit's `display_name`/service set. Evidence: README.md:39-43, RUNBOOK.md:10-12, openauto-plan.md:21-24. Status: active, doc-derived (no capture in repo).
- F10: The dongle is phone-driven into CarPlay mode (`05ac:12a8`), where it rejects AOA. Evidence: README.md:156, README.md:163-166, README.md:148. Status: unclear (no capture; the `05ac:12a8` identity has no recorded test artifact in the repo).
- F11: Dongle config writes are manual MTP operations (`mtp-delfile`/`mtp-sendfile`), never programmatic. Evidence: dongle-backup/README.md:62-110. Status: active.
- F12: The car trip rewrote only `videoInfo` (head-unit name + one header byte + SPS/PPS); `btapp.db`, `ly-AutoLink-A512`, `ly_linktype_aa` were unchanged. Evidence: `posttrip/videoInfo.post` == `dongle-backup/videoInfo.car-trip` (sha256 `325f2719…`); `posttrip/btapp.db.post` == `dongle-backup/btapp.db.orig` (sha256 `4023b49d…`); `posttrip/ly-AutoLink-A512.post` == `OPPO A72`. Status: active, evidenced.

## External facts and quirks

- X1: AOA v2 (`GET_PROTOCOL` → `[2,0]`). Source: doc (README.md:157, README.md:246), unverified in repo; `scripts/aoa_probe.py:50-52` prints it but no output is stored.
- X2: AOA interface has 2 bulk endpoints, `0x81` IN / `0x02` OUT, 512-byte packets. Source: doc (README.md:155). Code assumes exactly 2 endpoints and picks direction by `bEndpointAddress` bit: aasdk-upstream/src/USB/AOAPDevice.cpp:28-44, `scripts/aoa_read.py:43` (512). Unverified as hardware fact.
- X3: BT advertising dies when `btapp.db` holds duplicate/stale records. Symptom: `AutoLink-A512` not visible on BT; Wi-Fi AP unaffected. Cause (per doc): stale OPPO record / duplicate Galaxy records. Workaround that worked: delete `btapp.db`+`btapp.bk` via MTP, cold boot, re-pair (6-digit numeric comparison). Source: doc, README.md:226-242, RUNBOOK.md:162-182.
- X4: The dongle re-enumerates as MTP roughly every 22.0 s while idle, with no host process holding the device. Source: doc, openauto-plan.md:74-80, `scripts/aoa_probe.py:4-6`. Never re-measured after the BT DB reset; also the only window in which a cold `autoapp` can catch it.
- X5: `uhubctl` port power switching may kill only the data port, not VBUS; only a physical replug cold-boots the dongle. Source: doc, README.md:146-147, AGENTS.md:139-142, dongle-backup/README.md:122-123. Unverified.
- X6: `libusb` reset does not restore MTP on a dongle stuck in AOA with a stale TLS session. Source: doc, AGENTS.md:139-142. Unverified.
- X7: Wi-Fi AP `AutoLink-A512`, BSSID `e8:5c:b1:b5:c6:41`, 5180 MHz ch36, WPA2-PSK `12345678`. Source: doc, README.md:159. The PSK and SSID are hard-coded into the dead minimal app: `capture/src/WifiProjectionCapture.cpp:75-80`.
- X8: The dongle in MTP registers as Xiaomi VID `0x2717`. Source: `scripts/aoa_probe.py:4` (comment "Xiaomi MTP"), patches/openauto-auriga-usb-filter.patch:35. VID reuse is the vendor's, not a dongle property.
- X9: `btapp.db` trailer is not a CRC of the payload under 9 common CRC-16 variants (CCITT-FALSE, XMODEM, KERMIT, X25, MODBUS, IBM, ARC, AUG-CCITT, GENIBUS, endianness both). All three 207-byte bodies with different key bytes share trailer `4c f3`; the 33-byte body ends `0a 53`. Source: computed here. Consequence: hand-patching the DB bodies was not detected as a corrupt-checksum file, so the BT advertising failure was semantic, not checksum. Still unverified against vendor format.
- X10: The dongle LED is not an AA-link indicator (lit/blinking in MTP, dark in AOA). Source: doc, AGENTS.md:75-78, RUNBOOK.md:76-79. Unverified.
- X11: 207-byte DB patch "worked" (dongle targeted the Galaxy) but BT advertising later stopped with that same DB. Source: README.md:222-238. Timing of the failure is not recorded.

## Doc and code inconsistencies

- D1: dongle-backup/README.md:10 and :24-25 say `videoInfo.galaxy` holds the Galaxy address + `auriga-pi` with the 1280x720 SPS/PPS, and README.md:199 lists it as "current active config". The file has `0x00..0x4f` all zero — width field `0x04`=0, height `0x08`=0, no start code, no SPS, no PPS — and no session tag at `0x72`.
- D2: README.md:199 and dongle-backup/README.md:23 call the car-trip SPS/PPS the same as the bench config. Byte compare: 6 of 17 SPS bytes differ (`0x1e..0x23`: `48 28 30 30 36 85` vs `a8 08 08 08 36 85`) and the PPS differs (`68 ce 06 e2` vs `68 ce 06 f2`). Header `0x0c` also differs (0 vs 2).
- D3: dongle-backup/README.md:34-39 names four DB variants inside `dongle-backup/`; only two exist there. `dongle-backup/btapp.db.galaxy`/`btapp.bk.galaxy` (sha256 `d021cf83…`) contain the *galaxy2* content (identical to repo-root `btapp.db.galaxy2`), and repo-root `btapp.db.galaxy` (sha256 `554bb97e…`) is a different, earlier body (second record keeps the OPPO keys `21b3…`/`e724…`). `dongle-backup/*galaxy2` does not exist. dongle-backup/README.md:56-57 describes `active-btapp.db` on the Pi in `/tmp/auriga-db/` with sha `d021cf83…` — that byte-identical copy is present, under the name `dongle-backup/btapp.db.galaxy`.
- D4: README.md:185-191 layout is incomplete/wrong: SPS/PPS end at `0x2f` (doc says `0x00..0x31`), the width/height u32s at `0x04`/`0x08` are unmentioned, `0x50` is documented as always `02 00 00 00` (the galaxy snapshot has `04 00 00 00`), and "head-unit name (NUL-terminated)" then "session tag" is really a fixed 10-byte name field at `0x68` and a fixed 8-byte tag at `0x72` (`T  M918500` has no NUL before the tag).
- D5: README.md:245-248 states the AOA identity strings are `Auriga` / `Auriga Pi Capture` / `Android Auto capture head unit` / `1.0` / empty URI / `auriga-pi`. Those are the minimal app's (`capture/src/Usb.cpp:91-95`). The stack that actually projects sends `Android` / `Android Auto` / `Android Auto` / `2.0.1` / `HU-AAAAAA001` / `https://f1xstudio.com` (aasdk-upstream/src/USB/AccessoryModeQueryFactory.cpp:44-62). `scripts/aoa_probe.py:29-36` is a third set.
- D6: README.md:357-358 and DEVELOPING.md:43 say the aasdk change is `patches/aasdk-usb-filter.patch` and that `patches/` is the source of truth. The `aasdk-upstream` worktree also carries unpatched edits: `include/aasdk/Version.hpp` (6→7) and `protobuf/CMakeLists.txt` (absl include path). Neither exists in any file under `patches/`.
- D7: AGENTS.md:147-148 says "the 207-byte DBs are stale and must not be restored", while dongle-backup/README.md:80-88 gives a copy-paste restore recipe that uploads exactly `btapp.db.orig` + `btapp.bk.orig` (207 B, OPPO second record). The example contradicts the warning two paragraphs above it.
- D8: dongle-backup/README.md:6-17 describes the "current active config (2026-10-28)" as of the BT reset but is stale on two rows: `videoInfo` is unusable (D1) and `btapp.bk` is absent, so the table cannot be used as a restore baseline.
- D9: `posttrip/` is not documented in dongle-backup/README.md at all; only README.md:376 lists it, with no statement that `posttrip/videoInfo.post` is a byte-identical duplicate of `dongle-backup/videoInfo.car-trip`.
- D10: README.md:174 says `800x480-A512.h264` is "now missing" while README.md:388-389 and dongle-backup/README.md:117-120 add "a generated placeholder exists in `/tmp/auriga-splash/`". `/tmp` is volatile; the placeholder is not in the repo and the claim cannot be checked after a reboot.
- D11: AGENTS.md:131-133 states as an invariant that `autoapp` must never run an all-device AOA probe. The shipped build does exactly that whenever `AURIGA_CAPTURE_DIR` is unset (App.cpp:59), i.e. the invariant is a capture-mode-only property, not a build property.

## Assumptions to revalidate

- A1: That a `videoInfo` with zeroed width/height/SPS/PPS is harmless because the dongle rewrites it at session start. Baked into dongle-backup/README.md:24-27 (the galaxy snapshot is offered as the restore source). If false, restoring it leaves the dongle with `0x04=0`, `0x08=0` and no SPS, and video negotiation depends entirely on the phone/dongle runtime. No artifact in the repo shows a post-projection `videoInfo`.
- A2: That `0x50` = 2 is the normal value. It is 4 in the galaxy snapshot; semantics unknown. Baked into README.md:187.
- A3: That the 33-byte `btapp.db` is a complete replacement for the 207-byte form (it carries one link key, not two). Baked into dongle-backup/README.md:40-41, 67-70, RUNBOOK.md:176-182. If false, a future re-pair may need the full record shape.
- A4: That the dongle always re-enumerates when idle, so a hotplug `DEVICE_ARRIVED` event eventually arrives. Baked into aasdk-upstream/src/USB/USBHub.cpp:42-56 (ENUMERATE registered once) plus README.md:77-80. If false (no re-enumeration), the app sits at `Waiting for device...` forever with no retry.
- A5: That `18d1:2d00` can only be the dongle. Baked into patches/aasdk-usb-filter.patch:84-88 (only `18d1:2d01` is rejected). If a phone reaches AOA without ADB, autoapp would claim it and push AA at a phone.
- A6: That the relay model holds (dongle forwards AA service discovery, so OpenAuto's service set and `display_name` are what the phone sees). Baked into README.md:39-43 and the choice to keep OpenAuto as the reference stack. If the dongle is a terminator for some channels, minimal-app experiments were misdiagnosed.
- A7: That CarPlay mode is only reachable with an iPhone present. Baked into README.md:148-149, README.md:385. If the dongle can latch into `05ac:12a8` for other reasons, software recovery is impossible with the `2717:ff40` filter (see B3).
- A8: That `dongle-backup/btapp.db.galaxy-fresh` is the live pairing key set. It is gitignored (`.gitignore:41`), untracked, mode `-rwxr-----`, and dated 2026-10-28 12:51; any later re-pair silently invalidates it with no test that would notice.

## Bugs

- B1 [high]: The only documented restore source for the current phone's `videoInfo` is structurally invalid. `dongle-backup/videoInfo.galaxy` and `videoInfo.galaxy.active` have `0x04`=0 (width), `0x08`=0 (height), `0x12..0x2f` all zero (no start codes, no SPS, no PPS), and `0x72..0x79` zero (no session tag). `dongle-backup/README.md:72-79` tells the reader to upload exactly this file as `videoInfo`. Scenario: restore per doc → dongle holds a video config with 1280/720 fields cleared and no SPS, i.e. a file no other snapshot in the repo resembles.
- B2 [medium]: USB recovery has no retry path. `App::onUSBHubError` has the `waitForDevice()` retry commented out (openauto/src/autoapp/App.cpp:243-256), and `USBHub::start` registers `LIBUSB_HOTPLUG_ENUMERATE` only while `self_ == nullptr` (aasdk-upstream/src/USB/USBHub.cpp:54-62), so a later `waitForDevice()` does not re-enumerate devices already on the bus. Scenario: the AOA query chain rejects once (device busy after the switch, or a stale handle) → no second attempt, no log, the process idles until restarted.
- B3 [medium]: With the VID/PID filter, a dongle in CarPlay mode is unreachable. `isAccessoryModeSource` only matches `2717:ff40` (patches/aasdk-usb-filter.patch:55-64) and `isAOAPDevice` requires `18d1`; `05ac:12a8` matches neither, so `handleDevice` returns silently and nothing logs the mode. Scenario: an iPhone touches the dongle → `05ac:12a8` → `autoapp` never switches it, and only a replug with the iPhone off recovers (README.md:148-149 states the latch, not the software dead end).
- B4 [medium]: The all-device AOA probe is one env var away, and it sends `ACCESSORY_START` to a phone. `ConnectedAccessoriesEnumerator::enumerate` builds a full `AccessoryModeQueryChain` for every openable device (aasdk-upstream/src/USB/ConnectedAccessoriesEnumerator.cpp:76-83) and is gated only on `AURIGA_CAPTURE_DIR` (openauto/src/autoapp/App.cpp:59). Scenario: run the same binary without the env var (normal OpenAuto path, `openauto-config/run.sh` variants) → the attached Galaxy is switched to `18d1:2d01`, exactly the state AGENTS.md:131-138 forbids.
- B5 [low]: `dongle-backup/README.md:80-88` restore example uploads the stale 207-byte DBs, contradicting dongle-backup/README.md:67-70 and AGENTS.md:147-148.
- B6 [low]: `scripts/aoa_read.py:38` dereferences `ep_in`/`ep_out` without a `None` check (AttributeError if an endpoint is missing); `:46` tests `exc.errno == 110` although pyusb may set `errno=None`; no kernel-driver detach before `claim_interface`, so a Linux host with usbfs bound fails with `LIBUSB_ERROR_BUSY`.
- B7 [low]: `scripts/aoa_probe.py:29-36` reports a third AOA identity set, and `:72` shells out to `lsusb`, which does not exist on macOS — the platform the rig now runs on. The script's `start` mode would also report success from `ACCESSORY_START` on a device already in AA.
- B8 [low]: The current BT pairing backup is outside version control. `dongle-backup/btapp.db.galaxy-fresh` is matched by `.gitignore:41` (`/dongle-backup/*.db.*`), as are `btapp.db.orig` and `btapp.bk.orig` cited by dongle-backup/README.md:32-33. Scenario: fresh clone or new worktree → no pairing DB to restore, and no way to recover the link keys except a full re-pair.
- B9 [low]: `dongle-backup/README.md:56-57` relies on `/tmp/auriga-db/active-btapp.db` on the Pi — a volatile path — for the pre-deletion DB. The same bytes are actually present as `dongle-backup/btapp.db.galaxy` (sha `d021cf83…`), but under a name the doc calls a different patch generation (D3).

## Dead code, leftovers, stale comments

- L1: `scripts/__pycache__/aoa_probe.cpython-314.pyc`, Python cache in the repo tree (gitignored, untracked).
- L2: Repo-root `btapp.db.galaxy`, `btapp.db.galaxy2`, `btapp.bk.galaxy`, `btapp.bk.galaxy2` — 4 duplicate 207-byte DBs outside `dongle-backup/`, all gitignored by `.gitignore:48-49`, overlapping the `dongle-backup/` copies with different hashes for the `galaxy` name.
- L3: `openauto-plan.md:282-449` — Pi armv7 build plan (`Step 0` cleanup, `apt-get` list, `cmake`, `Step 6` WPP fallbacks). Superseded: README.md:95-97 and RUNBOOK.md:253-277 make macOS primary.
- L4: `openauto-plan.md:466-477` — "Open questions / risks" (RtAudio default device, offscreen Qt decode, 22 s re-enumeration) all resolved or obsolete after the macOS port.
- L5: README.md:275-312 — "Minimal app (`capture/`)" section describing a stack README.md:306-312 itself calls "not the current working stack".
- L6: `scripts/aoa_probe.py:10` `start` mode and `scripts/aoa_read.py` are unreferenced by any script; `README.md:373-374` lists them as standalone tools.
- L7: `patches/openauto-auriga-usb-filter.patch` has no `index` lines and depends on `aurigaCaptureMode()` introduced by `patches/openauto-macos.patch:18-26`; applied alone it does not compile. `patches/openauto-macos.patch` and `patches/openauto-auriga-usb-filter.patch` both rewrite `src/autoapp/App.cpp`; `patches/openauto-capture.patch` and `patches/openauto-auriga-gps-guard.patch` both rewrite `SensorService.cpp`. Order is undocumented.
- L8: `openauto/src/autoapp/App.cpp:238-239` (`//acceptor_.close();`) and `:216` (`// startServerSocket()` commented alternatives) — upstream leftovers kept in the patched tree.

## Improvement areas

- I1: No code validates dongle config files. `videoInfo` is touched only by hand MTP commands; a 20-line checker (magic `03 07 24 20`, width==1280, height==720, SPS start code at `0x12`, PPS at `0x27`, non-zero phone address at `0x54`) would have caught B1 and D2 before any upload. Mechanism: every current safeguard is prose in a README.
- I2: Replace per-file MTP surgery with one reversible operation set: capture the full 8-slot file list + hashes before a change, and keep it versioned. Mechanism: dongle-backup/README.md:107-110 already warns that MTP IDs are dynamic and the dongle has 8 slots, yet no snapshot of the full slot list exists.
- I3: Gate the AOA switch and the enumerator on the same filter. Mechanism: pass `2717:ff40` into `ConnectedAccessoriesEnumerator` (or delete it) instead of hiding it behind `AURIGA_CAPTURE_DIR`; today B4 depends on an env var.
- I4: Log the USB topology at startup ("no dongle: 2717:ff40 absent; present: 18d1:2d01, 04e8:6860"). Mechanism: `handleDevice` returns silently for unmatched descriptors (aasdk-upstream/src/USB/USBHub.cpp:113-117), so `Waiting for device...` never says why it is waiting.
- I5: Remove the fixed 1 s `std::this_thread::sleep_for` inside `USBHub::handleDevice` (aasdk-upstream/src/USB/USBHub.cpp:151-154). It runs inside a strand dispatch, blocking one of the 4 io_service threads for a full second on every AOA attempt; the VMware workaround has no business in a dongle-only filter path.
- I6: The 22 s re-enumeration is the de-facto device-discovery watchdog; nothing measures it. `scripts/aoa_probe.py` could log arrival timestamps (it already loops every 0.25 s at `:90`) and turn X4 into a testable fact instead of a 2026-10-28 anecdote.
- I7: Put the two unpatched aasdk edits into `patches/` (D6) so `patches/` really is the source of truth; otherwise a clean clone builds aasdk 1.6 and the dongle's 1.7 negotiation path is untested.
- I8: `btapp.db` state is the single most fragile dongle fact and it is untracked, stale-prone and has no checksum to verify (X9). Keep a current-pairing record plus an explicit "recovery = delete DB + replug + re-pair" runbook step (already RUNBOOK.md:162-182) and stop presenting local 207-byte files as restore candidates (D7).

## Interfaces

- Exposes: USB identity `2717:ff40` (MTP) → `18d1:2d00` (AOA v2, 2 bulk endpoints); AOA identity strings from the host; MTP root with 8 slots: `videoInfo` (364 B AA video + address + name + tag), `btapp.db`/`btapp.bk` (207 B or 33 B BT pairing DB), `ly_linktype_aa` (`0x01`), `bt.mac` (`EDA2A4944FB8`), `ly-AutoLink-A512` (`OPPO A72` cache), `carplay.key` (1433 B, no backup), `800x480-A512.h264` (missing); BT Classic `AutoLink-A512` `ED:A2:A4:94:4F:B8` class `0x200420` HFP; Wi-Fi AP `AutoLink-A512` BSSID `e8:5c:b1:b5:c6:41` 5180 MHz WPA2 `12345678`; AA protocol 1.7 (`256.1792`); AA-layer relay that passes the head unit's `display_name` and service set to the phone.
- Consumes: an AOA switch from the host (GET_PROTOCOL, 6× SEND_STRING, ACCESSORY_START — aasdk-upstream/src/USB/AccessoryModeQueryFactory.cpp:44-66), an AA 1.7 version request (`AASDK_MINOR` 7), AA service discovery + channel opens, phone BT pairing (6-digit numeric comparison) and Wi-Fi association, and a physical replug for cold boot. Consumes nothing from other aspects at the hardware level; the stream/UI aspects consume its capture output, not the dongle directly.
- Threading: the AOA switch executes on `aasdk::usb::USBHub::strand_` (aasdk-upstream/src/USB/USBHub.cpp:42-56); libusb hotplug events arrive on libusb's own thread and are re-dispatched onto that strand (:80-90). `autoapp` runs 4 libusb event threads plus 4 `io_service.run()` threads (openauto/src/autoapp/autoapp.cpp:56-75), so per-device ordering is strand-provided, not thread-provided. The 1 s sleep at aasdk-upstream/src/USB/USBHub.cpp:151-154 runs inside the strand, i.e. on one of the 4 io_service threads. `scripts/aoa_probe.py`/`aoa_read.py` are single-threaded sync libusb and must not run concurrently with `autoapp` (two owners of the device handle).

## Open questions for the user

- Q1: Does the dongle write width/height/SPS/PPS into `videoInfo` only after a completed AA video setup? A post-projection snapshot of `videoInfo` would settle whether `dongle-backup/videoInfo.galaxy` is a valid restore source (B1/A1) or a mid-flight file.
- Q2: What do `0x0c` (0 vs 2) and `0x50` (2 vs 4) select in `videoInfo`? No snapshot pairs a known session state with those values.
- Q3: Was the ~22 s MTP re-enumeration observed again after the 2026-10-28 BT DB reset, or is it a pre-reset artifact?
- Q4: Has the dongle ever been seen at `18d1:2d00` from anything other than the AOA switch performed by this host? If not, is rejecting only `18d1:2d01` acceptable (A5)?
- Q5: Is `05ac:12a8` (CarPlay) reachable without an iPhone on the air? The answer decides whether the software dead end in B3 needs code, not just a runbook note.
- Q6: Was the 207-byte duplicate-Galaxy DB ever restored and verified working after the reset, or is the 33-byte DB the only form that has ever projected?
