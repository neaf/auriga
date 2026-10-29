# AutoLink A512 dongle

The AutoLink A512 (`smartlinkBox`) is the USB device between the phone and
`autoapp`. It presents a small MTP config store and, after the host sends the
AOA accessory chain, re-enumerates as an Android Open Accessory device carrying
the AA session. It relays AA service discovery, so the phone sees the head
unit's identity (`unverified`; no capture in the repo shows the relay path
directly).

## USB identity

| State | VID:PID | Host view | Handling |
| --- | --- | --- | --- |
| MTP, idle before the switch | `2717:ff40` | Xiaomi MTP, product `AutoLink` | The only device sent the AOA chain (`openauto/src/autoapp/autoapp.cpp:245-246`) |
| AOA after the switch | `18d1:2d00` | Google AOA | Claimed as the head-unit target (`aasdk-upstream/src/USB/USBHub.cpp:84-87`) |
| AOA+ADB, a phone | `18d1:2d01` | Google AOA with ADB | Refused when a source filter is set (`aasdk-upstream/src/USB/USBHub.cpp:121-127`) |
| MTP+ADB, the phone | `04e8:6860` | Samsung MTP+ADB | Never touched: neither the source filter nor AOA (`USBHub.cpp:115`) |
| CarPlay | `05ac:12a8` | Apple | Neither matched, ignored without a log (`USBHub.cpp:89-96,115`) |

`2717` is the Xiaomi vendor ID that the dongle reuses; it is not a dongle
property (`tools/aoa_probe.py`, `VID`). The IDs are observed on this host with
`ioreg`; no vendor datasheet is in the repo, so they are `unverified` as vendor
facts beyond observation.

Only `18d1:2d01` is refused among AOA devices. Any device that enumerates as
`18d1:2d00` is claimed regardless of vendor (`USBHub.cpp:84-87`).

## AOA switch

| Step | bmRequestType | bRequest | Data |
| --- | --- | --- | --- |
| `GET_PROTOCOL` | `0xC0`, vendor IN | 51 | 2-byte AOA version |
| `SEND_STRING` x6 | `0x40`, vendor OUT | 52 | string index (wValue) + UTF-8 + NUL |
| `ACCESSORY_START` | `0x40`, vendor OUT | 53 | none |

String indices, in the order the chain sends them:

| Index | Field | Value |
| ---: | --- | --- |
| 0 | manufacturer | `Android` |
| 1 | model | `Android Auto` |
| 2 | description | `Android Auto` |
| 3 | version | `2.0.1` |
| 4 | URI | `https://f1xstudio.com` |
| 5 | serial | `HU-AAAAAA001` |

Source: `aasdk-upstream/src/USB/AccessoryModeQueryChain.cpp:51-178`,
`aasdk-upstream/src/USB/AccessoryModeQueryFactory.cpp:35-64`; request numbers in
`AccessoryModeProtocolVersionQuery.hpp:40`, `AccessoryModeSendStringQuery.hpp:41`,
`AccessoryModeStartQuery.hpp:37`; string indices in
`AccessoryModeSendStringType.hpp:28-34`.

The host accepts AOA version 1 or 2
(`AccessoryModeProtocolVersionQuery.cpp:59`). The dongle reports version 2
(`[2,0]`) per the operating notes; `unverified`, because no probe output is
stored.

`tools/aoa_probe.py` is a standalone diagnostic with a different string set
(`Auriga`, `Auriga Pi Headunit`, `Auriga AA capture`, `1.0`,
`https://auriga.invalid`, `auriga-pi`). Its `start` mode sends
`ACCESSORY_START` to whatever device matches `2717:ff40` and must not run while
`autoapp` owns the dongle. `tools/aoa_read.py` reads the AOA bulk-IN endpoint.

## AOA transport

Two bulk endpoints, IN `0x81` and OUT `0x02`, 512-byte packets. `unverified`
(doc-derived): aasdk assumes exactly two endpoints and picks IN/OUT by the
endpoint-address bit (`aasdk-upstream/src/USB/AOAPDevice.cpp`);
`tools/aoa_read.py` reads 512-byte chunks.

## AA protocol version

The session negotiates AA 1.7, logged as `Version Received: 256.1792`
(`logs/openauto-mac-*.log`). aasdk advertises major 1, minor 7
(`aasdk-upstream/include/aasdk/Version.hpp`, `AASDK_MAJOR`/`AASDK_MINOR`). The
minor bump is `patches/aasdk-version-absl.patch`; the same patch adds the absl
include path to `aap_protobuf` (`docs/Build.md#aasdk`).

## MTP config store

Flat files with dynamic MTP IDs; `btapp.bk` is absent on the dongle today, so
seven slots are populated.

| File | Size | Current value | Backup |
| --- | ---: | --- | --- |
| `videoInfo` | 364 B | video config + phone address + head-unit name + session tag | `dongle-backup/videoInfo.orig`, `videoInfo.car-trip`; `videoInfo.galaxy` is invalid |
| `btapp.db` | 207 B or 33 B | Bluetooth link keys | `dongle-backup/btapp.db.galaxy-fresh` (33 B) |
| `btapp.bk` | absent | backup DB, not recreated | none |
| `ly_linktype_aa` | 1 B | `0x01` = AA mode | tracked |
| `bt.mac` | 12 B | `EDA2A4944FB8` | `dongle-backup/bt.mac.txt` |
| `ly-AutoLink-A512` | 8 B | name cache `OPPO A72`, no NUL | tracked |
| `carplay.key` | 1433 B | CarPlay key | none; do not delete |
| `800x480-A512.h264` | 34,134 B | AA splash | missing, cannot be restored exactly |

Config writes are manual MTP operations only (`mtp-files`, `mtp-getfile`,
`mtp-delfile`, `mtp-sendfile`); no code writes them. `mtp-sendfile` uses the
local basename as the remote name, so stage files under the exact remote name.
Delete or upload one file at a time and re-list the slots afterwards. Sizes for
the on-dongle files are the ones in the table above (measured from the backups;
`mtp-files` lists the live slots); `carplay.key` (1433 B) and
`800x480-A512.h264` (34,134 B) are `unverified`, because neither is in the repo.

### MTP procedure

```bash
# list the slots (IDs are dynamic; always match by filename)
sudo mtp-files

# replace one file: stage it under the exact remote name first
mkdir -p /tmp/restore
cp dongle-backup/videoInfo.orig /tmp/restore/videoInfo
sudo mtp-delfile -f videoInfo
cd /tmp/restore && sudo mtp-sendfile videoInfo videoInfo

# verify by downloading it again
sudo mtp-getfile <file-id> /tmp/check && sudo cmp /tmp/restore/videoInfo /tmp/check
```

Restore only `videoInfo.orig` or `videoInfo.car-trip`; the `videoInfo.galaxy`
snapshots are invalid. The current Bluetooth pairing DB is
`dongle-backup/btapp.db.galaxy-fresh` (33 B); the 207-byte DBs hold stale link
keys.

### `videoInfo` layout

364 bytes, little-endian, verified by byte inspection of the snapshots in
`dongle-backup/`.

| Offset | Type | Value | Meaning |
| ---: | --- | --- | --- |
| `0x00` | 4 bytes | `03 07 24 20` | magic |
| `0x04` | u32 | 1280; 0 in `videoInfo.galaxy` | width |
| `0x08` | u32 | 720; 0 in `videoInfo.galaxy` | height |
| `0x0c` | u32 | 0 (`orig`, `galaxy`), 2 (`car-trip`) | unknown, `unverified` |
| `0x10` | 2 bytes | `15 08` = `0x0815` (`orig`, `car-trip`), 0 (`galaxy`) | unknown, `unverified`; the Annex-B start code follows immediately at `0x12` |
| `0x12` | 4 bytes | `00 00 00 01`; absent in `galaxy` | Annex-B start code |
| `0x16` | 17 bytes | `67 42 80 20 da 01 40 16 e9 48 28 30 30 36 85 09 a8` | SPS, Baseline 3.2 (profile `0x42`, constraint `0x80`, level `0x20`) |
| `0x27` | 4 bytes | `00 00 00 01`; absent in `galaxy` | Annex-B start code |
| `0x2b` | 4 bytes | `68 ce 06 e2` (`car-trip`: `68 ce 06 f2`) | PPS |
| `0x50` | u32 | 2 (`orig`, `car-trip`), 4 (`galaxy`) | unknown, `unverified` |
| `0x54` | 17 ASCII + NUL | e.g. `5C:D3:3D:56:71:F4` | phone Bluetooth address, uppercase colon form |
| `0x68` | 10 bytes | `auriga-pi\0`, `T  M918500` | head-unit name, fixed width, no NUL when full |
| `0x72` | 8 bytes | `1493 _0\0`; zero in `galaxy` | session tag |
| `0x168` | u32 | `4e2d347c` (`orig`), `5e205bfd` (`car-trip`), `576e7e45` (`galaxy`) | unknown, `unverified` |

`videoInfo.car-trip` differs from `videoInfo.orig` in 4 SPS bytes
(`0x1e..0x21`), the PPS level byte at `0x2e`, the `0x0c` field, the 10-byte
head-unit name (`0x68..0x71`) and the u32 at `0x168`. It records a real car head
unit (`T  M918500`), not the bench config.

### Backup inventory

| File | Size | Status |
| --- | ---: | --- |
| `dongle-backup/videoInfo.orig` | 364 B | valid bench config: OPPO address, `auriga-pi`, Baseline 3.2 SPS/PPS |
| `dongle-backup/videoInfo.car-trip` | 364 B | valid car-trip snapshot (the former `posttrip/videoInfo.post` duplicate is deleted with `posttrip/`) |
| `dongle-backup/videoInfo.galaxy` | 364 B | invalid: `0x04` and `0x08` are 0, `0x12..0x4f` are 0 (no start codes, no SPS, no PPS), `0x72..0x79` are 0. Do not restore |
| `dongle-backup/videoInfo.galaxy.active` | 364 B | byte-identical to `videoInfo.galaxy`, so also invalid |
| `dongle-backup/btapp.db.galaxy-fresh` | 33 B | current pairing DB; sha256 `f6b4b7e6…`; current but `unverified` |
| `dongle-backup/btapp.db.orig`, `btapp.bk.orig` | 207 B | original Galaxy + OPPO records; sha256 `4023b49d…`; stale |
| `dongle-backup/btapp.db.galaxy`, `btapp.bk.galaxy` | 207 B | duplicate-Galaxy DB; sha256 `d021cf83…`; link keys do not match the current pairing |
| `dongle-backup/bt.mac.txt` | 13 B | `EDA2A4944FB8` plus newline |
| `dongle-backup/ly_linktype_aa` | 1 B | `0x01` |
| `dongle-backup/ly-AutoLink-A512.orig` | 8 B | `OPPO A72`, no NUL |

The `*.db`/`*.bk` files are gitignored and untracked, so a fresh clone has no
pairing DB. `btapp.db.galaxy-fresh` is the only backup of the current link key;
a later re-pair silently invalidates it and nothing detects that.

### `btapp.db` layout

| Form | Bytes | Structure |
| --- | ---: | --- |
| two records | 207 | 8-byte prefix `02 01` + 6-byte address stored reversed; seven `13 00 01 04` + 16-byte link-key blocks starting every 29 bytes (`0x08, 0x25, 0x42, 0x5f, 0x7c, 0x99, 0xb6`); trailer `00 42 54 4c f3` |
| one record | 33 | 8-byte prefix; one `13 00 01 04` + 16-byte link key; trailer `00 42 54 0a 53` |

`btapp.db.orig` holds two records: `02 01` at `0x00` and `0x3a`; the Galaxy
address `f4 71 56 3d d3 5c` (`5C:D3:3D:56:71:F4`) sits at `0x02`, the OPPO
address `1a 20 4c 2d 47 14` at `0x3c`. `btapp.db.galaxy-fresh` is the one-record
form the dongle wrote after the 2026-10-28 re-pair, 33 B.

The trailer is not a CRC-16 of the body under nine common variants (CCITT-FALSE,
XMODEM, KERMIT, X25, MODBUS, IBM, ARC, AUG-CCITT, GENIBUS, both endiannesses),
so a hand-patched body is not rejected as corrupt; the failure mode is semantic
(the dongle stops advertising).

Whether the 33-byte form is a complete replacement for the 207-byte form (it
carries one link key, not two) is `unverified`.

## Recovery

### Bluetooth advertising stops

Symptom: `AutoLink-A512` is not visible to the phone; the Wi-Fi AP still works.
Cause: `btapp.db` holds duplicate or stale records. A hand-patched body passes
the trailer check, so the failure is semantic, not checksum-detected.
Workaround: delete `btapp.db` and `btapp.bk` over MTP, cold boot
(unplug/replug), re-pair with the 6-digit numeric comparison. The dongle
recreates a 33-byte `btapp.db`; `btapp.bk` is not recreated.
Location: MTP operations only; see `### MTP procedure` above.

### Stuck in AOA with a stale TLS session

Symptom: `autoapp` logs `Waiting for device...` while the dongle stays
`18d1:2d00`; no AA session starts.
Cause: a stale TLS session on the dongle; a `libusb` reset does not return it to
MTP (`unverified`).
Workaround: physical unplug/replug with the phone's BT/Wi-Fi on. `uhubctl` port
power switching may cut only the data port, not VBUS (`unverified`). Ask before
replugging; it interrupts any live session.
Location: host side `openauto/src/autoapp/App.cpp:175-186`.

### CarPlay latch

Symptom: the dongle never appears as `2717:ff40`; `autoapp` waits forever and
nothing logs the mode.
Cause: the dongle latches to `05ac:12a8` when an iPhone is on the air; the
source filter matches only `2717:ff40` and `isAOAPDevice` matches only `18d1`,
so `handleDevice` returns without logging (`USBHub.cpp:100-117`).
Workaround: replug with the iPhone off. No software path recovers it.
Location: `patches/aasdk-usb-filter.patch`, `USBHub.cpp:89-96`.
Whether the latch is reachable without an iPhone is `unverified`.

### Idle re-enumeration

Symptom: a cold `autoapp` can start between arrivals and wait at
`Waiting for device...`.
Cause: while idle in MTP the dongle re-enumerates roughly every 22.0 s; this is
the de-facto discovery watchdog (`tools/aoa_probe.py`, module docstring).
Workaround: leave `autoapp` running; it catches the next arrival.
Location: `tools/aoa_probe.py` polls every 0.25 s. The interval was measured
on 2026-10-28 and not re-measured after the BT DB reset: `unverified`.

## Bluetooth and Wi-Fi identity

| Interface | Value | Source |
| --- | --- | --- |
| BT Classic name | `AutoLink-A512` | operating notes; `unverified` |
| BT address | `ED:A2:A4:94:4F:B8` | `dongle-backup/bt.mac.txt` |
| BT class | `0x200420`, HFP | operating notes; `unverified` |
| Wi-Fi AP | `AutoLink-A512`, 5 GHz, channel 36 (5180 MHz), WPA2-PSK `12345678` | operating notes; `unverified` |
| Wi-Fi BSSID | `e8:5c:b1:b5:c6:41` | operating notes; `unverified` |

The dongle LED is not an AA-link indicator: it is lit or blinking in MTP and
dark in AOA (`unverified`).

## Validation gap

Symptom: an invalid `videoInfo` upload is accepted and only fails later at video
setup.
Cause: nothing validates the file; every safeguard is prose in a README.
Workaround: check magic `03 07 24 20`, width 1280 at `0x04`, height 720 at
`0x08`, a start code at `0x12`, PPS at `0x27` and a non-zero phone address at
`0x54` before uploading. The checks are the procedure; nothing in the repo runs
them.
