"""Build/runtime version identifier for ReCiter Desktop.

Used to stamp exports (CSV downloads, reports) so any artifact can be
traced back to a specific code revision.

Resolution order:
1. RECITER_DESKTOP_VERSION env var (preferred for Docker / packaged builds)
2. `git rev-parse --short HEAD` from the repo root (dev mode)
3. "unknown"
"""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_version() -> str:
    env = os.environ.get("RECITER_DESKTOP_VERSION", "").strip()
    if env:
        return env

    repo_root = Path(__file__).resolve().parents[2]
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        sha = out.stdout.strip()
        if sha:
            return sha
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return "unknown"
