# Android Auto head unit

The head unit is `autoapp`: a patched OpenAuto (`4cc739b8`) built on a patched
aasdk (`9bf6adf`, branch `newdev`). It owns the dongle, speaks AA 1.7 over USB,
and in capture mode writes the AA media to files instead of decoding it. The
stream server and browser consume those files (`docs/Stream protocol.md`).

## Source trees and patches

| Tree | Revision | State |
| --- | --- | --- |
| `openauto/` | `4cc739b8` | separate git clone, ignored by the root repo, dirty by design |
| `aasdk-upstream/` | `9bf6adf` (`newdev`) | separate git clone, ignored by the root repo, dirty by design |

`patches/` is the source of truth for both trees. Patch order:

| Order | Patch | Tree | Purpose |
| ---: | --- | --- | --- |
| 1 | `patches/openauto-capture.patch` | `openauto` | capture mode: `Auriga*` sinks (buffered writer, codec-config separation), session/manifest geometry, input device, silent mic, `ServiceFactory` wiring |
| 2 | `patches/openauto-macos.patch` | `openauto` | ephemeral TCP port and no `startServerSocket()` in capture mode, macOS Bluetooth lister fix |
| 3 | `patches/openauto-auriga-usb-filter.patch` | `openauto` | pass `0x2717/0xFF40` to `USBHub`, skip the all-device enumerator in capture mode |
| 4 | `patches/openauto-auriga-gps-guard.patch` | `openauto` | call `gps_read()` only after a successful `gps_open()` |
| 5 | `patches/openauto-auriga-identity.patch` | `openauto` | AA identity `display_name`/`make`/`model` → `Auriga` |
| — | `patches/aasdk-usb-filter.patch` | `aasdk-upstream` | optional accessory-source VID/PID filter, refuse AOA+ADB |

The three `openauto-auriga-*` patches are incremental: they assume the earlier
patches are applied. Patch 1 defines `projection::captureModeEnabled()`
(`openauto/src/autoapp/Projection/AurigaSession.cpp`); patches 2 and 3 call it,
so they do not compile alone. Patches 2 and 3 both rewrite
`openauto/src/autoapp/App.cpp`; patches 1 and 4 both rewrite
`SensorService.cpp`.

Patch application, once per fresh clone:

```bash
git -C aasdk-upstream apply "$PWD/patches/aasdk-usb-filter.patch"
git -C openauto apply "$PWD/patches/openauto-capture.patch"
git -C openauto apply "$PWD/patches/openauto-macos.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-usb-filter.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-gps-guard.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-identity.patch"
```

Use absolute patch paths: a relative path is resolved inside the nested clone and
fails (`git -C openauto apply --check --reverse patches/...` reports
`can't open patch`).

### aasdk edits live only in the nested tree

Symptom: a rebuild from `patches/` alone leaves aasdk at AA protocol 1.6 and
cannot compile the generated protobuf on Darwin.
Cause: two aasdk edits have no patch file: `AASDK_MINOR = 7` in
`aasdk-upstream/include/aasdk/Version.hpp:22-23`, and the Darwin absl include
block in `aasdk-upstream/protobuf/CMakeLists.txt`. The OpenAuto side is fully
described by the five patches above.
Workaround: apply the two edits by hand after the patch list, or build from the
existing nested trees. See `docs/Build.md`.
Location: `aasdk-upstream/Version.hpp`, `aasdk-upstream/protobuf/CMakeLists.txt`.

## USB and the AOA switch

`autoapp` constructs `USBHub` with vendor `0x2717`, product `0xFF40`
(`openauto/src/autoapp/autoapp.cpp:245-246`). `USBHub::handleDevice` ignores
every non-AOA device except that pair and refuses `18d1:2d01`
(`aasdk-upstream/src/USB/USBHub.cpp:100-133`). The dongle is the only device ever
switched to AOA; its USB identity table is in `docs/AutoLink A512 dongle.md`.

Hotplug is registered with `LIBUSB_HOTPLUG_ENUMERATE` and
`LIBUSB_HOTPLUG_MATCH_ANY` (`USBHub.cpp:43-51`): the flag reports devices
already on the bus at registration time, and the callback is registered once per
`start()` and removed only by `cancel()` (`USBHub.cpp:52-66`). A device that
appears while no callback is registered is not seen. A non-AOAP source match
costs a fixed 1 s sleep inside the strand before the query chain starts
(`USBHub.cpp:139`).

In capture mode `App` skips `enumerateDevices()`
(`openauto/src/autoapp/App.cpp:56-65`). That enumerator runs the full AOA query
chain against every openable USB device
(`aasdk-upstream/src/USB/ConnectedAccessoriesEnumerator.cpp:60-80`) and would
switch a development phone into accessory mode. The skip is keyed on capture
mode, not on the descriptor filter, so a non-capture run of the same binary
still probes every device.

### No retry after a hub error

Symptom: after one USB rejection `autoapp` idles at `Waiting for device...`
until restarted; nothing retries.
Cause: `App::onUSBHubError` logs and returns; its `waitForDevice()` retry block
is commented out (`openauto/src/autoapp/App.cpp:253-265`). Only
`onAndroidAutoQuit` re-arms `waitForDevice()` (`App.cpp:243-249`).
Workaround: restart `autoapp`; a cold dongle replug if it is stuck in AOA.
Location: `openauto/src/autoapp/App.cpp:253-265`.

## Capture mode

`AURIGA_CAPTURE_DIR` is the single opt-in switch. When it is set and non-empty,
`ServiceFactory` replaces the Qt/RtAudio backends with file sinks and `App`
changes its USB/TCP behaviour. The environment is read once, in
`captureDirectory()`, and every branch asks `captureModeEnabled()` or the same
cached directory (`openauto/src/autoapp/Projection/AurigaSession.cpp:34-64`).
An empty value means capture mode off, not a headless process with GUI backends.

| Effect | Condition | Location |
| --- | --- | --- |
| one `session-<id>/` directory per AA entity holding `video.h264`, `audio-{media,guidance,system}.wav`, `input.jsonl`, `manifest.json`, and a `current` pointer | capture dir non-empty | `openauto/src/autoapp/Service/ServiceFactory.cpp:132-136,178-180,197,205,231,240-241`; `openauto/src/autoapp/Projection/AurigaSession.cpp` |
| create the capture dir (`create_directories`) and read the env once | capture mode | `AurigaSession.cpp:38-59` |
| no all-device AOA enumerator | capture mode | `openauto/src/autoapp/App.cpp:56` |
| acceptor bound to port 0, no `async_accept` | capture mode | `App.cpp:40,182` |
| geometry published in `manifest.json` from `Video.Resolution` / `Video.FPS` | capture mode | `ServiceFactory.cpp:65-96,130-136`; `AurigaSession.cpp:182-191` |

## Capture file contract

One AA entity is one capture session: a directory plus a `current` pointer.

```
<capture-dir>/
  current -> session-<id>
  session-<id>/
    video.h264
    audio-media.wav
    audio-guidance.wav
    audio-system.wav
    input.jsonl
    manifest.json
```

`ServiceFactory::create()` builds one `AurigaSessionManager` per AA entity and
hands it to every sink, so the four files of one entity are created in the same
directory no matter how far apart the channels open
(`ServiceFactory.cpp:132-136,178-180,197,205,231,240-241`;
`AurigaSession.cpp:107-147`). Session ids are local time `%Y%m%d-%H%M%S`, with
`-2`, `-3`, … appended when that id already exists
(`AurigaSession.cpp:87-103`).

Publication order at session start: create `session-<id>/`, write
`manifest.json` (`manifest.json.tmp` + rename), then replace `current`
(`current.tmp.<pid>` symlink + rename). Both renames are atomic, so the stream
server never sees a half-written pointer or manifest
(`AurigaSession.cpp:182-233`).

`manifest.json` names the session, the AA video geometry and one segment count
per stream:

```json
{"session":"20261029-090405","width":1280,"height":720,"fps":30,"audio-guidance":0,"audio-media":0,"audio-system":0,"video":0}
```

`width`, `height` and `fps` come from `Video.Resolution` and `Video.FPS` through
`configuredVideoGeometry()` (`ServiceFactory.cpp:65-96,130-136`;
`AurigaSession.cpp:182-191`), the same mapping that sets the touch coordinate
space, so the stream server and the browser size the canvas from the geometry
the phone was actually configured with. `fps` is a JSON number and may be
fractional; `29.97` is printed as such.

| File | Format | Written | Rotation |
| --- | --- | --- | --- |
| `video.h264` | Annex-B H.264, 4-byte start codes, one AA access unit per `write()`; SPS/PPS once at the head of each segment | queued by the channel strand, written and flushed per access unit by the sink's writer thread (`AurigaVideoOutput.cpp:113-144`) | truncated and restarted at 0 before 4 GiB; the `video` count advances (`AurigaVideoOutput.cpp:138-142,146-160`) |
| `audio-media.wav` | PCM WAV, 48 kHz, 2 ch, 16-bit | raw AA PCM after a 44-byte header; queued by the channel strand, written by the writer thread (`AurigaAudioOutput.cpp:153-176`) | restarted at 44 bytes with a fresh header before 4 GiB; the `audio-media` count advances (`AurigaAudioOutput.cpp:164-168,215-229`) |
| `audio-guidance.wav` | PCM WAV, 16 kHz, 1 ch, 16-bit | same writer | same as `audio-media`, count `audio-guidance` |
| `audio-system.wav` | PCM WAV, 16 kHz, 1 ch, 16-bit | same writer | same as `audio-media`, count `audio-system` |
| `input.jsonl` | JSON lines `{"ts":epoch_us,"cmd","x","y"}` | flushed per line (`AurigaInputDevice.cpp:216-231`) | none |

Each sink still opens its file with `std::ios::trunc`, but into a directory that
was just created, so a new session never touches the previous files: a
reconnect creates a second `session-*` directory and preserves the first.

Rotation uses one limit, `SEGMENT_LIMIT = 4 GiB - 16 MiB`, applied to video
bytes and WAV data bytes so the 32-bit RIFF sizes cannot wrap
(`AurigaSession.hpp:40`; `AurigaVideoOutput.cpp:138`,
`AurigaAudioOutput.cpp:164`). A rotated file keeps its name and restarts at
offset 0; the manifest count is the only rollover signal, and the old segment's
bytes are discarded. Rotation runs on the sink's writer thread, so the manifest
rewrite is off the channel strand too.

Retention is bounded: a new session removes all but the newest five
`session-*` directories, always keeping the current one
(`AurigaSession.hpp:42`; `AurigaSession.cpp:235-281`).

WAV header: 44 bytes, RIFF/WAVE/fmt/data, 32-bit RIFF and data sizes, rewritten
after every accumulated second of audio (`AurigaAudioOutput.cpp:153-176,178-210`).
Between rewrites the header lags the file by up to 1 s of audio.

`AurigaAudioOutput::start()` and `suspend()` are empty, and `autoapp` installs
no SIGTERM handler: a `pkill` stop leaves the WAV header at the last 1 s
boundary. `stop()` (destructor path) rewrites it.

### Codec config is separate from media

`MEDIA_MESSAGE_CODEC_CONFIG` does not share the media write path: both sink
services hand the payload to `setCodecConfig()` instead of the media writer
(`VideoMediaSinkService.cpp:196-212`, `AudioMediaSinkService.cpp:227-243`). The
video sink caches the bytes and writes them once in front of the first access
unit of each segment, so every segment starts with SPS/PPS
(`AurigaVideoOutput.cpp:83-96,120-131`). The audio sink ignores the payload: it
describes the PCM format the WAV header already carries, and appending it would
corrupt the sample stream (`AurigaAudioOutput.cpp:108-112`).

`video.h264` therefore starts with SPS/PPS and then media only; `audio-*.wav`
contains only the 44-byte header and PCM. NAL layout of a segment head:
SPS at 0, PPS at 21, IDR at 29, first slice at 3645 (measured on
`captures/2026-10-28-macos-session2-video.h264`, which carries the same head).

### Silent microphone

The capture build advertises the microphone channel but feeds it paced silence:
zero buffers of `sampleRate/50 * channels * bytes/sample` every 20 ms on a
`deadline_timer` (`openauto/src/autoapp/Projection/AurigaAudioInput.cpp:62-93`).
No Qt/ALSA capture path is opened.

### Input device

`AurigaInputDevice` reads the process's stdin, which the run script wires to the
input FIFO. Line protocol:

| Line | Effect |
| --- | --- |
| `tap X Y` | `ACTION_DOWN`, 80 ms sleep, `ACTION_UP`, one JSONL line |
| `down X Y` | `ACTION_DOWN` |
| `move X Y` | `ACTION_MOVED` |
| `up X Y` | `ACTION_UP` |
| `quit` | stops the reader thread only; `autoapp` keeps running with touch disabled |

`X Y` are in the configured video geometry (`1280x720` with `Video.Resolution=2`).
The device starts only after the phone sends `KeyBindingRequest`
(`openauto/src/autoapp/Service/InputSource/InputSourceService.cpp:120-131`);
earlier FIFO lines are never read. The 80 ms `tap` sleep runs on the single
reader thread, so `down`/`move`/`up` behind a tap wait for it
(`AurigaInputDevice.cpp:165-175`). The FIFO needs a live writer or `read()`
returns EOF and the reader exits; the run scripts park `sleep 86400` on it.

### Configuration that capture mode honours

`openauto-config/openauto.ini` is resolved from the process CWD.

| Key | Value | Effect |
| --- | --- | --- |
| `Video.Resolution` | `2` | 1280x720; also sets the touch geometry (`ServiceFactory.cpp:149-152`) |
| `Video.FPS` | `2` | 30 fps (`ServiceFactory` uses the same enum mapping) |
| `AudioChannel.MediaEnabled` / `GuidanceEnabled` | `true` | creates the corresponding sink |
| `AudioChannel.TelephonyEnabled` | `false` | the telephony block in `ServiceFactory` is commented out, so the service is never created |
| `Bluetooth.WirelessProjectionEnabled` | `true` | registers the Bluetooth service (`ServiceFactory.cpp:115-125`) |
| `Bluetooth.AdapterAddress` | empty | selects `DummyBluetoothDevice` |
| `Audio.OutputBackendType`, `Input.EnableTouchscreen`, `Input.EnablePlayerControl`, `Bluetooth.AdapterType` | — | parsed but not read by any code path; inert |

## AA session behaviour

Advertised services, built per AA entity: video sink, media/guidance/system
audio sinks, microphone source, sensor source, input source, and Bluetooth when
`WirelessProjectionEnabled` is true. The same call mints one capture session and
publishes `current` (`ServiceFactory.cpp:123-153`). Android Auto over Wi-Fi (WPP)
and telephony audio are not advertised (`ServiceFactory.cpp:123-153,212-225`).

Identity and ping values in the service-discovery response
(`openauto/src/autoapp/Service/AndroidAutoEntity.cpp:178-203`):

| Field | Value |
| --- | --- |
| `display_name` | `Auriga` |
| `driver_position` | `DRIVER_POSITION_RIGHT` |
| `headunit_info.make` / `model` / `year` | `Auriga` / `Auriga` / `2018` |
| `headunit_info.vehicle_id` | `2024110822150988` |
| `head_unit_make` / `head_unit_model` | `Auriga` / `Auriga` |
| `head_unit_software_build` / `version` | `1` / `1.0` |
| ping interval / timeout / tracked | 1000 ms / 3000 ms / 5 |

The identity strings are patched in `patches/openauto-auriga-identity.patch`;
`display_name` is set once, in the `headunit_info` block.

The ping values are advertised, not implemented: the pinger runs on a 5000 ms
timer with one outstanding request and rejects the entity once 5 pings are
unanswered (`openauto/src/autoapp/Service/AndroidAutoEntityFactory.cpp:65`,
`openauto/src/autoapp/Service/Pinger.cpp:29-62`).

Sensor service (`openauto/src/autoapp/Service/Sensor/SensorService.cpp:30-48,238-260`):
driving status `UNRESTRICTED`, night mode from the existence of
`/tmp/night_mode_enabled`, GPS polled every 250 ms and read only when
`gps_open("127.0.0.1","2947")` succeeded. Without `gpsd` the service logs
`can't connect to GPSD` and never calls `gps_read`.

Bluetooth service (`BluetoothService.cpp:60-141`): with the dummy device
(`DummyBluetoothDevice.cpp:30-42`, `isAvailable() == false`) it advertises
`car_address=""` and `BLUETOOTH_PAIRING_UNAVAILABLE`. A pairing request always
gets `STATUS_SUCCESS`, `already_paired=false`, then authentication data with PIN
`123456`.

### First AA entity fails with `AASDK Error 10`

Symptom: the first entity after a start dies with `AASDK Error: 10` (native 1 or
2) before `Version Received`; OpenAuto reconnects and the next entity projects.
Cause: `unverified`. The failure happens before any Bluetooth pairing request can
occur, so the dongle cannot have rejected a pairing at that point. The first
entity's USB transfer fails on the dongle side; the trigger is not identified in
the log.
Workaround: let OpenAuto reconnect; if the dongle stays in AOA, replug it.
Location: `logs/openauto-mac-*.log`; `App.cpp:243-249` retry path.

## Threading and the real-time boundary

`autoapp` runs one Qt main thread (`qApplication.exec()`), four
`io_service.run()` threads and four libusb event threads
(`openauto/src/autoapp/autoapp.cpp:46-73`). Each service owns a
`boost::asio::strand` and hands the same strand to its aasdk channel, so channel
receive, the queue copy, ACK send and `stop()` are serialized per service.
`AurigaInputDevice` adds one raw reader thread on stdin; `AurigaAudioInput` and
`SensorService` use `deadline_timer` callbacks, not threads.

Media flow control: each media channel requests `max_unacked=1`
(`VideoMediaSinkService.cpp:117`, `AudioMediaSinkService.cpp:174`). The media ACK
is sent *before* the sink is asked to accept the buffer
(`VideoMediaSinkService.cpp:180-190`, `AudioMediaSinkService.cpp:211-221`), and
the sink's `write()` only copies into a bounded in-memory queue
(`AurigaWriter.hpp:79-115`). No media buffer touches the disk on the channel
strand and no disk latency sits in the flow-control window, so a slow disk cannot
stall the phone's next frame (`NFR-01`). Channel open and stop still open,
truncate and close the file once, on the strand, before the writer starts.

Each sink owns one writer thread that drains that queue to the segment file,
flushes per access unit and performs rotation, retention bookkeeping and the WAV
header rewrite (`AurigaVideoOutput.cpp:113-160`,
`AurigaAudioOutput.cpp:153-229`). The queue is bounded at 240 chunks and 64 MiB
(`AurigaWriter.hpp:42-45`); when a sink cannot keep up the oldest chunk is
dropped and counted, never blocked on, and the first drop plus every 100th is
logged. `stop()` drains the queue and joins the writer thread before closing the
file, so a normal stop still finalizes the WAV header.

`AurigaSessionManager` mints the session and publishes `current` on the
entity-creation path. `noteRotation` rewrites `manifest.json` from the sink's
writer thread, at most once per 4 GiB per stream (`AurigaSession.cpp:164-178`;
`AurigaVideoOutput.cpp:138-142`, `AurigaAudioOutput.cpp:164-168`).

## AA stream format

Measured on `captures/2026-10-28-macos-session2-video.h264` (ffprobe + NAL scan):

| Property | Value |
| --- | --- |
| codec / profile / level | H.264 Baseline, level 3.1 |
| resolution / fps | 1280x720, 30 |
| start codes | 4-byte `00 00 00 01`, all 3059 NALs |
| NALs | 1 SPS, 1 PPS, 2 IDR, 3055 non-IDR slices |
| frames | 3057 (`ffprobe -count_frames`) |
| IDR spacing | 1800 frames (~60 s at 30 fps) |
| slices per frame | 1 |
| size / duration | 12,274,423 B over 122 s (~100 kB/s) |

The file carries no container timestamps: `ffprobe` reports
`r_frame_rate=1200000/1`. Use `-count_frames`, never ffprobe duration.

## TLS

aasdk is the TLS client. `SSLWrapper::getMethod` returns
`TLSv1_2_client_method()` only for OpenSSL < 1.1.0 and `TLS_client_method()`
otherwise (`aasdk-upstream/src/Transport/SSLWrapper.cpp:97-103`), so the version
is negotiated. Peer verification is off:
`SSL_set_verify(ssl, SSL_VERIFY_NONE, nullptr)`
(`SSLWrapper.cpp:137-139`). The certificate and key are compiled-in PEM
constants (`aasdk-upstream/src/Messenger/Cryptor.cpp:253,273`; the same JVC
Kenwood certificate is installed from `aasdk-upstream/cert/headunit.crt|key` by
aasdk's CMake). aasdk never inspects or logs the peer certificate.

## Verification

```bash
cmake --build build-aasdk-mac --target aasdk -j8
cmake --build build-openauto-mac --target autoapp -j8
./scripts/mac-headunit-start.sh
pgrep -fl "autoapp|auriga_stream"
adb -s RFGL329J04J shell svc usb getFunctions          # expect: mtp
ioreg -p IOUSB -l -w 0 | grep -E 'o (AutoLink|SAMSUNG_Android)@|"idProduct" = (26720|11520|11521|65344)'
tail -20 "$(ls -t logs/openauto-mac-*.log | head -1)"  # Version Received + pings
ffmpeg -loglevel info -i captures-mac/video.h264 -f null - 2>&1 | tail -1
```

Expected: dongle `18d1:2d00`, phone `04e8:6860` and `svc usb getFunctions` =
`mtp`, at least one `Version Received: 256.1792`, and a growing video file.
