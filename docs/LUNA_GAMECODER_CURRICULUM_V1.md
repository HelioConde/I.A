# Luna GameCoder curriculum v1

This curriculum is a **suite of original exercise contracts**, not a model fine-tuning run.
It is deliberately separate from the skill-router Naive Bayes training.

## Included tasks
- Movement state update and gravity (FSM).
- Character landing collision, including no collision outside platform (debug).
- Subscribe/unsubscribe/emit with ordering (event bus).

`benchmarks/gamecoder_curriculum/tasks.json` describes behavior without exposing reference implementation.

## Evaluation safety
Candidate JavaScript must run in an isolated execution environment with strict resource and network limits. The repository metadata validator **does not execute candidate code**, and passing structural checks does not imply generated games work. Neither the Escudeiro benchmark nor third-party implementations are used as generated solutions.

## Next
Add isolated Node/Chromium evaluation with archived model-authored source, input traces and screenshots. Only after demonstrating executable code quality should curated, licensed and verified examples be considered for model fine-tuning. The existing model weights are unchanged.
