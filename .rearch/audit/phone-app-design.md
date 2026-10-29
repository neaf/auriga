# Audit: phone-app-design

Scope: the phone-side AA mega app design branch (`PHONE-APP.md`) and the `README.md` claims that describe or depend on it. Zero implementation exists in this repo for this aspect; every "code" claim below is verification of the *other* side of the contract (OpenAuto/aasdk) that the design assumes.

## Coverage
| File | Lines | Read fully |
| --- | ---: | --- |
| README.md | 389 | yes |
| PHONE-APP.md | 418 | yes |

Total: 807 lines.

## Functional behavior
The aspect describes intent, not behavior. Statements below are the requirement candidates, with the status of the code that would have to satisfy them.

- F1: The phone runs the AA phone role (wireless: BT RFCOMM WPP bootstrap, join dongle AP, TCP/TLS, AA 1.7, video/audio/input channels). Evidence: PHONE-APP.md:88-102. Status: dead — no code, no vendored AARE, no submodule (`ls` root; only `openauto/`, `aasdk-upstream/`, `capture/`, `stream/`).
- F2: The head unit (OpenAuto/aasdk) is the TLS *client* and the phone is the TLS *server*. Evidence: code — `aasdk-upstream/src/Transport/SSLWrapper.cpp:97-102` returns `TLS_client_method()`. Confirms PHONE-APP.md:96,180. Status: active.
- F3: The head unit does not verify the peer (phone) certificate. Evidence: `aasdk-upstream/src/Transport/SSLWrapper.cpp:139` `SSL_set_verify(ssl, SSL_VERIFY_NONE, nullptr)`. Status: active.
- F4: OpenAuto does not advertise the WPP service; the dongle, not the head-unit host, is the WPP/BT endpoint. Evidence: `openauto/src/autoapp/Service/ServiceFactory.cpp:124` commented out, with the reasoning comment at `:118-122`. Confirms README.md:37-38. Status: active.
- F5: The AA display name seen by the phone is OpenAuto's hardcoded `Crankshaft-NG`. Evidence: `openauto/src/autoapp/Service/AndroidAutoEntity.cpp:182`, `:196-202`. Confirms README.md:35-36. Status: active.
- F6: The custom car UI is rendered by the phone into a private `VirtualDisplay` + `Presentation` feeding the encoder input surface, no `MediaProjection` consent. Evidence: PHONE-APP.md:121-142. Status: unclear — all claims are about AARE internals that are not present in the repo.
- F7: Audio is split: nav TTS on the AA guidance channel, Spotify on the media channel. Evidence: PHONE-APP.md:167-176. Status: dead (no code).
- F8: Pi car server roles: CAN/OBD-II gateway, vehicle state to phone, librespot PCM over USB, power sequencing. Evidence: PHONE-APP.md:284-334. Status: dead (no code; no `pi/` or CAN sources in repo).

## External facts and quirks
- X1: TLS version is not pinned on the head-unit side. `SSLWrapper.cpp:97-102` selects `TLSv1_2_client_method()` only for OpenSSL < 1.1.0, else `TLS_client_method()` — i.e. negotiation, not "TLS 1.2". Symptom: an AARE implementation pinned to TLS 1.2 may see a 1.3 ClientHello. Source: code.
- X2: Peer certificate is never inspected or logged. `SSLWrapper.cpp:139` sets `SSL_VERIFY_NONE`; no `SSL_get_peer_certificate` call anywhere under `aasdk-upstream/src` (grep). Quirk: the doc's decisive experiment (log the peer cert) is not implementable without new code. Source: code.
- X3: The head-unit side presents a static cert/key from `aasdk-upstream/cert/headunit.crt|headunit.key`, loaded at `Cryptor.cpp:61-65`. If the car or dongle checked *this* cert, these files would be the lever. Source: code.
- X4: The dongle reports AA protocol 1.7 and `256.1792` while aasdk upstream now ships `AASDK_MINOR = 7` (`aasdk-upstream/include/aasdk/Version.hpp:22-23`), so protocol version is not a blocker for the phone side if AARE also speaks 1.7. Source: code + README.md:160,249.
- X5: Bluetooth pairing/DB state is a hard prerequisite for any phone→dongle test. The 207-byte DB stopped BT advertising entirely; deleting `btapp.db`/`btapp.bk` and re-pairing (6-digit comparison) restored it, and the dongle recreated a 33-byte DB. README.md:226-242. Source: capture/log per README; not re-verified in this audit.
- X6: First AA entity after a fresh dongle boot resets with `AASDK Error 10` on the dongle's BT pairing request, then reconnects on the second session. README.md:84-87, 254-256. Source: log per README.
- X7: AARE, Shizuku, librespot, Spotify capture policy and the "Google phone cert expires end of 2026" claim are all external and unverifiable from this repo. No AARE checkout, no pinned commit, no evidence file. PHONE-APP.md:184-218, 222-256, 272-282, 391-418. Source: unverified.
- X8: Repo root has no `LICENSE` file (`ls` root), while the design proposes forking GPL-3.0 AARE and notes the obligation at PHONE-APP.md:411. Source: code/repo.

## Doc and code inconsistencies
- D1: PHONE-APP.md:96 says "TLS 1.2"; `SSLWrapper.cpp:97-102` negotiates (TLS 1.3 likely with OpenSSL 3 on macOS). The wire step should say "TLS, version negotiated".
- D2: PHONE-APP.md:190-194 builds a three-row table on "who checks the phone cert", and PHONE-APP.md:204-207 calls peer-cert logging "a small instrumentation change". Code reality: verification is off (`SSLWrapper.cpp:139`) and no peer-cert API is used, so the test needs real code, and rows "dongle lenient" and "dongle strict" are indistinguishable from OpenAuto alone.
- D3: PHONE-APP.md:63 labels the dongle "AA head unit to phone", while PHONE-APP.md:14 and README.md:39-43 label it an AA-layer relay that *forwards* the head unit's service discovery (proved by the phone seeing `Crankshaft-NG`). The two models imply different cert owners and different WPP handling; the doc never resolves which one holds.
- D4: PHONE-APP.md:94 ("Join the dongle's AP with `WifiNetworkSpecifier`") never states where the WPA2 passphrase comes from. README.md:159 has it as `12345678`; on a real phone the system AA stack already stored it. An AARE-based app has no stated source for it (WPP `WifiInfoResponse` is the car→phone credentials message, PHONE-APP.md:92-93, which is the opposite direction here).
- D5: PHONE-APP.md:299 ("The Pi gets a DHCP address") and PHONE-APP.md:302 ("Use a static IP on the Pi") are left as simultaneous advice.
- D6: PHONE-APP.md:196-207 test procedure has no control for the known dongle BT-pairing reset (README.md:84-87). A first-session failure will be mis-read as a cert rejection.
- D7: README.md:330-337 summarizes the branch but omits two facts the design treats as binding: the AARE base and its GPL-3.0 obligation (PHONE-APP.md:29-32, 411).
- D8: The cert-expiry claim (PHONE-APP.md:215, "end of 2026") has no date of recording; README.md:139 records phone AA `17.9.664044-release`, so the expiry statement is tied to no version.
- D9: README.md:12 is dated `2026-10-28` and contains no pointer to `PHONE-APP.md` status date `2026-10-29`; the two docs' status headers are not comparable.

## Assumptions to revalidate
- A1: "The dongle's phone-certificate policy decides the project" (PHONE-APP.md:19-20, 39-40, 188). Baked into the go/no-go. If the dongle is transparent and OpenAuto is the only other endpoint, then no one checks the cert in this rig (F3) and the real blocker is WPP/BT behaviour, not certs. Evidence points both ways; unresolved.
- A2: "AARE works on this phone and speaks AA 1.7." No commit, no minSdk/targetSdk, no Android 16 note (PHONE-APP.md:104-119, 391-398). If AARE's version negotiation tops out lower or its `Presentation` path fails on One UI, the whole render plan (F6) is void.
- A3: "A `Presentation` on a private `VirtualDisplay` keeps rendering with the phone screen off" (PHONE-APP.md:135-139). Baked into the no-MediaProjection claim. Samsung background/presentation policies can pause it; nothing in the repo tests this.
- A4: "The dongle keeps relaying AA-layer messages from whatever answers on its USB side" (README.md:39-43). Baked into the topology at PHONE-APP.md:56-74. If the dongle instead expects the exact `Crankshaft-NG`-style service set, AARE's different service set changes dongle behaviour.
- A5: "Pi is USB host, phone is USB device sharing cellular" (PHONE-APP.md:296-307). Baked into the Pi↔phone link. Untested; also contends for the phone's single USB-C port with charging (PHONE-APP.md:303-304).
- A6: "Android keeps cellular as the internet path while joined to a local-only dongle network" (PHONE-APP.md:78-84). Baked into both networks. If the phone drops cellular during the AA session, librespot (PHONE-APP.md:281-282) dies.

## Bugs
- None in code: no implementation exists for this aspect. The doc-level defects that will cause wrong work are D2, D3, D4, D6.

## Dead code, leftovers, stale comments
- L1: `openauto/src/autoapp/Service/ServiceFactory.cpp:118-122` — stale TODO ("What is WiFi Projection Service?") plus speculation; the service is commented out at `:124`. This is the code the phone-app design's "dongle is the WPP endpoint" claim rests on.
- L2: `openauto/src/autoapp/Service/WifiProjection/WifiProjectionService.{cpp,hpp}` — compiled but unreachable from `ServiceFactory::create()`; dead path on the head-unit side.
- L3: PHONE-APP.md:19-20, 39-40, 364-365 — the cert go/no-go is stated three times; README.md:336 and NEXT-SESSION.md:36-37 restate it a fourth and fifth time. No single source of truth.
- L4: PHONE-APP.md:346-360 "Phone-only vs Pi4-in-the-AA-path" table repeats the prose of PHONE-APP.md:42-54 with slightly different framing.
- L5: `capture/src/WifiProjectionCapture.cpp:77-80` hardcodes SSID `AutoLink-A512` / password `12345678` — the same credentials PHONE-APP.md:94 assumes but never names.

## Improvement areas
- I1: Pin AARE by commit and version in PHONE-APP.md. Every path claim (`aap/`, `app/.../video/`, `TouchMapper`) is unverifiable and will rot; a rearch cannot plan against it.
- I2: Replace the "who checks the cert" table (PHONE-APP.md:190-194) with one falsifiable experiment: add `SSL_get_peer_certificate` logging next to `SSLWrapper.cpp:139` and print subject/issuer. Mechanism: the current code discards the peer chain, so no observation is possible today.
- I3: Make the first phone-app test distinguish three failures that currently look identical: dongle BT-pairing reset (README.md:84-87), WPP bootstrap close (README.md:257-273), TLS/cert rejection. Requires logging AA control-channel auth status separately.
- I4: Consolidate the phone-app status into one doc. It is currently spread over README.md:330-337, PHONE-APP.md, NEXT-SESSION.md:35-37, DEVELOPING.md:149, RUNBOOK.md and openauto-plan.md, with no dates aligned.
- I5: Add a root `LICENSE` before any AARE fork lands here; the GPL-3.0 obligation (PHONE-APP.md:411) has no counterpart file.
- I6: The cert-expiry date (PHONE-APP.md:215) is a fixed 2026-12 cliff; record the date it was verified and who verified it, otherwise the fallback path looks alive long after it dies.
- I7: State the dongle AP PSK source explicitly (D4). A hardcoded `12345678` and a WPP-derived credential lead to different join code and different failure modes.

## Interfaces
- Exposes: nothing executable. The doc defines two planned interfaces: phone↔dongle AA 1.7 over TLS (PHONE-APP.md:88-102) and phone↔Pi over USB tether carrying CAN telemetry and 48 kHz/16-bit stereo PCM with timestamps (PHONE-APP.md:272-281, 296-307, 329-334).
- Consumes: from the head-unit aspect — AA 1.7 protocol, TLS client role, service discovery shape (`AndroidAutoEntity.cpp:182-212`), non-advertised WPP (`ServiceFactory.cpp:124`), `capture/` as a reference implementation. From the dongle — BT Classic pairing DB (README.md:201-242), 5 GHz AP `AutoLink-A512` WPA2 `12345678` (README.md:159), AA-layer relay behaviour (README.md:39-43). From the stream aspect — the current H.264/PCM transport is a stand-in for the phone app's own output.
- Threading: none defined. The design defers encoder/audio/session threading entirely to AARE (PHONE-APP.md:104-119) and does not state which thread owns the Pi PCM socket, the CAN decoder or the encoder surface.

## Open questions for the user
- Q1: Is the phone app still a live goal, or is the dongle+OpenAuto capture rig the product? `PHONE-APP.md:3` says design note only, but README.md:314-328 sets a different next plan (`auriga-headunit` headless emulator).
- Q2: Which phone? PHONE-APP.md:388-389 asks whether a dedicated rooted car phone is preferred; the answer changes every audio option in PHONE-APP.md:237-244.
- Q3: Is a Pi 4/5 available? PHONE-APP.md:311 requires a 5 GHz Pi; the rig only has a Pi 3B (README.md:133).
- Q4: Does the cert test need to be done at all before the `auriga-headunit` work (README.md:314-326), or can it wait?
- Q5: Should the phone-app design survive rearch as a doc, or be archived as an unused branch and dropped from the doc set?
