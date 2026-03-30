from pathlib import Path

from datetime import datetime, timezone

import pytest

from suunto_export_activity.token_store import TokenData
from suunto_export_activity.token_store import TokenStore


def test_memory_store_roundtrip() -> None:
    store = TokenStore(path=None, mode="memory")
    token = store.save({"access_token": "abc", "expires_in": 60})

    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "abc"
    assert token.expires_at is not None


def test_file_store_roundtrip(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    store = TokenStore(path=token_path, mode="file")
    store.save({"access_token": "abc"})

    reloaded = TokenStore(path=token_path, mode="file").load()
    assert reloaded is not None
    assert reloaded.access_token == "abc"


def test_invalid_store_mode_raises() -> None:
    with pytest.raises(ValueError):
        TokenStore(path=None, mode="invalid")


def test_load_from_env_overrides_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text('{"access_token":"file-token"}', encoding="utf-8")
    store = TokenStore(path=token_path, mode="file")

    monkeypatch.setenv("SUUNTO_ACCESS_TOKEN", "env-token")
    token = store.load()
    assert token is not None
    assert token.access_token == "env-token"


def test_load_invalid_file_payload_returns_none(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text("not-json", encoding="utf-8")
    store = TokenStore(path=token_path, mode="file")
    assert store.load() is None


def test_load_file_without_access_token_returns_none(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    token_path.write_text('{"refresh_token":"r"}', encoding="utf-8")
    store = TokenStore(path=token_path, mode="file")
    assert store.load() is None


def test_token_data_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUUNTO_ACCESS_TOKEN", "abc")
    monkeypatch.setenv("SUUNTO_TOKEN_TYPE", "Bearer")
    monkeypatch.setenv("SUUNTO_REFRESH_TOKEN", "refresh")
    monkeypatch.setenv("SUUNTO_TOKEN_EXPIRES_AT", "123")
    monkeypatch.setenv("SUUNTO_TOKEN_SCOPE", "workouts.read")

    token = TokenData.from_env()
    assert token is not None
    assert token.access_token == "abc"
    assert token.refresh_token == "refresh"
    assert token.expires_at == 123
    assert token.scope == "workouts.read"


def test_token_data_from_env_none_when_access_missing() -> None:
    assert TokenData.from_env() is None


def test_token_data_expiration_logic(monkeypatch: pytest.MonkeyPatch) -> None:
    token = TokenData(access_token="a", expires_at=1000)
    monkeypatch.setattr(
        "suunto_export_activity.token_store.utc_now",
        lambda: datetime.fromtimestamp(1100, tz=timezone.utc),
    )
    assert token.is_expired() is True
    assert TokenData(access_token="b", expires_at=None).is_expired() is False


def test_clear_removes_file(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    store = TokenStore(path=token_path, mode="file")
    store.save({"access_token": "abc"})
    assert token_path.exists()
    store.clear()
    assert not token_path.exists()
