# Luna GameDev latest local runtime and one-command installer regression

Validate Windows official b11946 CPU runtime starts with SHA pin, model selection prefers Ornith only when modern CLI exists, then reverts to Qwen4B, and `setup_luna_gamedev_v4.py` requires explicit --confirm-download without modifying Brain-SSD chat or frozen research runtime. No need to redownload the GGUF on this runtime smoke test.
