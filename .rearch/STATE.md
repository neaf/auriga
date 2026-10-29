# Rearchitect state

Project: Android Auto head unit + capture rig (OpenAuto on macOS, AutoLink dongle relay, local H.264/PCM stream).
Branch: rearch/2026-10-29
Base tag: rearch-base (bfd7903)
Stage: 5 (phase execution)
Phase: 1 of 7 (topic docs from audit facts), not started

## Done
- Stage 0 setup: branch/tag, baseline build + static checks, manual checklist
  M1-M8 recorded (user asserts all pass). `d3f7c7d`
- Stage 1 inventory: 7 aspects confirmed by user. `0c266ec`
- Stage 2 audits: 7 aspect reports + seams, all 72 tracked files covered.
  `33e7d48`
- Stage 3 requirements: 54 FR (47 kept, 11 dropped), 8 NFR, 8 CON; all open
  questions resolved. `5d6c8ce`
- Stage 4 architecture: 7 phases approved by user; cleanup moved to Stage 6.
  `a1ad814`

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

## Next prompt
```
Use the rearchitect skill. Continue from .rearch/STATE.md.
Next: Phase 1 (topic docs from audit facts).
```
