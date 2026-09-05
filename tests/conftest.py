from __future__ import annotations

import os


# These suites exercise frozen Linux kernel APIs at import time. The native
# Windows functional runtime reports the same features as UNSUPPORTED and does
# not pretend that skipping them constitutes a canonical Phase 4E pass.
collect_ignore = []
if os.name == "nt":
    collect_ignore.extend([
        "test_residency.py",
        "test_pressure.py",
        "test_phase4e_physical_validation.py",
    ])
