# Luna / Brain-SSD — Grand Chase research, licensed sources and original training

Date: 2026-10-28. User-supplied reference URLs have been inspected with the GitHub connector. **This is not a copy of Grand Chase**, and no client file, asset, extracted source or unlicensed game code is approved for training.

## Source decisions

| Repo | Pinned commit | License evidence | Classification | In weight training? |
|---|---|---|---|---|
| Divv10/GcResourcesApp | f3bee7ecd0e94add31f71dfcc4b799172bff0e9c | MIT license | C# WPF resource management tool | No; optional separate tooling study |
| SkelletonX/GrandChaseIV | add799c80c0eb6636e6a0f1ed2fd3f1532cc74c0 | None found at repository root | C# Season 4 emulator | No |
| grandchaseproject/GrandChase-Playtest | 4f69c46c17132a0c7da100e2b5b772c7d4f093ef | None found | Archived commercial client EXE, DLLs, audio, textures and models | **Exclude fully** |
| rocverde/GrandChaseSeasonV | f9f32c46d7e494216b8c01dd113bc32776489f79 | None found at repository root | Java+SQL emulator | No |
| Diqxy1/grandchase | f7f8ac58b28a8992615beb4cc280229581212ddd | None found at repository root | C++ client + server | No |
| rockerudon/grandchase_toolkit | 99abf89aa27e5f72ab994cf833220cdfd1ada97c | MIT | KOM/Lua decrypt/decompile utility; includes crypto keys and third-party components | No; unrelated to gameplay |
| rage123450/GrandChasePacketDecoder | 90cce432c7e2f50692ce36c72bafa0411b2329f9 | None found at repository root | C# protocol decoder | No |
| Raitou/GrandChaseSeasonEternal | 1729b697db74a4d295902835c311504ef4269490 | None found at repository root | Partial Java emulator; legal notice in README | No |
| AngelsOnlineDev/grandchase-kom-extractor | 2c09ea436389fa6b94df3ad5590e4c032148b0bc | MIT + third-party license notices | KOM extractor, key tables and decompiler | No |

The published MIT license of a tool does not grant rights to extracted or bundled proprietary game data. Unlicensed files are not ingested. None of these nine repositories may be bulk cloned, executed, decrypted or copied by this research pipeline.

See [the machine-readable catalog](../experiments/luna-forge-zero/grandchase_research_catalog.json) and [license/holdout gate](../experiments/luna-forge-zero/grandchase_reference_gate.py).

## What the Luna GameCoder actually learns

A *new, original* teaching curriculum formalizes genre-level requirements, not copied Grand Chase implementation:

- Platform acceleration and jumping physics
- Original 3-hit combo timing
- Hitboxes, damage/knockback and short invulnerability
- Patrol AI and Godot CharacterBody2D patterns

Eight original reference solutions are in the **training** split; four separate tasks (ledge recovery, boss phases, enemy sensing and one-way platforms) are **holdout** with no answers provided to the model. These training examples are our own code, not redistributions of game-client code. The independent external MIT gaming dataset (Godot official demos, Godot roguelike, Phaser examples) continues to supply genuine third-party game code for the research model. No names, characters, story, stages, sprites, sounds or maps of Grand Chase are included.

## Commands

```powershell
cd C:\Users\helio\Documents\I.A\experiments\luna-forge-zero
python grandchase_reference_gate.py audit
python grandchase_reference_gate.py export --out external_data/original_curriculum_train.jsonl
python github_corpus.py collect --out external_data
python train_github.py --data external_data --curriculum action_platform_curriculum.json --out external_data/model_candidate --steps 180 --batch 12 --threads 2
```

The GitHub Actions pipeline runs audits, code-only collection and training separately in a sandbox. **The trained model is not automatically promoted** to the user's Luna, and the Brain-SSD research baselines are not modified.

## Scientific evaluation

The previous external-source-only MiniCoder checkpoint reached holdout next-char loss ~3.376, but **0/5** of its generated JavaScript snippets passed syntax parsing. A better next-character loss does *not* mean it learned to code games. The next experiment adds our original combat curriculum and repeats syntax checks against an entirely independent holdout repository, with separate gameplay testing needed later. Compare actual runs and SHA reports before drawing conclusions.

User-supplied repositories are a reference catalog; only original lessons plus vetted MIT gaming examples are actual training input. The model has not been taught how to implement any proprietary Grand Chase protocol or decrypt client assets. The goal remains a **new original action-platform game** with playable mechanics and editable files.


## First measured combat-curriculum training run

- [GitHub Actions successful run 40697580090](https://github.com/HelioConde/I.A/actions/runs/40697580090).
- [Checkpoint + provenance + syntax artifact 12820600764](https://github.com/HelioConde/I.A/actions/runs/40697580090/artifacts/12820600764).
- Both source/curriculum audit suites passed (5/5 + 5/5 tests).
- External MIT corpus unchanged: 19 training files, 6 files from a separate holdout repository.
- Eight original action-platform lessons included in training, four unanswered holdout lessons omitted from training.
- MiniCoder random initialization, 180 CPU update steps. Next-character holdout loss 35.61765 -> 3.303632. Earlier external-only experiment after 180 steps: 3.376007; improvement approximately 2.14% relative on that single evaluation.
- Generated JavaScript code syntax: **0/5**, unchanged. No gameplay tested. Result remains **NOT PROMOTED**.
- Report asserts: grandchase_raw_repositories_in_training=0, original_curriculum_examples=8.
