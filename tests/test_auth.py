from __future__ import annotations

import base64
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from suunto_export_activity.auth import OAuthClient
from suunto_export_activity.config import Settings
from suunto_export_activity.exceptions import AuthError
from suunto_export_activity.token_store import TokenData


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def post(self, url, data, timeout):  # noqa: ANN001
        self.calls.append({"url": url, "data": dict(data), "timeout": timeout})
        return self.responses.pop(0)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        client_id="cid",
        client_secret="secret",
        subscription_key="sub",
        token_storage_mode="memory",
        token_path=tmp_path / "token.json",
    )


def test_build_authorize_url_contains_expected_query(tmp_path: Path) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    url = oauth.build_authorize_url(state="abc123")
    query = parse_qs(urlparse(url).query)
    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["cid"]
    assert query["state"] == ["abc123"]


def test_exchange_code_for_token_success(tmp_path: Path) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    oauth.session = _FakeSession([_FakeResponse(200, {"access_token": "a", "expires_in": 60})])
    token = oauth.exchange_code_for_token("code-1")

    assert token.access_token == "a"
    assert token.expires_at is not None


def test_exchange_code_for_token_http_error_raises(tmp_path: Path) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    oauth.session = _FakeSession([_FakeResponse(400, text="bad request")])
    with pytest.raises(AuthError):
        oauth.exchange_code_for_token("code-1")


def test_exchange_code_for_token_missing_access_token_raises(tmp_path: Path) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    oauth.session = _FakeSession([_FakeResponse(200, {"refresh_token": "r"})])
    with pytest.raises(AuthError):
        oauth.exchange_code_for_token("code-1")


def test_refresh_access_token_success(tmp_path: Path) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    oauth.session = _FakeSession([_FakeResponse(200, {"access_token": "new-token"})])
    token = oauth.refresh_access_token("refresh-1")
    assert token.access_token == "new-token"


def test_refresh_access_token_http_error_raises(tmp_path: Path) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    oauth.session = _FakeSession([_FakeResponse(401, text="unauthorized")])
    with pytest.raises(AuthError):
        oauth.refresh_access_token("refresh-1")


def test_refresh_access_token_missing_access_token_raises(tmp_path: Path) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    oauth.session = _FakeSession([_FakeResponse(200, {"scope": "x"})])
    with pytest.raises(AuthError):
        oauth.refresh_access_token("refresh-1")


def test_get_valid_token_without_token_raises(tmp_path: Path) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    with pytest.raises(AuthError):
        oauth.get_valid_token()


def test_get_valid_token_expired_without_refresh_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    expired = TokenData(access_token="a", refresh_token=None, expires_at=1)
    monkeypatch.setattr(oauth.store, "load", lambda: expired)
    monkeypatch.setattr(TokenData, "is_expired", lambda self, leeway_seconds=45: True)
    with pytest.raises(AuthError):
        oauth.get_valid_token()


def test_get_valid_token_expired_with_refresh_calls_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    expired = TokenData(access_token="a", refresh_token="r", expires_at=1)
    refreshed = TokenData(access_token="b", refresh_token="r", expires_at=9999999999)
    monkeypatch.setattr(oauth.store, "load", lambda: expired)
    monkeypatch.setattr(TokenData, "is_expired", lambda self, leeway_seconds=45: True)
    monkeypatch.setattr(oauth, "refresh_access_token", lambda refresh_token: refreshed)

    token = oauth.get_valid_token()
    assert token.access_token == "b"


def test_refresh_if_possible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    no_refresh = TokenData(access_token="a", refresh_token=None)
    monkeypatch.setattr(oauth.store, "load", lambda: no_refresh)
    assert oauth.refresh_if_possible() is None

    with_refresh = TokenData(access_token="a", refresh_token="rr")
    monkeypatch.setattr(oauth.store, "load", lambda: with_refresh)
    monkeypatch.setattr(oauth, "refresh_access_token", lambda refresh_token: with_refresh)
    assert oauth.refresh_if_possible() is with_refresh


def test_decode_jwt_claims_variants() -> None:
    payload = {"sub": "user-1"}
    payload_raw = json.dumps(payload).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_raw).decode("ascii").rstrip("=")
    token = f"header.{payload_b64}.signature"

    assert OAuthClient._decode_jwt_claims(token) == payload
    assert OAuthClient._decode_jwt_claims("invalid-token") == {}
    assert OAuthClient._decode_jwt_claims("a.b.c") == {}


def test_get_token_claims(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    payload = {"sub": "u1"}
    payload_raw = json.dumps(payload).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_raw).decode("ascii").rstrip("=")
    token = f"h.{payload_b64}.s"
    monkeypatch.setattr(oauth, "get_valid_token", lambda: TokenData(access_token=token))
    assert oauth.get_token_claims() == {"sub": "u1"}


def test_get_current_user_id_uses_claim_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    monkeypatch.setattr(oauth, "get_token_claims", lambda: {"userid": " 42 "})
    assert oauth.get_current_user_id() == "42"

    monkeypatch.setattr(oauth, "get_token_claims", lambda: {"x": "y"})
    assert oauth.get_current_user_id() is None


def test_get_auth_header(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = OAuthClient(_settings(tmp_path))
    monkeypatch.setattr(
        oauth,
        "get_valid_token",
        lambda: SimpleNamespace(access_token="abc"),  # type: ignore[return-value]
    )
    assert oauth.get_auth_header() == "Bearer abc"
