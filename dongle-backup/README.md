# Dongle config backups

These are **MTP config files**, not firmware. The dongle is an AutoLink
wireless AA/CarPlay adapter (`smartlinkBox`, MTP `2717:ff40`).

Current active config (2026-10-28):

| File | Current active value | Local backup |
| --- | --- | --- |
| `videoInfo` | Galaxy address `5C:D3:3D:56:71:F4` + `auriga-pi` | none valid: `videoInfo.galaxy` is invalid, see below |
| `btapp.db` | fresh **33-byte** DB, one Galaxy record with the new link key (recreated after re-pair) | `btapp.db.galaxy-fresh` |
| `btapp.bk` | **missing** (dongle did not recreate it) | none |
| `ly_linktype_aa` | `0x01` (AA mode) | `ly_linktype_aa` |
| `ly-AutoLink-A512` | still `OPPO A72` (name cache) | `ly-AutoLink-A512.orig` |
| `bt.mac` | `EDA2A4944FB8` | `bt.mac.txt` |
| `800x480-A512.h264` | **missing** (34,134-byte AA splash) | none (not backed up) |
| `carplay.key` | present on dongle | none (not backed up) |

`videoInfo` files:

- `videoInfo.orig` — original bench config: OPPO `14:47:2D:4C:20:1A` + `auriga-pi`.
- `videoInfo.car-trip` — snapshot written by the real car trip: OPPO address +
  car head-unit name (`T  M91850...`), same 1280x720 SPS/PPS.
- `videoInfo.galaxy` — **invalid** snapshot (2026-10-28): width/height at
  `0x04`/`0x08`, the start codes/SPS/PPS at `0x12..0x4f` and the session tag at
  `0x72` are all zero. It also carries the Galaxy address and `auriga-pi`. Do
  not restore it.
- `videoInfo.galaxy.active` — byte-identical duplicate of the invalid snapshot.

`btapp.db` files:

- `btapp.db.orig` — original: Galaxy record first, OPPO record second.
- `btapp.bk.orig` — original backup (identical to `btapp.db.orig`).
- `btapp.db.galaxy` / `btapp.bk.galaxy` — historical 207-byte patch: two Galaxy
  addresses, zero OPPO, and the old Galaxy link keys in both records:
  - `ed4528010fa1e8514c7b33e3ff43beff`
  - `901226b5aba81300010435811ac9c286`
- `btapp.db.galaxy2` / `btapp.bk.galaxy2` — the later 207-byte duplicate-Galaxy
  patch that was active before the 2026-10-28 reset. Historical/stale.
- `btapp.db.galaxy-fresh` — current 33-byte DB recreated by the dongle after the
  fresh pairing. This is the one to restore for the current phone pairing.

The patch changed the 6-byte OPPO address and the 32 key bytes in the second
record; file size remains 207 bytes. This is what made the dongle target the
Galaxy instead of the powered-off OPPO.

**2026-10-28 reset:** BT advertising stopped while the 207-byte duplicate-Galaxy
DB was active. Both `btapp.db` and `btapp.bk` were deleted via MTP (no
replacement uploaded). The dongle then re-advertised `AutoLink-A512`, the
Galaxy paired with a 6-digit numeric-comparison code, and the dongle recreated a
**33-byte** `btapp.db` (one Galaxy record, new link key). `btapp.bk` was not
recreated.

- `btapp.db.galaxy-fresh` — current active DB backup, 33 bytes, sha256
  `f6b4b7e62e4ddddb2569cacda911baa98bef639ba270c2938522cef1abcaabe7`.
- `active-btapp.db` (on the Pi in `/tmp/auriga-db/`) — copy of the 207-byte DB
  that was active before deletion, sha256 `d021cf83...`.
- The 207-byte `galaxy`/`galaxy2` files are historical. Their link keys are
  stale after the re-pair; do not restore them unless intentionally reverting
  to the old pairing.

## Restore commands (MTP)

`mtp-sendfile` uses the **local basename** as the remote filename in this
environment, so stage files under their exact remote names.

> For the current phone pairing (after 2026-10-28), restore
> `btapp.db.galaxy-fresh` as `btapp.db`. Do **not** restore the 207-byte
> `.galaxy`/`.galaxy2` DBs: their link keys are stale after the re-pair.
> `btapp.bk` is currently absent; the dongle has not recreated it.

```bash
# Example: restore the original videoInfo (OPPO/auriga-pi)
mkdir -p /tmp/restore
cp dongle-backup/videoInfo.orig /tmp/restore/videoInfo
sudo mtp-delfile -f videoInfo
cd /tmp/restore
sudo mtp-sendfile videoInfo videoInfo

# Example: restore the original Bluetooth DB (Galaxy + OPPO)
mkdir -p /tmp/restore
cp dongle-backup/btapp.db.orig /tmp/restore/btapp.db
cp dongle-backup/btapp.bk.orig /tmp/restore/btapp.bk
sudo mtp-delfile -f btapp.db
sudo mtp-delfile -f btapp.bk
cd /tmp/restore
sudo mtp-sendfile btapp.db btapp.db
sudo mtp-sendfile btapp.bk btapp.bk

# Example: restore the current 33-byte fresh DB (one Galaxy record)
mkdir -p /tmp/restore
cp dongle-backup/btapp.db.galaxy-fresh /tmp/restore/btapp.db
sudo mtp-delfile -f btapp.db
cd /tmp/restore
sudo mtp-sendfile btapp.db btapp.db
```

After any restore:

```bash
sudo mtp-files | grep -E -B1 -A3 'Filename: (videoInfo|btapp)'
# download the file(s) and cmp against the local copy
sudo mtp-getfile <file-id> /tmp/check
sudo cmp /tmp/restore/videoInfo /tmp/check
```

MTP file IDs are **dynamic**; always list by filename, not a remembered ID.
The dongle has 8 file slots; delete/upload one file at a time and verify the
8-file list afterward. `mtp-sendfile` may create a file under the local
basename; stage names exactly.

## Warnings

- Do **not** restore the OPPO config unless you intentionally want the dongle to
  target the OPPO again. The active Galaxy DB is the fix for the AA pairing
  request.
- The `800x480-A512.h264` splash cannot be restored exactly; there is no backup.
  The real car trip worked without it, so it is not boot-critical. A generated
  800x480 H.264 placeholder exists locally (`/tmp/auriga-splash/` on the Mac)
  but must not be uploaded without approval.
- `carplay.key` is not backed up; do not delete it.
- `uhubctl` port power switching may only disable the data port, not VBUS. Use a
  physical replug for a true cold boot.
- No firmware images or flashing tools are in this directory.
