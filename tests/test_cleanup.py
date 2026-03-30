from pathlib import Path

from suunto_export_activity.cleanup import delete_exported_data


def test_delete_exported_data(tmp_path: Path) -> None:
    target = tmp_path / "output"
    target.mkdir()
    (target / "file.txt").write_text("x", encoding="utf-8")

    assert delete_exported_data(target) is True
    assert not target.exists()
