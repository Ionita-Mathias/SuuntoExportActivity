from pathlib import Path

import pytest

from suunto_export_activity.exporter import export_activities
from suunto_export_activity.models import ActivityRecord


def test_export_activities(tmp_path: Path) -> None:
    activities = [ActivityRecord(activity_id="1", type="run", distance=10.0)]
    json_path, csv_path = export_activities(tmp_path, activities)

    assert json_path.exists()
    assert csv_path.exists()
    assert "activity_id" in csv_path.read_text(encoding="utf-8")


def test_export_activities_encryption_requires_passphrase(tmp_path: Path) -> None:
    activities = [ActivityRecord(activity_id="1", type="run", distance=10.0)]
    with pytest.raises(ValueError):
        export_activities(tmp_path, activities, encrypt=True, passphrase=None)


def test_export_activities_encryption_calls_encrypt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    activities = [ActivityRecord(activity_id="1", type="run", distance=10.0)]

    encrypted_files: list[Path] = []

    def _fake_encrypt(path: Path, passphrase: str, *, delete_plaintext: bool) -> Path:
        assert passphrase == "secret"
        assert delete_plaintext is True
        encrypted = path.with_suffix(path.suffix + ".enc")
        encrypted.write_text("enc", encoding="utf-8")
        encrypted_files.append(encrypted)
        return encrypted

    monkeypatch.setattr("suunto_export_activity.exporter.encrypt_file", _fake_encrypt)

    json_path, csv_path = export_activities(tmp_path, activities, encrypt=True, passphrase="secret")
    assert json_path in encrypted_files
    assert csv_path in encrypted_files
