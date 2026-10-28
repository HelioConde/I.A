# Luna S1.1 dash semantic retry

Model's previous dash passed Node but failed real browser speed comparisons. Revised prompt and validator now require `lastRightTap > 0` and `lastLeftTap > 0` before dash, timestamp assignment AFTER speed decision and strict guard if (!e.repeat). Only Qwen creates code patches, no assistant fallback. Original six and three dash Playwright tests must pass.
