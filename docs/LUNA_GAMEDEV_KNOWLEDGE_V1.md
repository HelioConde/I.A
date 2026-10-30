# Luna GameDev — knowledge catalog v1

This is an **initial curated manifest**, not a claim that repositories were downloaded, ingested, validated for build correctness, or used to fine-tune model weights.

## Role separation
- **Luna Core**: plans game tasks, retrieves approved knowledge, evaluates outcomes and preserves provenance.
- **Luna GameCoder**: writes original game files and fixes them using tool feedback.
- **Evaluator**: runs isolated static, runtime, browser, visual, and requirement tests. Never credits evaluator-written game code to Luna.

## Source catalog
`knowledge/game_dev/sources.json` lists ten third-party references, their declared GitHub license metadata, priorities, and intended roles. Confirm licenses, file-level notices, content provenance, and compatibility at a pinned commit before ingestion. Attribution and required notices must be retained.

- **Architecture / skills**: OpenGame (Apache-2.0); Claude Code Game Studios (MIT). Adapt concepts to Luna rather than running Claude-specific hooks.
- **Candidate learning examples**: Godot 2D Platformer, Flatris, CraftyJS, PGZero Platformer, Pula-Pula, Hunter Adventures.
- **Research only**: DeepLearningFlappyBird (historic DQN approach; not a modern drop-in dependency).
- **Held-out evaluation**: Escudeiro. **Never** index, retrieve, fine-tune on, or reveal its solution to the generator before benchmark completion.

No external repository is installed or executed by this change. All source IDs are scoped to their original owners.

## Skills
`knowledge/game_dev/skills.json` defines nine normalized capability contracts: GDD, backlog, FSM, event bus, engine conversion, debug, performance, shader, and asset prompting. These are **specifications**, not working implementations.

## Evaluation contract: Luna Arcade
1. Freeze the benchmark prompt, scoring rubric, model identifier, hashes, and allowed attempts.
2. Require **model-authored** JavaScript or GDScript with provenance.
3. Syntax/build validation before sandbox execution.
4. Browser/Godot runtime input and collision tests plus screenshots.
5. Score: build 20, mechanics 30, visual 20, repair 20, code quality 10.
6. Keep model output, logs, screenshots, and evaluator-originated scaffolding separately.
7. Publish only with explicit attribution and verified playable evidence; incomplete attempts remain incomplete.

Target for a future evaluation: 80+/100 across three new games. This is a proposed goal, **not an achieved benchmark**.

## Verification
```bash
python tools/validate_game_knowledge.py
python -m pytest tests/test_game_knowledge.py -q
```
These commands validate catalog integrity only. They do not measure the coding ability of any Luna model.

## Next development steps
- Pin source commits and verify file-level licensing and scope.
- Introduce opt-in retrieval with strict holdout filtering.
- Implement the skills as tool adapters, starting with GDD, backlog and debugging.
- Integrate rubric and runtime evidence with the existing `benchmarks/arcade_s1` and game-agent workflows.
- Compare real models under identical tasks; only then consider supervised fine-tuning.
