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
| — | `patches/aasdk-version-absl.patch` | `aasdk-upstream` | AA protocol minor 6 → 7, absl include path for `aap_protobuf` |

The three `openauto-auriga-*` patches are incremental: they assume the earlier
patches are applied. Patch 1 defines `projection::captureModeEnabled()`
(`openauto/src/autoapp/Projection/AurigaSession.cpp`); patches 2 and 3 call it,
so they do not compile alone. Patches 2 and 3 both rewrite
`openauto/src/autoapp/App.cpp`; patches 1 and 4 both rewrite
`SensorService.cpp`.

Patch application, once per fresh clone:

```bash
git -C aasdk-upstream apply "$PWD/patches/aasdk-usb-filter.patch"
git -C aasdk-upstream apply "$PWD/patches/aasdk-version-absl.patch"
git -C openauto apply "$PWD/patches/openauto-capture.patch"
git -C openauto apply "$PWD/patches/openauto-macos.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-usb-filter.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-gps-guard.patch"
git -C openauto apply "$PWD/patches/openauto-auriga-identity.patch"
```

Use absolute patch paths: a relative path is resolved inside the nested clone and
fails (`git -C openauto apply --check --reverse patches/...` reports
`can't open patch`). `scripts/build.sh` performs this list on fresh clones and
builds both targets (`docs/Build.md#one-command-build`).

### aasdk needs AA 1.7 and absl include paths

Symptom: a stock aasdk advertises AA protocol 1.6, and on Darwin the generated
`aap_protobuf` target fails on `absl/...` includes from protobuf 36.
Cause: `AASDK_MINOR` is `6` upstream, and `aap_protobuf` does not add absl's
include directories.
Workaround: `patches/aasdk-version-absl.patch` (minor → 7, absl include path on
Darwin). A tree without that patch cannot negotiate the dongle's 1.7 session.
Location: `include/aasdk/Version.hpp` (`AASDK_MAJOR`/`AASDK_MINOR`),
`protobuf/CMakeLists.txt`.

## USB and the AOA switch

`autoapp` constructs `USBHub` with vendor `0x2717`, product `0xFF40`
(`openauto/src/autoapp/autoapp.cpp:245-246`). `USBHub::handleDevice` ignores
every non-AOA device except that pair and refuses `18d1:2d01`
(`aasdk-upstream/src/USB/USBHub.cpp:115-136`). The dongle is the only device ever
switched to AOA; its USB identity table is in `docs/AutoLink A512 dongle.md`.

Hotplug is registered with `LIBUSB_HOTPLUG_ENUMERATE` and
`LIBUSB_HOTPLUG_MATCH_ANY` (`USBHub.cpp:47-52`): the flag reports devices
already on the bus at registration time, and the callback is registered once per
`start()` (`:45-55`) and removed only by `cancel()` (`:57-72`). A device that
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
hands it to every sink, so all six files of one entity are created in the same
directory no matter how far apart the channels open
(`ServiceFactory.cpp` video/audio/input wiring; `AurigaSession.cpp`
session mint/publish). Session ids are local time `%Y%m%d-%H%M%S`, with
`-2`, `-3`, … appended when that id already exists.

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
`configuredVideoGeometry()` (`ServiceFactory.cpp`; `AurigaSession.cpp`
`writeManifest`), the same mapping that sets the touch coordinate space, so the
stream server and the browser size the canvas from the geometry the phone was
actually configured with. `configuredVideoGeometry()` yields 30 or 60 fps, so
`fps` is written as an integer (`30`); fractional rates are not produced.

| File | Format | Written | Rotation |
| --- | --- | --- | --- |
| `video.h264` | Annex-B H.264, 4-byte start codes, one AA access unit per `write()`; SPS/PPS once at the head of each segment | queued by the channel strand, written and flushed per access unit by the sink's writer thread (`AurigaVideoOutput.cpp`) | truncated and restarted at 0 before 4 GiB; the `video` count advances |
| `audio-media.wav` | PCM WAV, 48 kHz, 2 ch, 16-bit | raw AA PCM after a 44-byte header; queued by the channel strand, written by the writer thread (`AurigaAudioOutput.cpp`) | restarted at 44 bytes with a fresh header before 4 GiB; the `audio-media` count advances |
| `audio-guidance.wav` | PCM WAV, 16 kHz, 1 ch, 16-bit | same writer | same as `audio-media`, count `audio-guidance` |
| `audio-system.wav` | PCM WAV, 16 kHz, 1 ch, 16-bit | same writer | same as `audio-media`, count `audio-system` |
| `input.jsonl` | JSON lines `{"ts":epoch_us,"cmd","x","y"}` | flushed per line (`AurigaInputDevice.cpp`) | none |

Each sink still opens its file with `std::ios::trunc`, but into a directory that
was just created, so a new session never touches the previous files: a
reconnect creates a second `session-*` directory and preserves the first.

Rotation uses one limit, `SEGMENT_LIMIT = 4 GiB - 16 MiB`, applied to video
bytes and WAV data bytes so the 32-bit RIFF sizes cannot wrap
(`AurigaSession.hpp`; `AurigaVideoOutput.cpp`, `AurigaAudioOutput.cpp`). A
rotated file keeps its name and restarts at offset 0; the manifest count is the
only rollover signal, and the old segment's bytes are discarded. Rotation runs on
the sink's writer thread, so the manifest rewrite is off the channel strand too.

Retention is bounded: a new session removes all but the newest five
`session-*` directories, always keeping the current one
(`AurigaSession.hpp`; `AurigaSession.cpp` `prune`).

WAV header: 44 bytes, RIFF/WAVE/fmt/data, 32-bit RIFF and data sizes, rewritten
after every accumulated second of audio (`AurigaAudioOutput.cpp`).
Between rewrites the header lags the file by up to 1 s of audio.

`AurigaAudioOutput::start()` and `suspend()` are empty, and `autoapp` installs
no SIGTERM handler: a `pkill` stop leaves the WAV header at the last 1 s
boundary. `stop()` (destructor path) rewrites it.

### Codec config is separate from media

`MEDIA_MESSAGE_CODEC_CONFIG` does not share the media write path: both sink
services hand the payload to `setCodecConfig()` instead of the media writer
(`VideoMediaSinkService.cpp`, `AudioMediaSinkService.cpp`). The video sink caches
the bytes and writes them in front of the first access unit of each segment, so
every segment starts with SPS/PPS (`AurigaVideoOutput.cpp`). Config ordering is
not guaranteed: when the phone sends it after the first access unit, the writer
thread appends it at the current file offset and logs a warning, instead of
losing it until the next 4 GiB rotation. The audio sink ignores the payload: it
describes the PCM format the WAV header already carries, and appending it would
corrupt the sample stream (`AurigaAudioOutput.cpp`).

`video.h264` therefore starts with SPS/PPS and then media only; `audio-*.wav`
contains only the 44-byte header and PCM. NAL layout of a segment head:
SPS at 0, PPS at 21, IDR at 29, first slice at 3645 (measured on
`captures/2026-10-28-macos-session2-video.h264`, which carries the same head).

A writer-queue overflow drops the oldest chunk and counts it. Because the deltas
that follow reference the lost frame, the video writer then skips frames until
the next IDR and writes SPS/PPS before it, so the file never contains an
undecodable reference chain; the skipped interval is a visible gap, not
corruption. The stream server sees that IDR as its resync point.

### Silent microphone

The capture build advertises the microphone channel but feeds it paced silence:
zero buffers of `sampleRate/50 * channels * bytes/sample` every 20 ms on a
`deadline_timer` (`openauto/src/autoapp/Projection/AurigaAudioInput.cpp`).
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
| `quit` | stops the reader thread only; `autoapp` keeps running with touch disabled until the next `KeyBindingRequest` restarts it |

`X Y` are in the configured video geometry (`1280x720` with `Video.Resolution=2`).
The device starts only after the phone sends `KeyBindingRequest`
(`openauto/src/autoapp/Service/InputSource/InputSourceService.cpp`);
earlier FIFO lines are never read. The 80 ms `tap` sleep runs on the single
reader thread, so `down`/`move`/`up` behind a tap wait for it
(`AurigaInputDevice.cpp`). The FIFO needs a live writer or `read()` returns EOF
and the reader exits; `scripts/auriga.sh` parks one long-lived `sleep` on it.

### Configuration that capture mode honours

`openauto-config/openauto.ini` is resolved from the process CWD.

| Key | Value | Effect |
| --- | --- | --- |
| `Video.Resolution` | `2` | 1280x720; also sets the touch geometry (`ServiceFactory.cpp` `configuredVideoGeometry`) |
| `Video.FPS` | `2` | 30 fps (`ServiceFactory` uses the same enum mapping) |
| `AudioChannel.MediaEnabled` / `GuidanceEnabled` | `true` | creates the corresponding sink |
| `AudioChannel.TelephonyEnabled` | `false` | the telephony block in `ServiceFactory` is commented out, so the service is never created |
| `Bluetooth.WirelessProjectionEnabled` | `true` | registers the Bluetooth service (`ServiceFactory.cpp` Bluetooth block) |
| `Bluetooth.AdapterAddress` | empty | selects `DummyBluetoothDevice` |
| `Audio.OutputBackendType`, `Input.EnableTouchscreen`, `Input.EnablePlayerControl`, `Bluetooth.AdapterType` | — | inert in capture mode only: the Qt/RtAudio backends and the Qt input device are replaced, so the values are never read on that path; a non-capture run uses them |

## AA session behaviour

Advertised services, built per AA entity: video sink, media/guidance/system
audio sinks, microphone source, sensor source, input source, and Bluetooth when
`WirelessProjectionEnabled` is true. The same call mints one capture session and
publishes `current` (`ServiceFactory.cpp`). Android Auto over Wi-Fi (WPP)
and telephony audio are not advertised (`ServiceFactory.cpp`).

Identity and ping values in the service-discovery response
(`openauto/src/autoapp/Service/AndroidAutoEntity.cpp`):

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
`display_name` is set once before the `connection_configuration` block, outside
`headunit_info`.

The ping values are advertised, not implemented: the pinger runs on a 5000 ms
timer with one outstanding request and rejects the entity once 5 pings are
unanswered (`openauto/src/autoapp/Service/AndroidAutoEntityFactory.cpp`,
`openauto/src/autoapp/Service/Pinger.cpp`).

Sensor service (`openauto/src/autoapp/Service/Sensor/SensorService.cpp`):
driving status `UNRESTRICTED`, night mode from the existence of
`/tmp/night_mode_enabled` (re-read on the 250 ms timer), GPS polled every 250 ms
and read only when `gps_open("127.0.0.1","2947")` succeeded. Without `gpsd` the
service logs `can't connect to GPSD` and never calls `gps_read`.

Bluetooth service (`BluetoothService.cpp`): with the dummy device
(`DummyBluetoothDevice.cpp`; `isAvailable()` returns `false`) it advertises
`car_address=""` and `BLUETOOTH_PAIRING_UNAVAILABLE`. A pairing request always
gets `STATUS_SUCCESS`, `already_paired=false`, then authentication data with PIN
`123456`.

### First AA entity fails with `AASDK Error 10`

Symptom: the first entity after a start dies with `AASDK Error: 10` (native code
1 or 2); OpenAuto quits it, reconnects, and the next entity projects. The stored
logs show two shapes, and the failure is not tied to one stage:

- during setup, before `Version Received`: the services have started and the
  channel errors arrive with no version response
  (`logs/openauto-mac-20261029-074101.log:55-65`, native code 1);
- after full negotiation: version response, SSL handshake, service discovery and
  channel setup all succeed, a Bluetooth pairing request and
  `sendBluetoothAuthenticationData` happen, and the first channel error is
  `MEDIA_SINK_VIDEO` immediately after `onMediaChannelStartIndication`
  (`logs/openauto-mac-20261029-072459.log:57` version, `:128-133` pairing and
  authentication data, `:137-148` the error burst).

Cause: `unverified`. Neither shape names a trigger: the setup shape shows no
Bluetooth activity at all, and the negotiated shape does not show what the dongle
rejected. The dongle-side USB transfer fails; the log stops there.
Workaround: let OpenAuto reconnect; if the dongle stays in AOA, replug it.
Observed on 2026-10-29: the repeating shape was the phone's `Enable after unlock`
prompt. If it times out, the dongle resets again about every 40 s. Accept the
prompt on the phone during the first connect after a cold boot. To avoid the
prompt, enable `Start Android Auto while locked` in the phone's Android Auto
settings, or keep the phone unlocked for the first connect.
Location: `logs/openauto-mac-*.log`; `App.cpp` (`onAndroidAutoQuit`,
`waitForDevice`).

## Threading and the real-time boundary

`autoapp` runs one Qt main thread (`qApplication.exec()`), four
`io_service.run()` threads and four libusb event threads
(`openauto/src/autoapp/autoapp.cpp`). Each service owns a
`boost::asio::strand` and hands the same strand to its aasdk channel, so channel
receive, the queue copy, ACK send and `stop()` are serialized per service.
`AurigaInputDevice` adds one raw reader thread on stdin; `AurigaAudioInput` and
`SensorService` use `deadline_timer` callbacks, not threads.

Media flow control: each media channel requests `max_unacked=1`
(`VideoMediaSinkService.cpp`, `AudioMediaSinkService.cpp`). The media ACK
is sent *before* the sink is asked to accept the buffer
(`VideoMediaSinkService.cpp`, `AudioMediaSinkService.cpp`), and
the sink's `write()` only copies into a bounded in-memory queue
(`AurigaWriter.hpp`). No media buffer touches the disk on the channel
strand and no disk latency sits in the flow-control window, so a slow disk cannot
stall the phone's next frame (`NFR-01`). Channel open and stop still open,
truncate and close the file once, on the strand, before the writer starts.

Each sink owns one writer thread that drains that queue to the segment file,
flushes per access unit and performs rotation, retention bookkeeping and the WAV
header rewrite (`AurigaVideoOutput.cpp`, `AurigaAudioOutput.cpp`). The queue is
bounded at 240 chunks and 64 MiB (`AurigaWriter.hpp`); when a sink cannot keep
up the oldest chunk is dropped and counted, never blocked on, and the first drop
plus every 100th is logged. The video writer then skips deltas until the next
IDR (re-emitting SPS/PPS) so a dropped frame does not leave an undecodable
reference chain in the file. `stop()` drains the queue and joins the writer
thread before closing the file, so a normal stop still finalizes the WAV header.

`AurigaSessionManager` mints the session and publishes `current` on the
entity-creation path. `noteRotation` rewrites `manifest.json` from the sink's
writer thread, at most once per 4 GiB per stream (`AurigaSession.cpp`;
`AurigaVideoOutput.cpp`, `AurigaAudioOutput.cpp`).

### A media sink reopened after `stop()` writes nothing

Symptom: a second channel open on an entity that already stopped its media sink
reports success and the segment file stays empty.
Cause: `AurigaWriter::start()` returns without spawning a writer thread once
`stopping_` is set (`AurigaWriter.hpp`), while `AurigaVideoOutput::open()` and
`AurigaAudioOutput::open()` still return `true`; the media then queues and is
never written. Whether any AA entity reopens a media channel after shutdown is
`unverified`: no log shows it, and the entity is recreated per session.
Workaround: one entity per pair; restart the pair instead of reusing an entity.
Location: `AurigaWriter.hpp` (`start`, `append`), `AurigaVideoOutput.cpp`,
`AurigaAudioOutput.cpp` (`open`).

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

## Runtime

`scripts/auriga.sh {start|restart|stop|status|open|tap}` is the only runtime
entry point. `openauto-config/run.sh` only execs `autoapp` with the environment
it is handed.

| Verb | Effect |
| --- | --- |
| `start` | creates the FIFO and its writer (reaping stale writers first), starts `autoapp` (offscreen capture), starts the stream server with the configured ports, polls the HTTP and WS listeners, waits up to `AURIGA_SESSION_TIMEOUT` for the first AA session, starts `caffeinate`, writes the lock, opens the browser |
| `restart` | `stop` then `start`; the clean path after a stale pair or a dongle replug |
| `status` | pids of `autoapp` and the stream server, both listening ports, the dongle/phone USB IDs, the `current` session; exits non-zero unless both processes run |
| `stop` | SIGTERM to the pids in the lock (cmdline-checked), waits, SIGKILLs, `pkill` for `autoapp`/stream/FIFO-writer orphans, removes the FIFO and the lock |
| `open` | opens the browser at the HTTP UI when the stream server is listening; does not restart anything |
| `tap X Y` | writes one `tap X Y` to `AURIGA_INPUT_FIFO` in 1280x720 space; refuses when the FIFO or `autoapp` is missing |

- `status` also reads the USB product IDs from `ioreg`: dongle `2717:ff40`
  before the AOA switch, `18d1:2d00` while projecting, phone `04e8:6860`. A
  live pair with the dongle back at `2717:ff40` is not projecting; `restart`
  is the first recovery step.
- The lock is `<capture-dir>/.auriga.lock`, one `role pid` line per component.
  `start` refuses while a live pid is in it, and refuses a running `autoapp` of
  the same build. The exclusive scope is the host, not one capture directory:
  when the lock names no live process, `start` still falls back to a host-wide
  `pgrep` for `autoapp` and the stream server and refuses on either match. The
  lock is written after readiness, so it names a pair that came up.
- `AURIGA_CAPTURE_DIR` (default `<repo>/captures-mac`),
  `AURIGA_INPUT_FIFO` (default `/tmp/auriga-in`), `AURIGA_HTTP_PORT` (8080) and
  `AURIGA_WS_PORT` (8081) are resolved once in `scripts/auriga.sh` and exported
  or passed on the command line. `openauto-config/run.sh` has no defaults and
  fails without them, so the FIFO the browser writes and the FIFO `autoapp`
  reads cannot diverge. The page learns the WS port from `config.json`, which the
  stream server serves on the HTTP port.
- Readiness is a poll of both listen sockets (`nc -z`, 20 s,
  `AURIGA_READY_TIMEOUT`). A stream server that dies, for example on
  `EADDRINUSE`, is reported with its log tail instead of a "started" banner.
- Sockets are not an AA session: with the dongle still at `Waiting for device...`
  both listeners are up and the canvas stays blank. `start` therefore also waits
  up to `AURIGA_SESSION_TIMEOUT` (10 s) for a `<capture-dir>/current` target that
  differs from the one seen before the start (a pointer left by an earlier run is
  not this run's session) and prints either the session name or
  `session: none yet`; the wait never fails the start, because starting before
  the phone connects is legitimate.
- The FIFO writer is one long-lived `sleep` holding the write side open; EOF
  would stop the input reader for the rest of the run. A writer left over from a
  previous run is killed before the FIFO is recreated, so it cannot hold the old
  inode.

## Verification

```bash
cmake --build build-aasdk-mac --target aasdk -j8
cmake --build build-openauto-mac --target autoapp -j8
./scripts/auriga.sh start
./scripts/auriga.sh status
pgrep -fl "autoapp|auriga_stream"
adb -s <PHONE_SERIAL> shell svc usb getFunctions          # expect: mtp
ioreg -p IOUSB -l -w 0 | grep -E 'o (AutoLink|SAMSUNG_Android)@|"idProduct" = (26720|11520|11521|65344)'
tail -20 "$(ls -t logs/openauto-mac-*.log | head -1)"  # Version Received + pings
ffmpeg -loglevel info -i captures-mac/current/video.h264 -f null - 2>&1 | tail -1
```

Expected: dongle `18d1:2d00`, phone `04e8:6860` and `svc usb getFunctions` =
`mtp`, at least one `Version Received: 256.1792`, and a growing video file under
`captures-mac/current/` (the symlink to the live `session-<id>/`; `current` only
exists after the first AA session of the current code).
