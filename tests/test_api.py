from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from suunto_export_activity.api import RequestLimiter, SuuntoApiClient
from suunto_export_activity.config import Settings
from suunto_export_activity.exceptions import ApiError


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        payload=None,
        text: str = "",
        chunks: list[bytes] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self._chunks = chunks or []

    def json(self):  # noqa: ANN001
        return self._payload

    def iter_content(self, chunk_size: int):  # noqa: ARG002
        for chunk in self._chunks:
            yield chunk


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def request(self, method, url, headers, params, timeout, stream):  # noqa: ANN001
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "params": params,
                "timeout": timeout,
                "stream": stream,
            }
        )
        return self.responses.pop(0)


class _FakeOAuth:
    def __init__(self, *, refresh_result=None, user_id: str | None = None) -> None:
        self.refresh_result = refresh_result
        self.user_id = user_id
        self.refresh_calls = 0

    def get_auth_header(self) -> str:
        return "Bearer token"

    def refresh_if_possible(self):  # noqa: ANN001
        self.refresh_calls += 1
        return self.refresh_result

    def get_current_user_id(self) -> str | None:
        return self.user_id


def _settings() -> Settings:
    return Settings(
        client_id="cid",
        client_secret="secret",
        subscription_key="sub",
        api_base_url="https://cloudapi.suunto.com",
        rate_limit_per_minute=10,
    )


def test_request_limiter_waits_when_interval_not_elapsed(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = RequestLimiter(requests_per_minute=60)
    limiter._last_request_ts = 10.0

    values = iter([10.2, 10.4])
    monkeypatch.setattr("suunto_export_activity.api.time.monotonic", lambda: next(values))
    slept: list[float] = []
    monkeypatch.setattr("suunto_export_activity.api.time.sleep", lambda s: slept.append(s))

    limiter.wait_if_needed()
    assert slept == [pytest.approx(0.8)]
    assert limiter._last_request_ts == pytest.approx(10.4)


def test_request_limiter_does_not_wait_when_interval_elapsed(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = RequestLimiter(requests_per_minute=60)
    limiter._last_request_ts = 10.0

    values = iter([11.5, 11.6])
    monkeypatch.setattr("suunto_export_activity.api.time.monotonic", lambda: next(values))
    slept: list[float] = []
    monkeypatch.setattr("suunto_export_activity.api.time.sleep", lambda s: slept.append(s))

    limiter.wait_if_needed()
    assert slept == []
    assert limiter._last_request_ts == pytest.approx(11.6)


def test_headers_include_auth_and_subscription() -> None:
    oauth = _FakeOAuth()
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]
    headers = client._headers()
    assert headers["Authorization"] == "Bearer token"
    assert headers["Ocp-Apim-Subscription-Key"] == "sub"


def test_request_success(tmp_path: Path) -> None:
    oauth = _FakeOAuth()
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]
    client.rate_limiter = SimpleNamespace(wait_if_needed=lambda: None)  # type: ignore[assignment]
    client.session = _FakeSession([_FakeResponse(200, payload={"ok": True})])  # type: ignore[assignment]

    response = client._request("GET", "/v2/workouts")
    assert response.status_code == 200


def test_request_retries_on_401_when_refresh_available() -> None:
    oauth = _FakeOAuth(refresh_result=object())
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]
    client.rate_limiter = SimpleNamespace(wait_if_needed=lambda: None)  # type: ignore[assignment]
    client.session = _FakeSession([_FakeResponse(401), _FakeResponse(200, payload=[])])  # type: ignore[assignment]

    response = client._request("GET", "/v2/workouts")
    assert response.status_code == 200
    assert oauth.refresh_calls == 1


def test_request_401_without_refresh_raises() -> None:
    oauth = _FakeOAuth(refresh_result=None)
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]
    client.rate_limiter = SimpleNamespace(wait_if_needed=lambda: None)  # type: ignore[assignment]
    client.session = _FakeSession([_FakeResponse(401, text="unauthorized")])  # type: ignore[assignment]

    with pytest.raises(ApiError):
        client._request("GET", "/v2/workouts")


def test_request_rate_limit_raises() -> None:
    oauth = _FakeOAuth()
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]
    client.rate_limiter = SimpleNamespace(wait_if_needed=lambda: None)  # type: ignore[assignment]
    client.session = _FakeSession([_FakeResponse(429, text="too many")])  # type: ignore[assignment]

    with pytest.raises(ApiError):
        client._request("GET", "/v2/workouts")


def test_request_other_http_error_raises() -> None:
    oauth = _FakeOAuth()
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]
    client.rate_limiter = SimpleNamespace(wait_if_needed=lambda: None)  # type: ignore[assignment]
    client.session = _FakeSession([_FakeResponse(500, text="server error")])  # type: ignore[assignment]

    with pytest.raises(ApiError):
        client._request("GET", "/v2/workouts")


def test_list_workouts_pagination_and_max_items(monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = _FakeOAuth(user_id=None)
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]

    responses = iter(
        [
            _FakeResponse(200, payload=[{"id": 1}, {"id": 2}]),
            _FakeResponse(200, payload=[{"id": 3}]),
        ]
    )
    monkeypatch.setattr(client, "_request", lambda *a, **k: next(responses))

    workouts = client.list_workouts(page_size=2, max_items=3)
    assert [w["id"] for w in workouts] == [1, 2, 3]


def test_list_workouts_includes_start_and_end_date(monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = _FakeOAuth(user_id=None)
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]
    captured_params: list[dict] = []

    def _fake_request(method, endpoint, *, params=None, **kwargs):  # noqa: ANN001
        captured_params.append(dict(params or {}))
        return _FakeResponse(200, payload=[])

    monkeypatch.setattr(client, "_request", _fake_request)

    workouts = client.list_workouts(start_date="2026-01-01", end_date="2026-12-31", page_size=10)
    assert workouts == []
    assert captured_params[0]["startDate"] == "2026-01-01"
    assert captured_params[0]["endDate"] == "2026-12-31"


def test_list_workouts_breaks_on_empty_items(monkeypatch: pytest.MonkeyPatch) -> None:
    oauth = _FakeOAuth(user_id=None)
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]
    monkeypatch.setattr(client, "_request", lambda *a, **k: _FakeResponse(200, payload=[]))
    assert client.list_workouts(page_size=50) == []


def test_list_workouts_applies_owner_filter() -> None:
    oauth = _FakeOAuth(user_id="me")
    client = SuuntoApiClient(_settings(), oauth)  # type: ignore[arg-type]
    client._request = lambda *a, **k: _FakeResponse(200, payload=[{"id": 1, "userId": "me"}, {"id": 2, "userId": "other"}])  # type: ignore[method-assign]
    workouts = client.list_workouts(page_size=50)
    assert [w["id"] for w in workouts] == [1]


def test_effective_user_id_prefers_settings_override() -> None:
    settings = _settings()
    settings.owner_user_id = "forced-user"
    client = SuuntoApiClient(settings, _FakeOAuth(user_id="jwt-user"))  # type: ignore[arg-type]
    assert client._effective_user_id() == "forced-user"


def test_extract_owner_id_variants() -> None:
    assert SuuntoApiClient._extract_owner_id({"userId": "u1"}) == "u1"
    assert SuuntoApiClient._extract_owner_id({"user": {"id": "u2"}}) == "u2"
    assert SuuntoApiClient._extract_owner_id({"x": 1}) is None


def test_filter_for_current_user_keeps_unknown_owner() -> None:
    client = SuuntoApiClient(_settings(), _FakeOAuth(user_id="u1"))  # type: ignore[arg-type]
    workouts = [{"id": 1, "userId": "u1"}, {"id": 2}, {"id": 3, "userId": "u2"}]
    filtered = client._filter_for_current_user(workouts)
    assert [w["id"] for w in filtered] == [1, 2]


def test_extract_workout_items_variants() -> None:
    assert SuuntoApiClient._extract_workout_items([{"id": 1}, "x"]) == [{"id": 1}]
    assert SuuntoApiClient._extract_workout_items({"items": [{"id": 2}]}) == [{"id": 2}]
    assert SuuntoApiClient._extract_workout_items({"id": 3}) == [{"id": 3}]
    assert SuuntoApiClient._extract_workout_items("invalid") == []


def test_discover_urls_deduplicates_and_infers_type() -> None:
    payload = {
        "fitUrl": "https://cdn.example.com/workout.fit",
        "resources": [{"json_url": "https://cdn.example.com/workout.json"}],
        "duplicate": "https://cdn.example.com/workout.fit",
    }
    urls = SuuntoApiClient._discover_urls(payload)
    assert ("fit", "https://cdn.example.com/workout.fit") in urls
    assert ("json", "https://cdn.example.com/workout.json") in urls
    assert len(urls) == 2


def test_discover_urls_ignores_non_http_strings() -> None:
    urls = SuuntoApiClient._discover_urls({"fitUrl": "not-a-url"})
    assert urls == []


def test_url_filename_with_fallback() -> None:
    assert SuuntoApiClient._url_filename("https://x/y/file.fit", "fallback.fit") == "file.fit"
    assert SuuntoApiClient._url_filename("https://x", "fallback.fit") == "fallback.fit"


def test_workout_resource_urls_wrapper() -> None:
    client = SuuntoApiClient(_settings(), _FakeOAuth())  # type: ignore[arg-type]
    workout = {"fitUrl": "https://example.com/a.fit"}
    assert client.workout_resource_urls(workout) == [("fit", "https://example.com/a.fit")]


def test_download_resource_writes_streamed_content(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = SuuntoApiClient(_settings(), _FakeOAuth())  # type: ignore[arg-type]
    monkeypatch.setattr(
        client,
        "_request",
        lambda *a, **k: _FakeResponse(200, chunks=[b"a", b"", b"b"]),
    )
    destination = tmp_path / "download.fit"
    downloaded = client.download_resource("https://x/resource.fit", destination)

    assert downloaded == destination
    assert destination.read_bytes() == b"ab"


def test_download_workout_resources_builds_filenames(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = SuuntoApiClient(_settings(), _FakeOAuth())  # type: ignore[arg-type]
    monkeypatch.setattr(
        client,
        "workout_resource_urls",
        lambda workout: [
            ("fit", "https://example.com"),
            ("json", "https://example.com/file"),
        ],
    )

    created: list[Path] = []

    def _fake_download(url: str, destination: Path) -> Path:
        destination.write_bytes(url.encode("utf-8"))
        created.append(destination)
        return destination

    monkeypatch.setattr(client, "download_resource", _fake_download)

    workout = {"id": "w1"}
    files = client.download_workout_resources(workout, tmp_path)

    assert files == created
    assert created[0].name == "resource_1.fit"
    assert created[1].name == "file.json"
