# Luna Forge Zero — Brain-SSD experimental

**Objective:** Make both from-scratch research models operate using selective activation and the existing Brain-SSD storage backend, without changing frozen research phases, default Qwen models, chat, or user data.

## Actual path

- brain_ssd_bridge.py: a deterministic keyword router (planner vs coder); activates **one** PyTorch model at a time.
- Checkpoints stay on SSD. Loading uses torch.load(..., mmap=True, weights_only=True) with load_state_dict(assign=True) on CPU. This can reduce unnecessary weight copies, but **PyTorch, activations and page cache still require RAM**. The --max-mib flag guards weight **file size only**; it is **not** an OS-enforced RAM cap.
- Skills are stored in **4 KiB, read-only, checksummed cortical pages** with the existing brain_ssd.storage.MMapStorageBackend, accessed in groups of at most two pages. This is a separate experimental corpus; it does not change the original Brain-SSD 1 MiB logical page/4 MiB extent research or its policy.
- Metadata is a small lexical index in the manifest; access metrics count *logical bytes* not physical disk reads. No unverifiable RAM or disk savings are claimed.
- An opt-in local SQLite feedback journal stores examples pending review, **without automatically updating weights**.
- The game code model is still primitive. Generated text is never executed automatically; tests and approvals come first.

## Windows PowerShell

After extracting the trained checkpoints from the conversation ZIP into the directory experiments/luna-forge-zero/checkpoints/:

~~~powershell
cd C:\Users\helio\Documents\I.A
py -m pip install torch psutil
py experiments/luna-forge-zero/brain_ssd_bridge.py status
py experiments/luna-forge-zero/brain_ssd_bridge.py build-knowledge
py experiments/luna-forge-zero/brain_ssd_bridge.py plan --request "Crie um jogo de plataforma com pulo e moedas"
py experiments/luna-forge-zero/brain_ssd_bridge.py code --request "TAREFA: mover jogador velocidade 200"
py -m unittest discover -s tests -p test_luna_forge_brain_ssd.py -v
~~~

The plan output contains the Planner’s predicted genre and mechanics plus retrieved skill pages. The code output is **unverified** character generation. The auto mode routes on keywords; this classifier is a heuristic, not another trained teacher model.

## Architecture and next milestones

1. Validate on Windows 11 physical hardware and report Working Set / Private Bytes, CPU time, I/O and first-token latency. Compare ordinary torch.load vs mmap+assign under identical conditions, one worker per run.
2. Add a dedicated lifecycle manager that can evict inactive specialist models when the main Brain-SSD chat is using RAM; do not infer safety from the file-size guard.
3. Integrate with the existing Luna Code Studio as an **optional** provider, never replacing default models without consent and a benchmark.
4. Build Teacher Core scheduling, challenge generation, verified reward and dataset curation; train only from approved, traceable examples and independent held-out evaluation.
5. Verify on real Godot and Chromium game tests; do not claim game-creation competence from synthetic classifier scores.

## Status and provenance

This PR adds adapter code and standard-library tests against the **original Brain-SSD storage module**. Trained binary weights remain in the user-delivered ZIP, not committed to GitHub. The ZIP includes an additional portable storage fallback for running outside the monorepo. Do not merge this draft PR or enable its runtime by default until physical Windows tests and game benchmarks pass.
