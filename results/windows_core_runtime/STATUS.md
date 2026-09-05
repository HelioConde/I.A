# WCRE-1 Status

- Operational status: `PASS`
- Hypothesis `ENG-CORE-001`: `SUPPORTED`
- Recommendation: `KEEP` as an opt-in Windows runtime optimization
- Canonical matrix: `matrix-20260821T091306Z-95bf26ce26`
- Persistent backend: official `llama-server.exe` from llama.cpp commit `217df17ac30ba2a8c374088772f81926cc5beee3`
- Experimental runtime SHA-256: `ecf6207498a81df80ac753c60243e9a2fbdf9f046c9e8195a61a83e507cc7dc0`
- Baseline runtime SHA-256: `b89490a2f25e3d573db8eff43080188d04996b958cdabfef3497a940337bf685`
- Warm Core-only TTFT improvement: `955.68 ms / 86.42%`
- Core-only median total-latency improvement: `1269.94 ms / 78.68%`
- Sustained: `1205.00 s / 93 queries / STABLE`
- Cross-query context leak: `false`
- Cleanup: `PASS`, zero orphan server processes
- Default Core mode changed: `false`
- Phase 4E-W modified: `false`
- Phase 4F started: `false`
- Phase 5 or prefetch started: `false`

See `SUMMARY.md` and `summary.json` for the complete measurements and immutable run IDs.
