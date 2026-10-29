# Deviations

- **P1: topic docs document present behaviour only.** `architecture.md` and
  `docs-plan.md` assign the topic docs the target interfaces (per-session dirs +
  `manifest.json`, single viewer + keyframe request, `scripts/auriga.sh`,
  `scripts/build.sh`, `Auriga` identity) that P3-P7 implement, but `phases.md`
  gives a doc touch only to P7. Writing those as present-tense facts at P1 would
  be false and unsourced.
  Change: P1 docs state verified present behaviour; target-only contracts are
  not described. Added the doc files to the phases that change them: P3 gets
  `docs/Stream protocol.md` and `docs/Android Auto head unit.md`, P4 gets
  `docs/Stream protocol.md`, P5 gets `docs/Android Auto head unit.md` and
  `docs/Stream protocol.md`. Each phase adds its contract section when the code
  lands.

- **P1: build-green command block corrected.** The block named
  `stream/server.py` and `stream/lib/*.py`, which do not exist before P2, and
  passed `scripts/*.sh` to `py_compile`. Replaced with
  `py_compile $(find stream scripts -name '*.py')`; P7 adds `tools/*.py` after
  the move.

- **P1: audit facts corrected against the tree.** Recorded so later phases do not
  copy the audit text:
  - `patches/openauto-capture.patch` does not touch `App.cpp`. Patches 2
    (`openauto-macos`) and 3 (`openauto-auriga-usb-filter`) do.
  - AA identity block (`AndroidAutoEntity.cpp:181-202`): `display_name`
    `Crankshaft-NG`; `headunit_info` make `Crankshaft`, model `Universal`, year
    `2018`, vehicle_id `2024110822150988`; `head_unit_make` `f1x`,
    `head_unit_model` `Crankshaft-NG Autoapp`, build `1`, version `1.0`. FR-HU-10
    quotes only the `head_unit_*` pair.
  - TLS certificate and key are compiled-in PEM constants
    (`aasdk-upstream/src/Messenger/Cryptor.cpp:253,273`).
    `aasdk-upstream/cert/headunit.crt|key` is installed by CMake but not read by
    `Cryptor`.
  - `scripts/aoa_probe.py` sends `Auriga`, `Auriga Pi Headunit`,
    `Auriga AA capture`, `1.0`, `https://auriga.invalid`, `auriga-pi`, not the
    set quoted in `audit/dongle-hardware.md#D5`.
  - `btapp.db` 207-byte form: 8-byte prefix, then seven 29-byte blocks
    `13 00 01 04` + 16-byte key (+ 6 bytes) starting at `0x08, 0x25, ...`,
    trailer `00 42 54 4c f3`. The audit's one-record description does not cover
    the repeated blocks, so the doc states only the verified 29-byte stride and
    the two prefixes at `0x00`/`0x3a`. The 33-byte form is one block plus
    trailer `00 42 54 0a 53`.
  - `videoInfo.galaxy`/`.active` are invalid (zero width, height, SPS, PPS, tag);
    `btapp.db.galaxy-fresh` is 33 B, gitignored/untracked, current but
    `unverified`.
