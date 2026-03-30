"""Persist OAuth tokens locally."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import ensure_directory, utc_now


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
            expires_at=payload.get("expires_at"),
            scope=payload.get("scope"),
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
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> TokenData | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        token = TokenData.from_dict(payload)
        return token if token.access_token else None

    def save(self, token_payload: dict[str, Any]) -> TokenData:
        token_payload = dict(token_payload)
        expires_in = token_payload.get("expires_in")
        if expires_in is not None and "expires_at" not in token_payload:
            token_payload["expires_at"] = int(utc_now().timestamp()) + int(expires_in)

        token = TokenData.from_dict(token_payload)
        ensure_directory(self.path.parent)
        self.path.write_text(json.dumps(token.to_dict(), indent=2), encoding="utf-8")
        return token
