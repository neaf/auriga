# AARE fork (certificate rotation)

**Status: bench tool, not the car path.** AARE renders through Android's
compositor, so it needs the phone screen on; see
[`Phone-side app.md`](Phone-side%20app.md) for the measured result and what a
custom app would reuse from AARE instead.

A locally built AARE with one change: a head unit reached over a **Bluetooth
bond** may rotate its TLS certificate. Stock AARE pins the first one and refuses
any other, which on the AutoLink A512 means every other connection is rejected
as `head unit certificate changed`.

## Why

The A512 presents one of two leaf certificates on the wireless path:

| SHA-256 (prefix) | Seen |
| --- | --- |
| `4e75e8b3f73ae438…` | before and after some dongle resets |
| `1c0e0ef9e672dd1a…` | the other half of the connections |

Stock AARE keeps a `Set<String>` of fingerprints per head unit but only accepts
a new one when the set is **empty** (`trustOnFirstUse && trusted.isEmpty()`), so
with one pin the other certificate is refused, the Wi-Fi/AAP bootstrap restarts,
and the next attempt usually succeeds — a 20–40 s delay and sometimes an
`ECONNREFUSED` relay state instead of a connection.

## Patch

`docs/aare-cert-rotation.patch` against AARE `main` (`aap/…/PinStore.kt`):

- on a `trustOnFirstUse` peer (wireless, i.e. a bonded BT address), an unknown
  fingerprint is accepted and remembered instead of refused;
- `commit()` adds the fingerprint to the pin set if it is not already there.

USB accessory and developer-TCP head units keep strict pinning (`false`), so the
change only affects head units already authenticated by the Bluetooth bond.

## Build

AARE's release workflow signs with a key from the environment; locally, sign
with `daxter-certs/aare-fork.keystore` (password in `daxter-certs/README.md`).

```bash
git clone https://github.com/prototux/AARE /tmp/aare
cd /tmp/aare && git apply /path/to/auriga/docs/aare-cert-rotation.patch
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export AARE_KEYSTORE=/path/to/auriga/daxter-certs/aare-fork.keystore
export AARE_KEYSTORE_PASSWORD=… AARE_KEY_ALIAS=aare AARE_KEY_PASSWORD=…
./gradlew :app:assembleRelease -x lint -PversionName=1.1.1-fork -PversionCode=10102
```

The built APK is kept locally as `artifacts/aare-1.1.1-fork.apk` (gitignored).

## Install on a fresh phone

The fork is signed with a different key than the upstream APK, so it cannot be
installed over it: uninstall `net.prototux.aare` first. Uninstalling also drops
the imported phone certificate, permissions and pins.

```bash
adb uninstall net.prototux.aare
adb install -r artifacts/aare-1.1.1-fork.apk
P=net.prototux.aare
for perm in BLUETOOTH_CONNECT BLUETOOTH_SCAN ACCESS_FINE_LOCATION \
  ACCESS_COARSE_LOCATION POST_NOTIFICATIONS RECORD_AUDIO READ_CONTACTS \
  READ_CALENDAR READ_PHONE_STATE READ_CALL_LOG CALL_PHONE ANSWER_PHONE_CALLS \
  NEARBY_WIFI_DEVICES ACCESS_LOCAL_NETWORK; do
  adb shell pm grant $P android.permission.$perm
done
adb shell cmd notification allow_listener $P/.notify.CarNotificationListener
adb shell cmd deviceidle whitelist +$P
adb shell cmd appops set $P RUN_IN_BACKGROUND allow
adb shell cmd appops set $P WAKE_LOCK allow
adb shell am set-standby-bucket $P active
```

Then, in the app:

1. **Advanced → Phone certificates → Import certificate…**, pick
   `aare-phone.p12` (password `aare`), and delete the copy from
   `/sdcard/Download` afterwards.
2. **Connection**: Wireless on, car GPS off (unless mock location is set up),
   720p, 60 fps off.
3. Connect once; the first attempt offers the generated certificate and is
   rejected, the next one uses `aare-phone.p12`. Both dongle fingerprints are
   pinned automatically (`trusted head unit certificate for …` in the log).

## Phone settings that matter

- `settings put system screen_off_timeout 2147483647` and
  `settings put global stay_on_while_plugged_in 15`: with the screen off AARE
  stops producing frames and the car screen freezes.
- AARE only encodes when the car UI changes, so a static map looks frozen while
  `video.h264` is not growing; a tap produces new frames.
