# Phone-side AA mega app + Pi car server — findings and plan

**Status: design note (2026-10-29). Nothing here is implemented yet.**
This branch is separate from the working OpenAuto capture stack. It records the
architecture we arrived at after the macOS/OpenAuto work: a phone-side Android
Auto implementation that renders a fully custom UI, plus a Raspberry Pi in the
car for CAN and Spotify.

## Context from the existing stack

- OpenAuto + aasdk 1.7 is a working AA **head unit** on the Pi and the Mac; it
  completes AA 1.7, TLS, service discovery and captures video/audio/input.
- The AutoLink dongle is a working AA **relay**: the real-car trip proves its
  car side, and the phone sees the head unit's display name and service set.
- The missing half is the AA **phone**. Replacing the phone's system AA stack is
  what lets the car display a custom UI instead of Android Auto's templates.
- AARE and mretallack/AndroidAuto show the phone half is feasible in open
  source; AARE additionally implements wireless BT/WPP and dongle quirks.
- The main unknown is not the protocol but the dongle's phone-certificate
  policy. Test that before committing to the app.

## Decision in one page

- **Keep the AutoLink dongle as the car-side AA bridge.** It already implements
  the USB AOA phone identity and the car side that works with the real car.
- **The phone is the AA phone.** The app implements the phone half of AA and
  renders the final UI itself: custom map, Spotify, status bar, gauges. The car
  sees one H.264 video stream, not Android Auto's UI.
- **Use AARE as the base, not a from-scratch app.** Its `aap/` protocol stack,
  wireless bootstrap, `ProjectionDisplay`, `VideoEncoder`, `CarSession`,
  `TouchMapper` and audio routing are the plumbing. Replace AARE's car shell
  with the custom map/mega UI.
- **The Pi is a car server, not the AA renderer.** It reads CAN/OBD-II, exposes
  vehicle data to the phone, runs librespot/Spotify Connect, logs, and manages
  power. It talks to the phone over USB; it does not sit in the AA video path.
- **Spotify:** the clean path with the Pi is librespot on the Pi -> PCM over USB
  -> phone app -> AA media channel. Phone-only fallbacks are Shizuku, Bluetooth
  A2DP, or MediaProjection capture, in that order.
- **First go/no-go:** does the dongle accept AARE's phone-side TLS certificate?
  Test that before building the mega app.

## Why not put the Pi4 in place of the dongle

A Pi4 that replaces the dongle has to implement **both** AA sides:

1. AA head unit to the phone: BT RFCOMM/WPP, Wi-Fi AP, TCP, AA service set.
2. AA phone to the car: USB AOA gadget, AA version, TLS phone certificate the
   car accepts, plus video/audio forwarding or compositing.

The dongle already does both and is proven with the real car. A Pi4 replacement
is the bigger project and only makes sense if the Pi must render/composite the
AA video itself, run without the phone, or mix audio into the AA stream. For a
custom map UI that already runs on the phone, the Pi belongs beside the AA path,
not inside it.

## Topology

```
phone mega app (AARE fork: map + Spotify UI + AA phone)
        |
        | Wi-Fi: BT/WPP bootstrap, AA TCP/TLS, H.264 + PCM + input
        v
AutoLink A512 dongle (AA head unit to phone, AA phone to car)
        |
        | USB AOA
        v
car head unit

phone <--- USB-C: tether + CAN/telemetry + Spotify PCM + charging ---> Pi
                                                                        |
                                                                        | CAN/OBD-II
                                                                        v
                                                                   car bus
```

Two independent networks are in use:

- **Dongle Wi-Fi**: local-only AA link. Android must keep cellular as the
  internet path; AARE asks for a local-only `WifiNetworkSpecifier` and binds its
  AA sockets to that network.
- **USB tether**: phone shares internet with the Pi and gives the app a local
  TCP link to the Pi. The app must bind Pi traffic to the USB network and AA
  traffic to the dongle Wi-Fi explicitly; neither should rely on the default
  route.

## Phone-side AA

### Wire sequence

1. Pair the phone with `AutoLink-A512` over Bluetooth.
2. Connect RFCOMM to UUID `4de17a00-52cb-11e6-bdf4-0800200c9a66`.
3. WPP exchange: `WifiVersionRequest/Response`, `WifiStartRequest`,
   `WifiInfoRequest/Response`, connection status.
4. Join the dongle's AP with `WifiNetworkSpecifier`.
5. Connect TCP to the IP/port from `WifiStartRequest`.
6. AA framing, then TLS 1.2 with the **phone as TLS server** and mutual auth.
7. Version 1.7, service discovery, then open video/audio/input/sensor channels.
8. Send H.264 access units and PCM; receive touch/keys and sensor data.

AARE already implements this, including the dongle-specific WPP cases (a bare
`WifiStartRequest`, a dongle that hangs up after reading two frames, and
credential frames that arrive in either order).

### AARE pieces to keep

| Path | Use |
| --- | --- |
| `aap/` | Frame/TLS/session/channel protocol; pure Kotlin/JVM |
| `aap/.../wireless/` | `WPP`, `WirelessBootstrap` |
| `app/.../transport/wireless/` | `WirelessConnector`, `HeadUnitNetwork` |
| `app/.../video/` | `ProjectionDisplay`, `VideoEncoder` |
| `app/.../car/CarSession.kt` | AA callbacks, video/audio/input/sensor wiring |
| `app/.../car/TouchMapper.kt` | AA touch report -> `MotionEvent` |
| `app/.../audio/` | `CarAudioOut`, `PcmSources` |
| `app/.../aap/channels/` | `VideoChannel`, `AudioChannel`, `InputChannel`, `SensorChannel`, `BluetoothChannel` |

AARE's `host/` (Car App Library host), `ui/car` shell and most of `media/` are
not needed if the custom map UI is the whole car UI. Keep the media host only
if other Car App Library/media apps should still appear.

### Render path

AARE's `CarSession.startProjection()` creates the encoder and then:

```kotlin
display = ProjectionDisplay(context, w, h, dpi, enc.inputSurface) {
    Box(...) {
        runtime.Root(Modifier.padding(...))
    }
}
```

`ProjectionDisplay` creates a private `VirtualDisplay` with
`FLAG_PRESENTATION | FLAG_OWN_CONTENT_ONLY` and hosts a `Presentation` whose
`ComposeView` draws into the encoder input surface. This means:

- no `MediaProjection`, no screen-capture consent;
- no phone-screen mirroring; the phone screen can be off;
- the app renders only its own windows;
- the car's touches/keys are dispatched directly into the Presentation's view
  tree by `ProjectionDisplay.dispatchTouch()` / `dispatchKey()`;
- multi-touch is supported by `TouchMapper` and `MotionEvent` pointer actions.

Replace `runtime.Root(...)` with a `MegaRoot(...)` containing the map UI,
Spotify mini-player/full-screen route, status bar and gauges. Keep AARE's
padding calculation from the head unit's `VideoConfiguration`: resolution, fps,
density, width/height margins and `UiConfig.contentInsets`.

### Integrating the existing map app

- Best: extract the map UI into a library module exposing a `@Composable` or a
  `View`; host it inside `MegaRoot`. Same process, normal lifecycle and touch.
- `MapView`/`TextureView`-based rendering composes normally under Compose
  overlays.
- `SurfaceView`/GL rendering needs care: a `SurfaceView` is a separate layer and
  Compose overlays may not draw above it. Use a `TextureView`, render the map to
  an FBO/texture and composite overlays in the same GL context, or test the
  layer ordering on the virtual display.
- A separate `Activity` is possible via `ActivityView` or launching it on the
  virtual display, but input/lifecycle is more work. Refactoring to a `View` is
  the lower-risk route.
- Make the UI resolution-agnostic. Test 800x480, 1280x720, 1920x720, portrait,
  RHD and non-zero insets/margins.
- Handle `VideoFocus` (pause/resume, keyframe on return), night mode, driving
  status and `UPDATE_UI_CONFIG_REQUEST`.

### Audio split

- Map/nav TTS: generate PCM directly and send on the AA **guidance** channel.
  This keeps navigation voice independent of Spotify capture.
- Spotify: ideally PCM from the Pi (librespot) on the **media** channel.
- The car can then duck media for guidance. If everything is one mixed Shizuku
  stream, the car cannot separate or duck it.
- AARE's `CarAudioOut` handles focus requests, silence detection, underflow and
  the ack window; implement a custom `PcmSource` for the Pi PCM stream or the
  TTS queue.

## Certificate risk and test

AA uses mutual TLS with the **phone as TLS server** and the **head unit as TLS
client**. AARE presents a self-signed certificate by default. Google's Desktop
Head Unit and head units built on Google's receiver library check the phone
certificate against the Google Automotive Link CA and reject self-signed certs
with `AUTH_COMPLETE status -3` or a TLS abort. OpenAuto/Crankshaft, Headunit
Revived, LIVI, aa-proxy-rs and some OEM units accept AARE's certificate.

The AutoLink dongle is an AA-layer relay, not a dumb byte bridge; it may
terminate TLS on the phone side. That decides who checks the certificate:

| Dongle behavior | Who checks the phone cert | AARE self-signed |
| --- | --- | --- |
| Terminates TLS, lenient | dongle | likely works; car sees the dongle's cert |
| Terminates TLS, strict | dongle vs Google CA | fails with -3 / TLS abort |
| Passes TLS through | car | works only if the car is lenient |

### Test procedure

1. Build AARE debug and install it on the phone. Disable the system AA wireless
   connection to the dongle, or use a spare phone.
2. Pair with `AutoLink-A512`; start OpenAuto on the Mac with the dongle in MTP.
3. Connect AARE wirelessly to the dongle. Read AARE's connection log.
4. If it projects, watch for `TLS handshake did not complete` vs
   `head unit rejected authentication (status -3)`.
5. To distinguish "dongle terminates" from "dongle is transparent", log the TLS
   peer certificate OpenAuto receives. If it is AARE's distinctive certificate,
   TLS passes through; if it is a Google/dongle certificate, the dongle
   terminates TLS. This is a small instrumentation change in aasdk/OpenAuto.

If the dongle is strict:

- AARE supports importing a certificate you are entitled to use (PEM/PKCS#12).
- The official AA APK's `CarService` certificate/key is extractable; the
  `mretallack/AndroidAuto` project documents the chain and an extraction tool.
  That is Google's private key, likely violates AA's terms, and the known cert
  expires at the end of 2026. Do not ship it.
- A custom dongle/firmware where you control the cert policy is the alternative.
- Patching the AutoLink firmware is not a first move and conflicts with the
  repo's "no firmware flashing" rule.

## Spotify

### Why playback capture is fragile

`MediaProjection`/`AudioPlaybackCapture` only captures apps whose audio usage is
`MEDIA`/`GAME`/`UNKNOWN` and whose capture policy allows third-party capture.
Spotify's Java `AudioTrack` renderer has allowed capture, but its native
Oboe/AAudio renderer can set `ALLOW_CAPTURE_BY_SYSTEM`, which blocks ordinary
apps. Behavior has changed across Spotify versions. Do not build the product on
it.

Spotify also restricts its `MediaBrowserService` to whitelisted callers
(Android Auto, the Assistant), so AARE's media browser will not browse Spotify.
Plan on the Spotify App Remote SDK + Web API instead.

### Options

| Path | How it works | Cost / risk |
| --- | --- | --- |
| **Pi librespot** | Pi is a Spotify Connect device; PCM over USB to the phone; phone sends it on AA media | Unofficial client, ToS grey area, Premium; cleanest audio once running |
| **Shizuku** | Shell-rights `REMOTE_SUBMIX` records the whole phone output | Per-boot restart; no PC on Android 11+, but a ~20-30 s ritual |
| **Root / privileged** | `MODIFY_AUDIO_ROUTING`; AARE Magisk module | Root required; best media/guidance split; S25 root has Knox/banking costs |
| **MediaProjection capture** | `AudioPlaybackCapture` with one consent | Spotify may block; unreliable across versions |
| **Bluetooth A2DP** | Car plays Spotify over BT while AA carries video/nav | Zero capture, but car must mix BT audio with AA |
| **Official AA app** | Native Spotify AA UI | Not compatible with a custom AA phone app |

### Shizuku details

- Android 11+ can start Shizuku entirely on-device via Wireless debugging:
  enable Wireless debugging, open Shizuku, tap Start. Pairing is normally done
  once; re-pair with the 6-digit code if it is lost. No computer is required.
- Shizuku does **not** survive a reboot without root. The manual says the
  startup steps must be done again after each reboot.
- Shizuku 13.6+ has a trusted-Wi-Fi auto-start on Android 13+, but it is not
  reliable on Samsung/Android 16. Root is the only reliable auto-start.
- A dedicated rooted car phone (e.g. a Pixel with Magisk, AARE as a privileged
  app, its own data SIM) avoids the ritual and keeps the main phone clean.

### Spotify UI and control

- **App Remote SDK**: playback control, player state, metadata/artwork,
  recommended content. Playback stays in the Spotify app.
- **Web API**: search, playlists, albums, library, queue, playback control.
  App Remote's `ContentApi` has no search.
- **Premium** is required for on-demand track playback and Web API playback
  control.
- Build a Spotify screen in the mega app: home/recent, search, playlists, now
  playing, queue, transport; a mini-player overlay on the map. The car's
  steering-wheel keys can be mapped to transport commands.

### Pi librespot path

- Run `librespot` on the Pi as a Spotify Connect device, output PCM instead of
  using a local DAC.
- Stream 48 kHz/16-bit stereo PCM to the phone over USB TCP, with timestamps and
  an adaptive buffer for clock drift. Feed it into AARE's `PcmSource`.
- Control it through the Spotify Web API (transfer playback to the Pi device) or
  the official Spotify app if it can see the device.
- Device discovery across the USB-tether network may not work via local mDNS.
  Web API control is the reliable path; putting the Pi on the dongle AP as well
  requires a 5 GHz-capable Pi 4/5.
- The Pi needs internet; USB tether from the phone provides it. If the phone has
  no signal, librespot cannot stream.

## Pi car server

### Roles

- CAN/OBD-II gateway, signal decoding (DBC), logging, timestamps.
- Vehicle state for the phone UI: ignition, gear, RPM, speed, doors, lights,
  climate, steering-wheel buttons, night mode, etc.
- Spotify Connect/librespot playback -> PCM over USB.
- Power sequencing and safe shutdown; optional GPS/IMU/LTE.
- Always-on logging and OTA updates.

### Phone <-> Pi link

- Use USB tethering: the Pi is the USB host, the phone is the USB device and
  shares its cellular internet. The Pi gets a DHCP address; the phone app
  connects to it over the USB network.
- Bind the Pi sockets to the USB network and the AA sockets to the dongle
  Wi-Fi. Do not rely on the default route for either.
- Use a static IP on the Pi or mDNS/NSD for discovery.
- The Pi's USB port may not fast-charge the phone; use a powered hub or a
  separate charger. A USB-C hub can carry data and power.
- Alternative: put the Pi on the dongle's AP (requires 5 GHz; Pi 4/5) for
  same-LAN Spotify Connect discovery, with internet via USB tether. This gives
  the Pi two interfaces; keep the default route on USB.

### Hardware

- **Pi 4 (2-4 GB) or Pi 5** for librespot + CAN + USB host + 5 GHz Wi-Fi.
  Pi Zero 2 W is fine for CAN-only, but is 2.4 GHz-only and tight for
  librespot + USB host + power.
- **CAN**: USB-CAN (CANable 2.0, Innomaker, etc.) with SocketCAN is easiest;
  MCP2515 HAT for classic CAN, MCP2518FD for CAN-FD. Check bus speed and whether
  the signals are on OBD pins 6/14 or a separate body/comfort bus behind a
  gateway. The DBC is usually the real work.
- **Power**: 12 V -> 5 V automotive buck (9-36 V, 3-5 A), fuse, reverse-polarity
  protection, TVS/load-dump protection, ignition-sense GPIO, safe shutdown
  (supercap/UPS/power-management HAT). Read-only root/overlayfs and a
  high-endurance SD or SSD; dash power cuts corrupt normal SD cards.
- **Thermal**: a Pi 4 in a closed dash gets hot; heatsink/ventilation. Pi 5
  needs more careful thermal design.
- **Isolation**: use a proper CAN transceiver, preferably isolated; do not
  backfeed the bus.

### Software

- Raspberry Pi OS Lite 64-bit; `can-utils`, `python-can`, `cantools`, SocketCAN,
  DBC files; systemd services.
- Expose CAN data as protobuf/JSON over MQTT, WebSocket or a small TCP API;
  timestamp frames, batch/decimate for the UI, log raw frames locally.
- `librespot` for Spotify; a PCM server over USB TCP.
- OTA/read-only root, persistent logs, watchdog, NTP/RTC, VPN/SSH as needed.

### CAN safety

- Start read-only. Do not send frames until you know the bus, the DBC and the
  effect. Sending on powertrain/safety buses can be dangerous.
- Prefer a separate comfort/body bus for any control work; isolate the
  interface, fuse it and gate commands behind interlocks (parked, ignition,
  explicit confirmation).
- Test any actuation on a bench or with the wheels off the ground. Log
  everything and keep a replay path.

## Phone-only vs Pi4-in-the-AA-path

| | Phone + dongle + Pi companion | Pi4 replacing the dongle |
| --- | --- | --- |
| Custom video/nav | Phone renders; Pi supplies data | Pi renders/composites or forwards |
| Spotify | librespot on Pi -> PCM -> phone -> AA | librespot on Pi -> AA audio directly |
| Car-side identity | Dongle already proven | Must reproduce AOA gadget + phone cert |
| Effort | AARE fork + map integration + Pi server | Both AA sides + USB gadget + compositing |
| Heat/battery | Phone encodes; Pi handles CAN/Spotify | Pi does the heavy lifting |
| Always-on | Phone must be present | Pi can run without phone |
| Cert control | Dongle's phone-side policy | You control both sides |

The companion split is the lower-risk first version. The Pi4-in-path version is
only justified if the Pi must render/composite video or run the AA session
without the phone.

## Next experiments, in order

1. **Certificate test**: AARE + dongle + OpenAuto. Confirm the dongle accepts
   AARE's cert. If not, stop and decide the cert path before building UI.
2. **Spotify route test**: with the Pi, run librespot and stream PCM to a small
   phone test app, then into AARE's media channel. Compare with Shizuku and
   Bluetooth A2DP on the actual car.
3. **Map UI in `ProjectionDisplay`**: replace AARE's car shell with a test
   pattern, then the map library, at 800x480 and 1280x720, with touch and
   insets. Test on AARE's desktop head unit first.
4. **Phone <-> Pi link**: USB tether, bind sockets, static IP/mDNS, CAN data
   rate, PCM stability, reconnect behavior.
5. **CAN bring-up**: read-only OBD-II first; then the body/comfort bus and DBC.
6. **Car test, parked**: actual resolution/insets, touch, audio ducking, night
   mode, driving-status gate.

## Open questions

- What should CAN actually do: read-only telemetry/gauges, body/comfort control,
  or powertrain? OBD-II only, or direct bus with a DBC? Car model/year?
- Does the car mix Bluetooth A2DP audio with AA? If yes, Bluetooth Spotify is
  the simplest zero-capture fallback.
- Does the dongle accept AARE's certificate, or does it check against Google's
  CA? The peer-certificate logging test answers this.
- Is librespot acceptable given Spotify's terms, or should the Pi only do CAN
  and the phone handle Spotify via Shizuku/BT?
- Is the phone the daily device, or is a dedicated rooted car phone preferable
  for always-on/no-ritual audio?

## References

- [prototux/AARE](https://github.com/prototux/AARE) — phone-side AA, Kotlin,
  GPL-3.0; wireless, video/audio, `ProjectionDisplay`, `VideoEncoder`,
  `AapSession`, `WirelessBootstrap`.
- [mretallack/AndroidAuto](https://github.com/mretallack/AndroidAuto) —
  phone-side AA over USB; mutual-TLS certificate chain documentation and
  extraction notes. Do not ship Google's key.
- [Android AudioPlaybackCapture](https://developer.android.com/media/platform/av-capture)
  and [MediaProjection](https://developer.android.com/reference/android/media/projection/MediaProjection).
- [Spotify App Remote SDK](https://spotify.github.io/android-sdk/app-remote-lib/)
  and [Spotify Web API](https://developer.spotify.com/documentation/web-api).
- [Shizuku setup manual](https://shizuku.rikka.app/guide/setup/).
- [opencardev/openauto](https://github.com/opencardev/openauto),
  [opencardev/aasdk](https://github.com/opencardev/aasdk) — local head-unit
  stack and test harness.
- Local: `README.md`, `openauto-plan.md`, `MAC-PORT.md`, `RUNBOOK.md`.

## Caveats

- AARE is GPL-3.0; a distributed fork must comply.
- Bypassing Android Auto's UI removes Google's driving restrictions. Video and
  phone-screen mirroring must be parked/passenger-only; add a driving-status
  gate and do not rely on the car.
- Spotify's SDK/API and capture behavior can change. Keep the audio source
  pluggable and test again after Spotify updates.
- librespot is unofficial; Spotify can break it and its use is a ToS grey area.
- Do not distribute an app containing Google's extracted phone certificate/key.
