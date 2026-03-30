from __future__ import annotations

import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

from suunto_export_activity.exceptions import ParseError
from suunto_export_activity.parsers.fit_parser import (
    _compute_hr_zones,
    _latlon_to_deg,
    parse_fit_file,
)


class _Field:
    def __init__(self, name: str, value) -> None:  # noqa: ANN001
        self.name = name
        self.value = value


class _Message:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __iter__(self):
        for key, value in self.payload.items():
            yield _Field(key, value)


class _FakeFitFile:
    def __init__(self, _path: str) -> None:
        self.session = [
            _Message(
                {
                    "total_timer_time": 3600,
                    "total_distance": 10000,
                    "total_ascent": 500,
                    "total_descent": 450,
                    "start_time": datetime(2026, 3, 30, 10, 0, tzinfo=timezone.utc),
                    "sport": "running",
                    "sub_sport": "trail",
                }
            )
        ]
        self.laps = [
            _Message(
                {
                    "total_distance": 5000,
                    "total_timer_time": 1800,
                    "avg_heart_rate": 140,
                    "max_heart_rate": 160,
                    "total_ascent": 200,
                }
            )
        ]
        self.records = [
            _Message(
                {
                    "position_lat": 46.1,
                    "position_long": 6.2,
                    "altitude": 800.5,
                    "timestamp": datetime(2026, 3, 30, 10, 1, tzinfo=timezone.utc),
                    "heart_rate": 130,
                    "cadence": 80,
                }
            ),
            _Message(
                {
                    "position_lat": int(0.5 * (2**31) / 180.0),
                    "position_long": int(0.2 * (2**31) / 180.0),
                    "heart_rate": 150,
                }
            ),
        ]

    def get_messages(self, name: str):
        if name == "session":
            return list(self.session)
        if name == "lap":
            return list(self.laps)
        if name == "record":
            return list(self.records)
        return []


class _FakeFitFileAvgSpeedAndMissingGps:
    def __init__(self, _path: str) -> None:
        self.session = [_Message({"total_timer_time": 600, "total_distance": 2000})]
        self.laps = [_Message({"avg_speed": 3.0, "total_distance": 1000})]
        self.records = [_Message({"heart_rate": 120})]

    def get_messages(self, name: str):
        if name == "session":
            return list(self.session)
        if name == "lap":
            return list(self.laps)
        if name == "record":
            return list(self.records)
        return []


def _install_fake_fitparse(monkeypatch: pytest.MonkeyPatch, fit_file_class) -> None:  # noqa: ANN001
    module = types.ModuleType("fitparse")
    module.FitFile = fit_file_class
    monkeypatch.setitem(sys.modules, "fitparse", module)


def test_latlon_to_deg() -> None:
    assert _latlon_to_deg(46.1) == 46.1
    semicircle = int(1.0 * (2**31) / 180.0)
    assert _latlon_to_deg(semicircle) == pytest.approx(1.0, rel=1e-5)
    assert _latlon_to_deg("invalid") is None


def test_compute_hr_zones() -> None:
    zones = _compute_hr_zones([100, 120, 140, 160, 180], max_hr=200)
    assert zones == {"z1": 1, "z2": 1, "z3": 1, "z4": 1, "z5": 1}
    assert _compute_hr_zones([], max_hr=200) == {}
    assert _compute_hr_zones([0], max_hr=0) == {}


def test_parse_fit_file_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_fake_fitparse(monkeypatch, _FakeFitFile)
    file_path = tmp_path / "activity.fit"
    file_path.write_bytes(b"fake-fit")

    record = parse_fit_file(
        file_path,
        max_hr=190,
        external_metadata={"id": "ext-id", "notes": "good", "equipment": "shoes"},
    )

    assert record.activity_id == "ext-id"
    assert record.type == "trail"
    assert record.date == "2026-03-30"
    assert record.duration == "01:00:00"
    assert record.distance == 10.0
    assert record.elevation_gain == 500.0
    assert record.heart_rate.avg == 140
    assert record.heart_rate.max == 150
    assert len(record.laps) == 1
    assert len(record.gps_track) == 2
    assert record.notes == "good"
    assert record.equipment == "shoes"
    assert record.raw_metadata["id"] == "ext-id"


def test_parse_fit_file_wraps_exceptions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _BrokenFitFile:
        def __init__(self, _path: str) -> None:
            raise RuntimeError("boom")

    _install_fake_fitparse(monkeypatch, _BrokenFitFile)

    file_path = tmp_path / "broken.fit"
    file_path.write_bytes(b"x")

    with pytest.raises(ParseError):
        parse_fit_file(file_path)


def test_parse_fit_file_uses_avg_speed_and_skips_missing_gps(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_fitparse(monkeypatch, _FakeFitFileAvgSpeedAndMissingGps)
    file_path = tmp_path / "avg.fit"
    file_path.write_bytes(b"x")

    record = parse_fit_file(file_path)
    assert record.laps[0].pace_avg == "05:33/km"
    assert record.gps_track == []
