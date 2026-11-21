# Phone-side custom app (what carries over from AARE)

Source reference: upstream `https://github.com/prototux/AARE` at
`e8da04dc422abd36be60a81bb9fc7f782e8d7e84` (2026-10-26, after v1.1.1). The bench
build in [`AARE fork.md`](AARE%20fork.md) is that tree plus
`docs/aare-cert-rotation.patch`.

Goal: a phone app that talks to the AutoLink A512 itself and puts **its own UI** on
the car screen, with the phone in the car and its screen asleep. AARE was the
experiment; this note records what it proved and what has to be different.

## Result

AARE works as a phone-side AA source (protocol, certificate, transport, input,
audio) but **cannot run with the phone screen off**: it renders the car UI as
Android windows on a virtual display (`ProjectionDisplay`: `Presentation` with
Compose content, `VIRTUAL_DISPLAY_FLAG_PRESENTATION | OWN_CONTENT_ONLY`), so
frames come from SurfaceFlinger composition. When the phone screen sleeps the
compositor stops and the encoder receives nothing.

Measured on the S25 (A512, wireless):

| State | `captures-mac/current/video.h264` |
| --- | --- |
| screen on, tap | grows (e.g. +300 kB in 4 s) |
| screen off, tap | 0 bytes |
| screen off, panel on at brightness 0 | grows normally |

The virtual display itself stays `state ON`; the process stays `FGS`; the AAP
session keeps pinging. Only composition stops, so this is not a wake-lock or
background-execution problem. Keeping the panel on (or at brightness 0) works but
defeats the point: the phone must stay unlocked and the display active.

## Proven alternative

An app that draws **into the encoder surface itself** does not depend on the
compositor and keeps running with the phone dozing. Verified with a throwaway app
(`artifacts/prender-test`, gitignored): OpenGL ES into
`MediaCodec.createInputSurface()`, drained in a second thread, foreground service
with a partial wake lock:

```
screen on:   frames=483  bytes=895090
screen off:  frames=603  bytes=1142126   (mWakefulness=Dozing, 30 fps)
```

Consequence: the custom app must draw its own UI. It cannot show other apps'
windows (Google Maps, Spotify) on the car screen, because those are separate
surfaces that only the compositor can combine. Audio is unaffected: media audio
goes through `AudioPlaybackCapture`, which works with the screen off.

## What to reuse from AARE

- `aap/` module — AA protocol: `AapSession`, `Cryptor` (TLS + pinning), `Frame`,
  `FrameIo`, `MessageIds`, `channels/`, `wireless/`.
- Transport: USB AOA (`UsbAccessoryTransport`) and the wireless WPP bootstrap
  (RFCOMM to the dongle, Wi-Fi credentials, `WifiNetworkSpecifier`).
- The phone certificate: the dongle only accepts a Google-issued `O=CarService`
  certificate (`daxter-certs/aare-phone.p12`); AARE's generated one is rejected
  with status `-3`.
- The dongle's certificate rotation: it presents one of two leaf certificates
  (`4e75e8b3…`, `1c0e0ef9…`); see [`AARE fork.md`](AARE%20fork.md) for the pin
  patch.
- Channel plumbing already exercised end to end: video (3), input (1), audio
  (6/7), media source/playback, phone status, navigation status.

## What to replace

- `ProjectionDisplay` (virtual display + `Presentation`) with a renderer that
  draws into the encoder input surface (EGL or Canvas) and feeds the video
  channel. This is the whole blocker.
- Car app hosting: no `CarAppService`/template rendering; the app owns the UI and
  handles the input channel directly.
- Car audio: keep the AA audio channels, but do not rely on screen capture for
  anything.

## Open questions for the custom app

- Which transport to implement first: USB AOA to the dongle (as the Mac does) or
  the wireless WPP path AARE uses (proven).
- Video format negotiation: the A512 accepts 1280x720/30 (`videoInfo`); 60 fps and
  1080p were never exercised successfully.
- How much of the AA "car" behaviour the dongle requires beyond video/input/audio
  (focus requests, media metadata, navigation status) — AARE's log shows the
  sequence to copy.
- Whether the car UI needs touch only, or also rotary/key events.

## Status

AARE stays as a **bench tool and protocol reference**, not the car path. The
bench setup (patched build, imported certificate, pairing) is in
[`AARE fork.md`](AARE%20fork.md).
