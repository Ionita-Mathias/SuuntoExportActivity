"""Token storage backends.

By default tokens are kept in memory only.
File persistence can be enabled explicitly via configuration.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import ensure_directory, safe_int, utc_now


@dataclass(slots=True)
class TokenData:
    access_token: str
    token_type: str = "Bearer"
    refresh_token: str | None = None
    expires_at: int | None = None
    scope: str | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TokenData":
        return cls(
            access_token=payload.get("access_token", ""),
            token_type=payload.get("token_type", "Bearer"),
            refresh_token=payload.get("refresh_token"),
            expires_at=safe_int(payload.get("expires_at")),
            scope=payload.get("scope"),
        )

    @classmethod
    def from_env(cls) -> "TokenData" | None:
        access_token = os.getenv("SUUNTO_ACCESS_TOKEN", "").strip()
        if not access_token:
            return None
        return cls(
            access_token=access_token,
            token_type=os.getenv("SUUNTO_TOKEN_TYPE", "Bearer").strip() or "Bearer",
            refresh_token=os.getenv("SUUNTO_REFRESH_TOKEN", "").strip() or None,
            expires_at=safe_int(os.getenv("SUUNTO_TOKEN_EXPIRES_AT")),
            scope=os.getenv("SUUNTO_TOKEN_SCOPE", "").strip() or None,
        )

    def is_expired(self, leeway_seconds: int = 45) -> bool:
        if self.expires_at is None:
            return False
        return int(utc_now().timestamp()) >= (int(self.expires_at) - leeway_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
            "scope": self.scope,
        }


class TokenStore:
    def __init__(self, path: Path | None, *, mode: str = "memory"):
        if mode not in {"memory", "file"}:
            raise ValueError(f"Unsupported token storage mode: {mode}")
        self.path = path
        self.mode = mode
        self._memory_token: TokenData | None = None

    def load(self) -> TokenData | None:
        env_token = TokenData.from_env()
        if env_token is not None:
            self._memory_token = env_token
            return env_token

        if self._memory_token is not None:
            return self._memory_token

        if self.mode == "file" and self.path and self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
            token = TokenData.from_dict(payload)
            if token.access_token:
                self._memory_token = token
                return token
        return None

    def save(self, token_payload: dict[str, Any]) -> TokenData:
        token_payload = dict(token_payload)
        expires_in = token_payload.get("expires_in")
        if expires_in is not None and "expires_at" not in token_payload:
            token_payload["expires_at"] = int(utc_now().timestamp()) + int(expires_in)

        token = TokenData.from_dict(token_payload)
        self._memory_token = token

        if self.mode == "file" and self.path is not None:
            ensure_directory(self.path.parent)
            self.path.write_text(json.dumps(token.to_dict(), indent=2), encoding="utf-8")

        return token

    def clear(self) -> None:
        self._memory_token = None
        if self.mode == "file" and self.path is not None and self.path.exists():
            self.path.unlink(missing_ok=True)
