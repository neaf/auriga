# `capture/` — minimal headless aasdk head unit

This is the minimal Android Auto head unit used during the first exploration.
It is **reference/failed-path code**: it reaches AA version, TLS, service
discovery, channel opens and sensor requests, but does not get past the phone's
WPP / "Communication error 2" screen. The next session should use the full
OpenAuto stack (see `../NEXT-SESSION.md`).

## What it does

- AOA v2 switch with retry loop (dongle may cycle MTP/AOA).
- AA version (aasdk 1.7), TLS, service discovery.
- Advertises:
  - video sink (H.264 Baseline, 1280x720@30 requested),
  - media/system/guidance/telephony audio sinks (PCM 48 kHz/16-bit/stereo),
  - input source with a 1280x720 touchscreen,
  - Bluetooth service (car address `ED:A2:A4:94:4F:B8`, PIN + numeric comparison),
  - sensor source (driving status, location, night mode),
  - microphone media source (PCM 48 kHz/16-bit/mono),
  - Wi-Fi projection service (`AutoLink-A512` BSSID/credentials).
- Replies to incoming pings; sends a `PingRequest` immediately after service
  discovery and every 2 s.
- Sends the video focus indication after video setup.
- Writes raw outputs:
  - `video.h264` — H.264 Annex-B access units,
  - `audio-media.wav`, `audio-system.wav`, `audio-guidance.wav`,
    `audio-telephony.wav` — PCM WAV,
  - `input.jsonl` — injected touch events.

## Build on the Pi

Prereqs: aasdk built at `../build-aasdk` (see root `README.md`; aasdk protocol
version bumped to 1.7 in `aasdk/include/aasdk/Version.hpp`), CMake, Boost,
OpenSSL, protobuf, libusb.

```bash
cd ~/auriga
cmake --build build-aasdk -j2
cmake -S capture -B build-capture -DCMAKE_BUILD_TYPE=Release
cmake --build build-capture -j2
```

The app links the aasdk build tree directly and sets an rpath to
`build-aasdk/lib`. If you change aasdk headers (e.g. `AASDK_MINOR`), rebuild
aasdk and then the app.

## Run

```bash
cd ~/auriga
sudo ./build-capture/auriga_capture --out captures --duration 90
```

Options:

- `--out DIR` — output directory (default `captures`).
- `--duration SECONDS` — stop after N seconds.
- `--no-input` — do not advertise the input channel.

stdin commands (while the app is running):

```text
tap 640 360
down 640 360
move 700 380
up 700 380
quit
```

To inject commands when starting in the background, run with a FIFO:

```bash
mkfifo /tmp/auriga-in
tail -f /dev/null > /tmp/auriga-in &
sudo ./build-capture/auriga_capture --out captures < /tmp/auriga-in
echo 'tap 640 360' > /tmp/auriga-in
```

## Known limitations

- The dongle's phone-side WPP connection closes; the phone shows
  "Communication error 2 - incompatible software"; projection never starts.
- The phone's AA app retry loop can reset the dongle if it overlaps startup.
- The Pi has no GPS, so the sensor location event is empty (the phone should use
  its own location).
- The microphone source advertises the channel but sends no real mic audio.
- The Wi-Fi projection service returns the dongle AP credentials; it did not
  fix the WPP close.
- The car trip proved the dongle/phone work; the missing piece is the Pi
  head-unit/WPP behavior, which is why the full OpenAuto stack is next.
