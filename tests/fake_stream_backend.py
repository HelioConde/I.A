#!/usr/bin/env python3
import sys
import time

time.sleep(0.05)
print("AZUL", flush=True)
time.sleep(0.05)
print("llama_perf_context_print: eval time = 100.00 ms / 2 runs (50.00 ms per token, 20.00 tokens per second)", file=sys.stderr)

