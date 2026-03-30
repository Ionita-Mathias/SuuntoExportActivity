"""Secure-ish cleanup helpers for exported activity data."""

from __future__ import annotations

import shutil
from pathlib import Path


def _guard_output_path(path: Path) -> None:
    resolved = path.resolve()
    if str(resolved) in {"/", str(Path.home().resolve())}:
        raise ValueError(f"Refusing to delete unsafe path: {resolved}")


def delete_exported_data(output_dir: Path) -> bool:
    target = output_dir.resolve()
    if not target.exists():
        return False
    _guard_output_path(target)
    shutil.rmtree(target)
    return True
