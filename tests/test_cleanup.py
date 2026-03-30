from pathlib import Path

import pytest

from suunto_export_activity.cleanup import _guard_output_path
from suunto_export_activity.cleanup import delete_exported_data


def test_delete_exported_data(tmp_path: Path) -> None:
    target = tmp_path / "output"
    target.mkdir()
    (target / "file.txt").write_text("x", encoding="utf-8")

    assert delete_exported_data(target) is True
    assert not target.exists()


def test_delete_exported_data_when_missing(tmp_path: Path) -> None:
    assert delete_exported_data(tmp_path / "missing") is False


def test_guard_output_path_rejects_unsafe_paths() -> None:
    with pytest.raises(ValueError):
        _guard_output_path(Path.home())
