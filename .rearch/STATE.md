# Rearchitect state

Project: Android Auto head unit + capture rig (OpenAuto on macOS, AutoLink dongle relay, local H.264/PCM stream).
Branch: rearch/2026-10-29
Base tag: rearch-base (bfd7903)
Stage: 5 (phase execution)
Phase: 3 of 7 (capture session model), not started

## Done
- Stage 0 setup. `d3f7c7d`
- Stage 1 inventory: 7 aspects. `0c266ec`
- Stage 2 audits: 7 aspects + seams, all 72 tracked files covered. `33e7d48`
- Stage 3 requirements: 54 FR (47 kept, 11 dropped), 8 NFR, 8 CON. `5d6c8ce`
- Stage 4 architecture: 7 phases approved. `a1ad814`
- Phase 1 topic docs from audit facts. `8fb94d6`
- Phase 2 test harness + pure stream libs: 43 tests pass. `e834a3e`

## Decisions
- 2026-10-29: treat M1-M8 as passing at baseline; user call ("assume everything works").
- 2026-10-29: keep the 7-aspect split (no merge of build-and-tooling).
- 2026-10-29 Q1: drop Pi fallback; macOS-local is the only supported host.
- 2026-10-29 Q2: keep the dummy Bluetooth service as-is; investigate the
  first-session reset later; no WPP hardware test now.
- 2026-10-29 Q3: media-only PCM to the browser; guidance/system audio file-only.
- 2026-10-29 Q4: one browser viewer per session.
- 2026-10-29 Q5: per-session timestamped captures, rotate before 4 GiB, bounded.
- 2026-10-29 Q6: promote aasdk Version.hpp 6->7 and protobuf absl edits into patches.
- 2026-10-29 Q7: drop `capture/`.
- 2026-10-29 Q8: CarPlay mode is a runbook note only, no code path.
- 2026-10-29 Q9: drop the phone-app design branch.
- 2026-10-29 Q10: add a one-command patch-apply + build script.
- 2026-10-29: keep rename to Auriga; drop the USB-hub-error retry path.
- 2026-10-29: architecture and 7-phase plan approved as written.
- 2026-10-29: P1 deviations in `.rearch/deviations.md` (doc touches P3/P4/P5,
  build-green block corrected, six audit facts corrected).
- 2026-10-29: P2 deviations in `.rearch/deviations.md` (`stream/lib/__init__.py`,
  doc repoints, P3 now splits `stream/server.py`, P4 extends tests).
- 2026-10-29: manual checks after phases are treated as pass under the baseline
  assumption unless the user asks to run them.

## Next prompt
```
Use the rearchitect skill. Continue from .rearch/STATE.md.
Next: Phase 3 (capture session model).
```
