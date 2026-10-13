"""Location for local firmware images and device credentials."""

from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _work_dir() -> Path:
    configured = os.environ.get("INKFORGE_WORK_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    # Preserve the original research workspace layout; normal clones use a
    # sibling directory so generated firmware cannot enter the Git tree.
    legacy = ROOT.parent.parent / "work"
    if ROOT.parent.name == "outputs" and legacy.is_dir():
        return legacy.resolve()
    return (ROOT.parent / "inkforge-work").resolve()


WORK_DIR = _work_dir()
