"""OAuth2 authentication helpers for Suunto API."""

from __future__ import annotations

from urllib.parse import urlencode

import requests

from .config import Settings
from .exceptions import AuthError
from .token_store import TokenData, TokenStore


class OAuthClient:
    def __init__(self, settings: Settings, timeout: int = 30):
        self.settings = settings
        self.timeout = timeout
        self.store = TokenStore(settings.token_path)
        self.session = requests.Session()

    def build_authorize_url(self, state: str = "suunto-export") -> str:
        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": self.settings.redirect_uri,
            "scope": self.settings.scope,
            "state": state,
        }
        return f"{self.settings.oauth_authorize_url}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> TokenData:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
        }
        response = self.session.post(
            self.settings.oauth_token_url,
            data=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise AuthError(
                f"Token exchange failed ({response.status_code}): {response.text[:300]}"
            )
        token_payload = response.json()
        token = self.store.save(token_payload)
        if not token.access_token:
            raise AuthError("Received token payload without access_token.")
        return token

    def refresh_access_token(self, refresh_token: str) -> TokenData:
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
        }
        response = self.session.post(
            self.settings.oauth_token_url,
            data=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise AuthError(
                f"Token refresh failed ({response.status_code}): {response.text[:300]}"
            )
        token_payload = response.json()
        token = self.store.save(token_payload)
        if not token.access_token:
            raise AuthError("Received refreshed payload without access_token.")
        return token

    def get_valid_token(self) -> TokenData:
        token = self.store.load()
        if token is None:
            raise AuthError(
                "No token found. Run 'suunto-export auth-url' then 'suunto-export exchange-code'."
            )

        if token.is_expired():
            if not token.refresh_token:
                raise AuthError(
                    "Access token expired and no refresh_token is available. Re-authenticate."
                )
            token = self.refresh_access_token(token.refresh_token)
        return token

    def get_auth_header(self) -> str:
        token = self.get_valid_token()
        return f"Bearer {token.access_token}"
