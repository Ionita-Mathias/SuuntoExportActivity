from __future__ import annotations

from pathlib import Path

import pytest

from suunto_export_activity.config import Settings
from suunto_export_activity.exceptions import ConfigError


def _write_env(tmp_path: Path, lines: list[str]) -> Path:
    env_file = tmp_path / ".env.test"
    env_file.write_text("\n".join(lines), encoding="utf-8")
    return env_file


def test_settings_from_env_happy_path(tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        [
            "SUUNTO_CLIENT_ID=cid",
            "SUUNTO_CLIENT_SECRET=csecret",
            "SUUNTO_SUBSCRIPTION_KEY=subkey",
            "SUUNTO_MAX_HR=190",
            "SUUNTO_TOKEN_PATH=.tokens/token.json",
            "SUUNTO_TOKEN_STORAGE=file",
            "SUUNTO_RATE_LIMIT_PER_MINUTE=15",
            "SUUNTO_OWNER_USER_ID=user-1",
            "SUUNTO_REQUIRE_CONSENT=false",
            "SUUNTO_ENCRYPT_EXPORT=true",
            "SUUNTO_EXPORT_PASSPHRASE=secret",
            "SUUNTO_LOG_FILE=logs/app.log",
        ],
    )

    settings = Settings.from_env(env_file=env_file)

    assert settings.client_id == "cid"
    assert settings.client_secret == "csecret"
    assert settings.subscription_key == "subkey"
    assert settings.max_hr == 190
    assert settings.token_path == Path(".tokens/token.json")
    assert settings.token_storage_mode == "file"
    assert settings.rate_limit_per_minute == 15
    assert settings.owner_user_id == "user-1"
    assert settings.require_consent is False
    assert settings.default_encrypt_export is True
    assert settings.export_passphrase == "secret"
    assert settings.log_file == Path("logs/app.log")


def test_settings_from_env_without_required_credentials_when_disabled(tmp_path: Path) -> None:
    env_file = _write_env(tmp_path, [])
    settings = Settings.from_env(env_file=env_file, require_api_credentials=False)
    assert settings.client_id == ""
    assert settings.client_secret == ""
    assert settings.subscription_key == ""


def test_settings_missing_client_id_raises(tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        [
            "SUUNTO_CLIENT_SECRET=csecret",
            "SUUNTO_SUBSCRIPTION_KEY=subkey",
        ],
    )
    with pytest.raises(ConfigError):
        Settings.from_env(env_file=env_file)


def test_settings_missing_client_secret_raises(tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        [
            "SUUNTO_CLIENT_ID=cid",
            "SUUNTO_SUBSCRIPTION_KEY=subkey",
        ],
    )
    with pytest.raises(ConfigError):
        Settings.from_env(env_file=env_file)


def test_settings_missing_subscription_key_raises(tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        [
            "SUUNTO_CLIENT_ID=cid",
            "SUUNTO_CLIENT_SECRET=csecret",
        ],
    )
    with pytest.raises(ConfigError):
        Settings.from_env(env_file=env_file)


def test_settings_invalid_max_hr_raises(tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        [
            "SUUNTO_CLIENT_ID=cid",
            "SUUNTO_CLIENT_SECRET=csecret",
            "SUUNTO_SUBSCRIPTION_KEY=subkey",
            "SUUNTO_MAX_HR=not-an-int",
        ],
    )
    with pytest.raises(ConfigError):
        Settings.from_env(env_file=env_file)


def test_settings_invalid_token_storage_raises(tmp_path: Path) -> None:
    env_file = _write_env(
        tmp_path,
        [
            "SUUNTO_CLIENT_ID=cid",
            "SUUNTO_CLIENT_SECRET=csecret",
            "SUUNTO_SUBSCRIPTION_KEY=subkey",
            "SUUNTO_TOKEN_STORAGE=database",
        ],
    )
    with pytest.raises(ConfigError):
        Settings.from_env(env_file=env_file)


def test_settings_invalid_rate_limit_raises(tmp_path: Path) -> None:
    env_file_int = _write_env(
        tmp_path,
        [
            "SUUNTO_CLIENT_ID=cid",
            "SUUNTO_CLIENT_SECRET=csecret",
            "SUUNTO_SUBSCRIPTION_KEY=subkey",
            "SUUNTO_RATE_LIMIT_PER_MINUTE=not-int",
        ],
    )
    with pytest.raises(ConfigError):
        Settings.from_env(env_file=env_file_int)


def test_settings_rate_limit_must_be_positive(tmp_path: Path) -> None:
    env_file_positive = _write_env(
        tmp_path,
        [
            "SUUNTO_CLIENT_ID=cid",
            "SUUNTO_CLIENT_SECRET=csecret",
            "SUUNTO_SUBSCRIPTION_KEY=subkey",
            "SUUNTO_RATE_LIMIT_PER_MINUTE=0",
        ],
    )
    with pytest.raises(ConfigError):
        Settings.from_env(env_file=env_file_positive)


def test_settings_from_default_env_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUUNTO_CLIENT_ID", "cid")
    monkeypatch.setenv("SUUNTO_CLIENT_SECRET", "secret")
    monkeypatch.setenv("SUUNTO_SUBSCRIPTION_KEY", "sub")

    called: list[Path] = []
    monkeypatch.setattr("suunto_export_activity.config.load_env_file", lambda path: called.append(path))

    settings = Settings.from_env(env_file=None)
    assert settings.client_id == "cid"
    assert called == [Path(".env")]
