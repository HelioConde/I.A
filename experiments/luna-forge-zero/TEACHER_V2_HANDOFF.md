# Luna Forge Zero V2 — Teacher Core / Brain-SSD

Status 2026-10-28: **working local experimental package**, not merged or enabled in the main Luna runtime.

## What was validated in this continuation

- Deterministic code challenge curriculum: JavaScript and GDScript, train/holdout split, prompt isolation.
- Brain-SSD inference trial uses the original MiniCoder V0 checkpoint, lazy model selection, read-only knowledge mapping, weight SHA-256 provenance.
- JavaScript evaluation via `node --check` **parses only**; generated code is not executed.
- Human review gate: rejected/pending/holdout/syntax-failing outputs are not eligible for training.
- New candidate optimizer: runs only with `--confirm`, reads reviewed train-only examples, and saves a separate version instead of overwriting baseline.
- Local ZIP tests: **24/24 passed** (5 Brain-SSD bridge + 15 teacher + 4 optimizer); a real 5-challenge MiniCoder V0 trial passed **0/5** JavaScript syntax checks. This is an explicit capability limitation, not a hidden error.

## Artifact handoff

The complete, tested V2 implementation (teacher_core.py, train_approved.py, test_teacher_core.py, test_train_approved.py, model weights, reports and commands) was delivered in the conversation artifact:

`Luna_Forge_Zero_BrainSSD_V2_2026-10-28.zip`

The ZIP is not currently committed as a binary GitHub artifact; **this branch does not yet include those four V2 source files**. Keep this PR in draft. The next repository integration should add those exact tested sources plus a dedicated Windows/Linux CI check, then evaluate against real Godot/Chromium gameplay tasks. Do not promote MiniCoder based on synthetic classification or loss alone.

## Brain-SSD boundaries

- SSD-backed memory mapping is not an OS physical RAM cap.
- Teacher V1 is a rule-driven curriculum/orchestrator, not a powerful neural teacher model.
- The first 5/5 failed syntax checks establish a trustworthy baseline. No self-training or model-weight changes happened during the real inference trials.
- The controlled optimizer was exercised with synthetic fixtures **only** to prove model-version isolation and gradient updates. This does not establish better game generation.
