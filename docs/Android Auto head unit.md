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
| 1 | `patches/openauto-capture.patch` | `openauto` | capture mode: `Auriga*` file sinks, input device, silent mic, `ServiceFactory` wiring |
| 2 | `patches/openauto-macos.patch` | `openauto` | `aurigaCaptureMode()`, ephemeral TCP port, no `startServerSocket()`, macOS Bluetooth lister fix |
| 3 | `patches/openauto-auriga-usb-filter.patch` | `openauto` | pass `0x2717/0xFF40` to `USBHub`, skip the all-device enumerator in capture mode |
| 4 | `patches/openauto-auriga-gps-guard.patch` | `openauto` | call `gps_read()` only after a successful `gps_open()` |
| — | `patches/aasdk-usb-filter.patch` | `aasdk-upstream` | optional accessory-source VID/PID filter, refuse AOA+ADB |

The two `openauto-auriga-*` patches are incremental: they assume patches 1 and 2
are applied. `openauto-auriga-usb-filter.patch` calls `aurigaCaptureMode()`,
which patch 2 introduces, so it does not compile alone. Patches 2 and 3 both
rewrite `openauto/src/autoapp/App.cpp`; patches 1 and 4 both rewrite
`SensorService.cpp`.

Patch application, once per fresh clone:

```bash
git -C aasdk-upstream apply "$PWD/patches/aasdk-usb-filter.patch"
git -C openauto apply "$PWD/patches/openauto-capture.patch"
git -C openauto apply "$PWD/patches/openauto-macos.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-usb-filter.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-gps-guard.patch"
```

Use absolute patch paths: a relative path is resolved inside the nested clone and
fails (`git -C openauto apply --check --reverse patches/...` reports
`can't open patch`).

### Patches are not a complete source of truth

Symptom: applying the four OpenAuto patches to a pristine `4cc739b8` tree
compiles `AurigaInputDevice.cpp` with an incomplete
`IInputDeviceEventHandler` type; `git apply --check --reverse` of the capture
patch fails on that one file.
Cause: `patches/openauto-capture.patch` omits
`#include <f1x/openauto/autoapp/Projection/IInputDeviceEventHandler.hpp>`; the
live tree has it at
`openauto/src/autoapp/Projection/AurigaInputDevice.cpp:18`, and the sink calls
`eventHandler_->onTouchEvent(...)`, which needs the complete type.
Workaround: add the include after applying the patch, or build from the existing
`openauto/` tree.
Location: `patches/openauto-capture.patch` (new-file block for
`AurigaInputDevice.cpp`); the reverse check is the detector.

Two aasdk edits live only in the nested tree, with no patch file:
`AASDK_MINOR = 7` in `aasdk-upstream/include/aasdk/Version.hpp:22-23`, and the
Darwin absl include block in `aasdk-upstream/protobuf/CMakeLists.txt`. A rebuild
from patches alone leaves aasdk at protocol 1.6. See `docs/Build.md`.

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
(`openauto/src/autoapp/App.cpp:57-66`). That enumerator runs the full AOA query
chain against every openable USB device
(`aasdk-upstream/src/USB/ConnectedAccessoriesEnumerator.cpp:60-80`) and would
switch a development phone into accessory mode. The skip is keyed on capture
mode, not on the descriptor filter, so a non-capture run of the same binary
still probes every device.

### No retry after a hub error

Symptom: after one USB rejection `autoapp` idles at `Waiting for device...`
until restarted; nothing retries.
Cause: `App::onUSBHubError` logs and returns; its `waitForDevice()` retry block
is commented out (`openauto/src/autoapp/App.cpp:256-266`). Only
`onAndroidAutoQuit` re-arms `waitForDevice()` (`App.cpp:247-253`).
Workaround: restart `autoapp`; a cold dongle replug if it is stuck in AOA.
Location: `openauto/src/autoapp/App.cpp:256-266`.

## Capture mode

`AURIGA_CAPTURE_DIR` is the single opt-in switch. When set, `ServiceFactory`
replaces the Qt/RtAudio backends with file sinks and `App` changes its USB/TCP
behaviour.

| Effect | Condition | Location |
| --- | --- | --- |
| `video.h264`, `audio-{media,guidance,system}.wav`, `input.jsonl` in the capture dir | capture dir non-empty | `openauto/src/autoapp/Service/ServiceFactory.cpp:60-101,166-168,228-231,247-249` |
| create the capture dir (`create_directories`) | capture dir non-empty | `ServiceFactory.cpp:68-78` |
| no all-device AOA enumerator | `AURIGA_CAPTURE_DIR` set | `openauto/src/autoapp/App.cpp:59` |
| acceptor bound to port 0, no `async_accept` | `AURIGA_CAPTURE_DIR` set | `App.cpp:42-43,185-188` |

The variable has two readers with different empty-string semantics:
`App.cpp:31-33` treats any non-null value (including `""`) as capture mode, while
`ServiceFactory.cpp:67` requires non-null and non-empty, and caches the result
in a function-local static. `AURIGA_CAPTURE_DIR=""` therefore gives a headless
process with GUI backends and no capture files.

## Capture file contract

| File | Format | Written | Truncated at |
| --- | --- | --- | --- |
| `video.h264` | Annex-B H.264, 4-byte start codes, one AA access unit per `write()` | written and flushed per access unit (`openauto/src/autoapp/Projection/AurigaVideoOutput.cpp:67-68`) | video channel open (`AurigaVideoOutput.cpp:39`) |
| `audio-media.wav` | PCM WAV, 48 kHz, 2 ch, 16-bit | raw AA PCM after a 44-byte header (`AurigaAudioOutput.cpp:90-106`) | media audio channel open (`AurigaAudioOutput.cpp:70`) |
| `audio-guidance.wav` | PCM WAV, 16 kHz, 1 ch, 16-bit | same writer | guidance audio channel open |
| `audio-system.wav` | PCM WAV, 16 kHz, 1 ch, 16-bit | same writer | system audio channel open |
| `input.jsonl` | JSON lines `{"ts":epoch_us,"cmd","x","y"}` | flushed per line (`AurigaInputDevice.cpp:220-232`) | input device start, i.e. the phone's `KeyBindingRequest` |

The three audio sinks open with `std::ios::trunc` on fixed names. All four files
are recreated for every AA entity: a reconnect discards the previous session's
capture, and the four truncation instants are not synchronized (video and audio
at channel open, JSONL at `KeyBindingRequest`).

WAV header: 44 bytes, RIFF/WAVE/fmt/data, 32-bit RIFF and data sizes, rewritten
after every accumulated second of audio (`AurigaAudioOutput.cpp:103-106,145-166`).
Between rewrites the header lags the file by up to 1 s of audio. The 32-bit
sizes wrap after ~4 GiB of media audio (about 6.2 h at 192,000 B/s).

`AurigaAudioOutput::start()` and `suspend()` are empty, and `autoapp` installs
no SIGTERM handler: a `pkill` stop leaves the WAV header at the last 1 s
boundary. `stop()` (destructor path) rewrites it.

### Codec config shares the media write path

Symptom: the codec-config payload is written into the media file by the same
callback as frames; the video file starts with SPS/PPS, and the PCM file is only
clean because the audio config payload is empty today.
Cause: `onMediaIndication` forwards into `onMediaWithTimestampIndication`
(`openauto/src/autoapp/Service/MediaSink/VideoMediaSinkService.cpp:190-193`,
`AudioMediaSinkService.cpp:222-226`), and both sinks write unconditionally.
Workaround: none needed while the audio config is empty; the stream server
filters SPS/PPS out of the video stream.
Location: `VideoMediaSinkService.cpp:190-193`,
`AudioMediaSinkService.cpp:222-226`.

Measured head of `captures/2026-10-28-macos-session2-video.h264`: SPS at 0, PPS
at 21, IDR at 29, first slice at 3645.

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
`WirelessProjectionEnabled` is true. Android Auto over Wi-Fi (WPP) and telephony
audio are not advertised (`ServiceFactory.cpp:108-128,199-213`).

Identity and ping values in the service-discovery response
(`openauto/src/autoapp/Service/AndroidAutoEntity.cpp:181-202`):

| Field | Value |
| --- | --- |
| `display_name` | `Crankshaft-NG` (set twice) |
| `driver_position` | `DRIVER_POSITION_RIGHT` |
| `headunit_info.make` / `model` / `year` | `Crankshaft` / `Universal` / `2018` |
| `headunit_info.vehicle_id` | `2024110822150988` |
| `head_unit_make` / `head_unit_model` | `f1x` / `Crankshaft-NG Autoapp` |
| `head_unit_software_build` / `version` | `1` / `1.0` |
| ping interval / timeout / tracked | 1000 ms / 3000 ms / 5 |

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
Location: `logs/openauto-mac-*.log`; `App.cpp:247-253` retry path.

## Threading and the real-time boundary

`autoapp` runs one Qt main thread (`qApplication.exec()`), four
`io_service.run()` threads and four libusb event threads
(`openauto/src/autoapp/autoapp.cpp:46-73`). Each service owns a
`boost::asio::strand` and hands the same strand to its aasdk channel, so channel
receive, sink write, ACK send and `stop()` are serialized per service. The
per-file `std::mutex` in both sinks is therefore uncontended. `AurigaInputDevice`
adds one raw reader thread on stdin; `AurigaAudioInput` and `SensorService` use
`deadline_timer` callbacks, not threads.

Media flow control: each media channel requests `max_unacked=1`
(`VideoMediaSinkService.cpp:117`, `AudioMediaSinkService.cpp:174`) and sends the
media ACK after `write()` returns
(`VideoMediaSinkService.cpp:177-186`, `AudioMediaSinkService.cpp:209-218`). Disk
latency is therefore inside the phone-visible flow-control path: a slow write
delays the ACK and the phone's next frame. Removing the I/O from that path is an
open requirement (NFR-01), not current behaviour.

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
