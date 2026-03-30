from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from suunto_export_activity.utils import (
    datetime_to_iso,
    ensure_directory,
    format_pace,
    load_env_file,
    parse_datetime,
    safe_float,
    safe_int,
    seconds_to_hhmmss,
)


def test_load_env_file_reads_values_without_overriding_existing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# comment",
                "SUUNTO_CLIENT_ID=from_file",
                "SUUNTO_CLIENT_SECRET='secret'",
                'SUUNTO_SUBSCRIPTION_KEY="sub"',
                "INVALID_LINE",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("SUUNTO_CLIENT_ID", "from_env")
    load_env_file(env_path)

    assert "from_env" == __import__("os").environ["SUUNTO_CLIENT_ID"]
    assert "secret" == __import__("os").environ["SUUNTO_CLIENT_SECRET"]
    assert "sub" == __import__("os").environ["SUUNTO_SUBSCRIPTION_KEY"]


def test_load_env_file_missing_is_noop(tmp_path: Path) -> None:
    load_env_file(tmp_path / "missing.env")


def test_ensure_directory_creates_and_returns_path(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "dir"
    resolved = ensure_directory(target)
    assert target.exists()
    assert resolved == target


def test_parse_datetime_variants() -> None:
    aware = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)
    naive = datetime(2026, 3, 30, 12, 0)

    assert parse_datetime(None) is None
    assert parse_datetime(aware) == aware
    assert parse_datetime(naive).tzinfo == timezone.utc
    assert parse_datetime(0).isoformat().endswith("+00:00")
    assert parse_datetime("2026-03-30T12:00:00Z").isoformat().endswith("+00:00")
    assert parse_datetime("   ") is None
    assert parse_datetime("invalid-date") is None
    assert parse_datetime(object()) is None


def test_datetime_to_iso_formats_utc() -> None:
    dt = datetime(2026, 3, 30, 12, 0, tzinfo=timezone.utc)
    assert datetime_to_iso(dt) == "2026-03-30T12:00:00Z"
    assert datetime_to_iso(None) is None


def test_seconds_to_hhmmss_edges() -> None:
    assert seconds_to_hhmmss(None) is None
    assert seconds_to_hhmmss(-1) is None
    assert seconds_to_hhmmss(3661) == "01:01:01"
    assert seconds_to_hhmmss(0.6) == "00:00:01"


def test_format_pace_edges() -> None:
    assert format_pace(None) is None
    assert format_pace(0) is None
    assert format_pace(305.2) == "05:05/km"


def test_safe_float_and_safe_int() -> None:
    assert safe_float("1.5") == 1.5
    assert safe_float("x") is None
    assert safe_float(None) is None

    assert safe_int("12") == 12
    assert safe_int("x") is None
    assert safe_int(None) is None
