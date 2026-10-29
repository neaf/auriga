# Test fixtures

Synthetic inputs for `tests/`; no capture data from a real session.

| File | Content |
| --- | --- |
| `sample.h264` | Annex-B, 4-byte start codes: SPS, PPS, AUD, IDR, two deltas, IDR, AUD, delta. NAL layout only; not decodable video. |
| `manifest.json` | Full `manifest.json` sample: session, geometry, four segment counts. |
| `manifest-no-geometry.json` | Session and segment counts only; the parser applies the geometry defaults. |
| `manifest-invalid.json` | Truncated JSON; the parser returns `None`. |
