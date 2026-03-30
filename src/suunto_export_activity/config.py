"""Configuration handling for Suunto export utility."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .compliance import normalize_bool
from .exceptions import ConfigError
from .utils import load_env_file


@dataclass(slots=True)
class Settings:
    client_id: str
    client_secret: str
    subscription_key: str
    oauth_token_url: str = "https://cloudapi-oauth.suunto.com/oauth/token"
    oauth_authorize_url: str = "https://cloudapi-oauth.suunto.com/oauth/authorize"
    api_base_url: str = "https://cloudapi.suunto.com"
    redirect_uri: str = "http://localhost:8080/callback"
    scope: str = "workouts.read"
    token_path: Path = Path(".tokens/suunto_token.json")
    token_storage_mode: str = "memory"
    max_hr: int | None = None
    rate_limit_per_minute: int = 10
    owner_user_id: str | None = None
    require_consent: bool = True
    default_encrypt_export: bool = False
    export_passphrase: str | None = None
    log_file: Path = Path("suunto_export.log")

    @classmethod
    def from_env(
        cls,
        env_file: Path | None = None,
        *,
        require_api_credentials: bool = True,
    ) -> "Settings":
        if env_file:
            load_env_file(env_file)
        else:
            load_env_file(Path(".env"))

        client_id = os.getenv("SUUNTO_CLIENT_ID", "").strip()
        client_secret = os.getenv("SUUNTO_CLIENT_SECRET", "").strip()
        subscription_key = os.getenv("SUUNTO_SUBSCRIPTION_KEY", "").strip()

        if require_api_credentials and not client_id:
            raise ConfigError("SUUNTO_CLIENT_ID is required.")
        if require_api_credentials and not client_secret:
            raise ConfigError("SUUNTO_CLIENT_SECRET is required.")
        if require_api_credentials and not subscription_key:
            raise ConfigError("SUUNTO_SUBSCRIPTION_KEY is required.")

        max_hr_raw = os.getenv("SUUNTO_MAX_HR")
        try:
            max_hr = int(max_hr_raw) if max_hr_raw and max_hr_raw.strip() else None
        except ValueError as exc:
            raise ConfigError("SUUNTO_MAX_HR must be an integer.") from exc

        token_path_str = os.getenv("SUUNTO_TOKEN_PATH", ".tokens/suunto_token.json").strip()
        token_path = Path(token_path_str)

        token_storage_mode = os.getenv("SUUNTO_TOKEN_STORAGE", "memory").strip().lower()
        if token_storage_mode not in {"memory", "file"}:
            raise ConfigError("SUUNTO_TOKEN_STORAGE must be 'memory' or 'file'.")

        rate_limit_raw = os.getenv("SUUNTO_RATE_LIMIT_PER_MINUTE", "10").strip()
        try:
            rate_limit_per_minute = int(rate_limit_raw)
        except ValueError as exc:
            raise ConfigError("SUUNTO_RATE_LIMIT_PER_MINUTE must be an integer.") from exc
        if rate_limit_per_minute <= 0:
            raise ConfigError("SUUNTO_RATE_LIMIT_PER_MINUTE must be > 0.")

        return cls(
            client_id=client_id,
            client_secret=client_secret,
            subscription_key=subscription_key,
            oauth_token_url=os.getenv(
                "SUUNTO_OAUTH_TOKEN_URL", "https://cloudapi-oauth.suunto.com/oauth/token"
            ).strip(),
            oauth_authorize_url=os.getenv(
                "SUUNTO_OAUTH_AUTHORIZE_URL", "https://cloudapi-oauth.suunto.com/oauth/authorize"
            ).strip(),
            api_base_url=os.getenv("SUUNTO_API_BASE_URL", "https://cloudapi.suunto.com").strip(),
            redirect_uri=os.getenv("SUUNTO_REDIRECT_URI", "http://localhost:8080/callback").strip(),
            scope=os.getenv("SUUNTO_SCOPE", "workouts.read").strip(),
            token_path=token_path,
            token_storage_mode=token_storage_mode,
            max_hr=max_hr,
            rate_limit_per_minute=rate_limit_per_minute,
            owner_user_id=os.getenv("SUUNTO_OWNER_USER_ID", "").strip() or None,
            require_consent=normalize_bool(os.getenv("SUUNTO_REQUIRE_CONSENT"), True),
            default_encrypt_export=normalize_bool(os.getenv("SUUNTO_ENCRYPT_EXPORT"), False),
            export_passphrase=os.getenv("SUUNTO_EXPORT_PASSPHRASE", "").strip() or None,
            log_file=Path(os.getenv("SUUNTO_LOG_FILE", "suunto_export.log").strip()),
        )
