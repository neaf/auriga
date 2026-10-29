# Docs plan

Fate of every current doc plus the target doc set. Rules from
`references/docs-style.md`: topic docs are present-tense facts with
`symptom / cause / workaround / code location` per quirk, `unverified` marks, and
no history.

## Current docs → fate

| Current doc | Fate | Target |
| --- | --- | --- |
| `README.md` | rewrite (drop Pi/phone-app/capture sections, macOS-only, build/run/test) | `README.md` |
| `AGENTS.md` | rewrite (<60 lines, commands + pointers) | `AGENTS.md` |
| `DEVELOPING.md` | fold patch/build workflow facts | `docs/Build.md`, `AGENTS.md` |
| `MAC-PORT.md` | fold prerequisites + configure lines + macOS quirks | `docs/Build.md` |
| `RUNBOOK.md` | fold recovery/verify steps | `docs/AutoLink A512 dongle.md`, `docs/Android Auto head unit.md`, `README.md` |
| `openauto-plan.md` | delete (superseded, Pi-era, speculative) | — |
| `NEXT-SESSION.md` | delete (session handoff) | — |
| `PHONE-APP.md` | delete (dropped Q9) | — |
| `stream/README.md` | fold wire protocol + client behavior | `docs/Stream protocol.md` |
| `captures/README.md` | fold fixture provenance | `docs/Android Auto head unit.md` (one line) |
| `capture/README.md` | delete with `capture/` | — |
| `dongle-backup/README.md` | fold config-file layout + recovery; keep the data files | `docs/AutoLink A512 dongle.md` |
| `.rearch/*` | delete (Stage 6); FRs become `docs/requirements.md` | `docs/requirements.md` |

## Target doc set

| Doc | Scope |
| --- | --- |
| `README.md` | What it is; quick start; build/run/test commands; pointers to the docs below. |
| `AGENTS.md` | <60 lines: start/stop/verify commands, USB invariants, safety, doc pointers. |
| `docs/requirements.md` | FRs with IDs + status (kept/dropped), NFRs, external constraints. |
| `docs/architecture.md` | Modules, data flow, threading/real-time model, interfaces, traceability. |
| `docs/AutoLink A512 dongle.md` | USB IDs, `videoInfo` (364 B) + `btapp.db` (33/207 B) layout, CarPlay latch, ~22 s re-enumeration, recovery; which backups are valid (`videoInfo.galaxy` is invalid, `btapp.db.galaxy-fresh` is current). |
| `docs/Android Auto head unit.md` | AA 1.7/TLS/service set, the four/five patches, capture contract (session dir + manifest), reconnect, identity. |
| `docs/Stream protocol.md` | Wire framing (`>BQ` header, AVCC/PCM), session/manifest, single viewer, WebCodecs/WebAudio quirks. |
| `docs/Build.md` | Boost 1.85, CMake 4.4 policy 3.5, taglib/absl/protobuf/openssl, patch order, `scripts/build.sh`, clean-rebuild verification. |

## Fact notes carried into the topic docs

- Dongle: `2717:ff40`→`18d1:2d00`, AOA v2, 2 bulk endpoints, AA 1.7 (`256.1792`),
  BT `AutoLink-A512 ED:A2:A4:94:4F:B8`, Wi-Fi AP 5 GHz WPA2 `12345678`, CarPlay
  `05ac:12a8`. `videoInfo.galaxy` has zeroed width/height/SPS (do not restore);
  current pairing key is the 33-byte `btapp.db.galaxy-fresh` (`unverified` until
  a post-projection snapshot is taken).
- Head unit: OpenAuto `4cc739b8` + aasdk `9bf6adf`; patches
  `openauto-capture` → `openauto-macos` → `openauto-auriga-usb-filter` →
  `openauto-auriga-gps-guard`, plus `aasdk-usb-filter` and (new)
  `aasdk-version-absl`. TLS client, `SSL_VERIFY_NONE`, static headunit cert.
  First-session `AASDK Error 10` reconnect is `unverified` as BT-pairing-attributed.
- Stream: 1280x720 H.264 Baseline 3.1, 4-byte start codes, IDR ~1800 frames;
  WebCodecs needs a secure context (`localhost` OK, `ws://` from HTTPS is not).
