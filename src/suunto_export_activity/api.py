"""Suunto API client wrappers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .auth import OAuthClient
from .config import Settings
from .exceptions import ApiError
from .utils import ensure_directory


class RequestLimiter:
    """Simple fixed-interval limiter to respect per-minute API quotas."""

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = max(1, requests_per_minute)
        self._min_interval = 60.0 / self.requests_per_minute
        self._last_request_ts = 0.0

    def wait_if_needed(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_ts
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_ts = time.monotonic()


class SuuntoApiClient:
    def __init__(self, settings: Settings, oauth_client: OAuthClient, timeout: int = 45):
        self.settings = settings
        self.oauth_client = oauth_client
        self.timeout = timeout
        self.session = requests.Session()
        self.rate_limiter = RequestLimiter(settings.rate_limit_per_minute)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.oauth_client.get_auth_header(),
            "Ocp-Apim-Subscription-Key": self.settings.subscription_key,
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: dict[str, Any] | None = None,
        stream: bool = False,
        absolute_url: bool = False,
        retry_on_unauthorized: bool = True,
    ) -> requests.Response:
        url = endpoint if absolute_url else f"{self.settings.api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        self.rate_limiter.wait_if_needed()
        response = self.session.request(
            method,
            url,
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
            stream=stream,
        )

        if response.status_code == 401 and retry_on_unauthorized:
            refreshed = self.oauth_client.refresh_if_possible()
            if refreshed is not None:
                self.rate_limiter.wait_if_needed()
                response = self.session.request(
                    method,
                    url,
                    headers=self._headers(),
                    params=params,
                    timeout=self.timeout,
                    stream=stream,
                )

        if response.status_code == 429:
            raise ApiError(
                f"Suunto API rate limit reached for {url}. "
                f"Configured client-side throttle: {self.settings.rate_limit_per_minute}/minute."
            )
        if response.status_code >= 400:
            raise ApiError(f"API request failed ({response.status_code}) for {url}: {response.text[:400]}")
        return response

    def list_workouts(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        page_size: int = 50,
        max_items: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch workouts from /v2/workouts with simple offset pagination."""
        collected: list[dict[str, Any]] = []
        offset = 0

        while True:
            params: dict[str, Any] = {
                "limit": page_size,
                "offset": offset,
            }
            if start_date:
                params["startDate"] = start_date
            if end_date:
                params["endDate"] = end_date

            response = self._request("GET", "/v2/workouts", params=params)
            payload = response.json()
            items = self._extract_workout_items(payload)

            if not items:
                break

            for item in items:
                collected.append(item)
                if max_items is not None and len(collected) >= max_items:
                    return self._filter_for_current_user(collected)

            if len(items) < page_size:
                break
            offset += page_size

        return self._filter_for_current_user(collected)

    def _effective_user_id(self) -> str | None:
        if self.settings.owner_user_id:
            return self.settings.owner_user_id
        return self.oauth_client.get_current_user_id()

    @staticmethod
    def _extract_owner_id(workout: dict[str, Any]) -> str | None:
        for key in (
            "userId",
            "user_id",
            "ownerId",
            "owner_id",
            "athleteId",
            "athlete_id",
            "accountId",
            "account_id",
        ):
            value = workout.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()

        user_node = workout.get("user")
        if isinstance(user_node, dict):
            for key in ("id", "userId", "user_id"):
                value = user_node.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()

        return None

    def _filter_for_current_user(self, workouts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        user_id = self._effective_user_id()
        if not user_id:
            return workouts

        filtered: list[dict[str, Any]] = []
        for workout in workouts:
            owner_id = self._extract_owner_id(workout)
            if owner_id is None or owner_id == user_id:
                filtered.append(workout)
        return filtered

    @staticmethod
    def _extract_workout_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("workouts", "items", "data", "results"):
                candidate = payload.get(key)
                if isinstance(candidate, list):
                    return [item for item in candidate if isinstance(item, dict)]
            if payload:
                return [payload]
        return []

    @staticmethod
    def _discover_urls(payload: Any) -> list[tuple[str, str]]:
        """Find URLs in nested workout payload and infer file type."""
        discovered: list[tuple[str, str]] = []

        def visit(node: Any, parent_key: str = "") -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    visit(value, key)
            elif isinstance(node, list):
                for value in node:
                    visit(value, parent_key)
            elif isinstance(node, str):
                value = node.strip()
                if not (value.startswith("http://") or value.startswith("https://")):
                    return

                lowered = value.lower()
                key_hint = parent_key.lower()
                if lowered.endswith(".fit") or "fit" in key_hint:
                    discovered.append(("fit", value))
                elif lowered.endswith(".json") or "json" in key_hint:
                    discovered.append(("json", value))

        visit(payload)

        unique: list[tuple[str, str]] = []
        seen: set[str] = set()
        for file_type, url in discovered:
            if url in seen:
                continue
            seen.add(url)
            unique.append((file_type, url))
        return unique

    def workout_resource_urls(self, workout: dict[str, Any]) -> list[tuple[str, str]]:
        return self._discover_urls(workout)

    @staticmethod
    def _url_filename(url: str, fallback: str) -> str:
        parsed = urlparse(url)
        candidate = Path(parsed.path).name
        if candidate:
            return candidate
        return fallback

    def download_resource(self, url: str, destination: Path) -> Path:
        ensure_directory(destination.parent)
        response = self._request("GET", url, stream=True, absolute_url=True)
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    handle.write(chunk)
        return destination

    def download_workout_resources(self, workout: dict[str, Any], output_dir: Path) -> list[Path]:
        resources = self.workout_resource_urls(workout)
        downloaded: list[Path] = []
        workout_id = str(workout.get("id") or workout.get("workoutId") or "unknown")
        workout_dir = ensure_directory(output_dir / workout_id)

        for idx, (file_type, url) in enumerate(resources, start=1):
            ext = ".fit" if file_type == "fit" else ".json"
            filename = self._url_filename(url, fallback=f"resource_{idx}{ext}")
            if not filename.lower().endswith((".fit", ".json")):
                filename = f"{filename}{ext}"
            destination = workout_dir / filename
            downloaded.append(self.download_resource(url, destination))

        return downloaded
