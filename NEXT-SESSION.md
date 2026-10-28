# Next session handoff

## Current state (2026-10-28, end of session)

**Working end-to-end:**

- Full OpenAuto (`opencardev/openauto` `main` @ `4cc739b8`) + aasdk 1.7 on the
  Pi projects the Galaxy S25 through the AutoLink dongle.
- Captures: 1280x720 H.264 video, 48 kHz/16-bit stereo media audio, JSONL touch
  input.
- The Mac client works: `stream/auriga_stream.py` on the Pi tails the capture,
  Brave at `http://localhost:8080` displays video via WebCodecs and audio via
  WebAudio, and taps go back to the AA input FIFO.
- Start/stop scripts: `scripts/pi-start.sh`, `pi-stop.sh`, `mac-start.sh`,
  `mac-stop.sh`.
- BT recovery: deleting `btapp.db`/`btapp.bk` and re-pairing restored BT
  advertising. The dongle recreated a 33-byte DB (new key); backup
  `dongle-backup/btapp.db.galaxy-fresh`.

**Known issues / next work:**

1. First AA session can reset on the dongle's AA Bluetooth pairing request
   (`AASDK Error 10`, USB transfer); OpenAuto reconnects and the next session is
   stable. Investigate the Bluetooth service / DummyBluetoothDevice.
2. Capture files truncate on a new AA session (`open` uses trunc). Add
   per-session filenames and rotation.
3. File sinks ignore AA timestamps, so streamed audio/video are not
   sample-synced. The long-term fix is a headless emulator feeding the stream
   directly from aasdk callbacks with timestamps.
4. AA display name is OpenAuto's hardcoded `Crankshaft-NG`; rename to Auriga.
5. Forwarding to a real head unit needs a Pi 4/5 (host + OTG) or a two-device
   relay.
6. The dongle is a **relay at the AA layer**, not a full terminator: the phone
   sees the head unit's `display_name` and service set. Head-unit behavior
   matters.

## Prompt to paste into the new session

```text
We are continuing the Auriga project in /Users/tomaszwerbicki/dev/auriga.

Read, in this order:
1. README.md
2. RUNBOOK.md
3. openauto-plan.md
4. stream/README.md
5. dongle-backup/README.md

State: full OpenAuto on the Pi projects the Galaxy S25 through the AutoLink
dongle; video/audio/input capture works; the Mac client (stream/auriga_stream.py
+ Brave at http://localhost:8080 over an SSH tunnel) streams live and accepts
taps. Start/stop scripts are in scripts/.

Goal: turn the working prototype into a stable headless head unit and then
forwarding. Priorities:
1. Build `auriga-headunit` from `capture/` + aasdk 1.7, matching OpenAuto's
   working service set (no WPP/telephony; test the Bluetooth variants),
   headless without Qt. Feed the stream protocol directly from aasdk callbacks
   with AA timestamps.
2. Per-session capture files and rotation; fix A/V sync.
3. Investigate the first-session reset on the AA Bluetooth pairing request.
4. Rename the AA display name to Auriga.
5. Forwarding later needs a Pi 4/5 or a two-device relay.

Constraints:
- No firmware flashing, factory reset, or dongle/phone writes/deletes without
  explicit approval. Ask before touching dongle config or phone settings.
- Keep the iPhone and OPPO BT/Wi-Fi off during AA tests.
- uhubctl may only disable the data port, not VBUS; use a physical replug for a
  cold boot.
- Pi 3B cannot be USB host and gadget simultaneously.
- Before each batch of commands, state the next 1-2 steps and wait for OK.
- Persist findings to the repo as you go.

Current hardware: Pi 192.168.2.2 / auriga-pi.local; dongle at 1-1.4.4 port 2;
BT/Wi-Fi AutoLink-A512; Wi-Fi password 12345678; Galaxy BT
5C:D3:3D:56:71:F4. OpenAuto build at ~/auriga/build-openauto; aasdk at
~/auriga/build-aasdk; capture at ~/auriga/captures-openauto; stream at
~/auriga/stream.
```

## Important files

- `README.md` — project state, findings, quick start.
- `RUNBOOK.md` — operational steps, BT recovery, rebuild, streaming.
- `openauto-plan.md` — full build/run/patch history and result.
- `stream/` — Pi WebSocket server + Brave client.
- `patches/openauto-capture.patch` — capture patch applied to OpenAuto.
- `openauto-config/` — run config and launch script.
- `scripts/` — Pi/Mac start-stop, `aa-tap.sh`.
- `dongle-backup/` — BT DB backups/restore rules (fresh 33-byte DB).
- `captures/` — local media artifacts (large files not in git).
