from __future__ import annotations

import json
from pathlib import Path

import pytest

from suunto_export_activity.exceptions import ParseError
from suunto_export_activity.parsers.json_parser import parse_json_file


def test_parse_json_file_basic_payload(tmp_path: Path) -> None:
    payload = {
        "id": "A1",
        "type": "trail",
        "date": "2026-03-29T08:30:00Z",
        "duration": 5400,
        "distance": 15500,
        "elevation_gain": 800,
        "heart_rate": {"avg": 145, "max": 178},
        "laps": [
            {"lap_number": 1, "distance": 5000, "duration": 1650, "hr_avg": 140},
            {"lap_number": 2, "distance": 5000, "duration": 1700, "hr_avg": 147},
        ],
        "gps_track": [
            {"lat": 46.1, "lon": 6.2, "altitude": 745.2, "timestamp": "2026-03-29T08:31:00Z"}
        ],
    }
    file_path = tmp_path / "activity.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")

    records = parse_json_file(file_path)

    assert len(records) == 1
    activity = records[0]
    assert activity.activity_id == "A1"
    assert activity.type == "trail"
    assert activity.distance == 15.5
    assert activity.heart_rate.avg == 145
    assert len(activity.laps) == 2
    assert len(activity.gps_track) == 1


def test_parse_json_file_with_wrapped_items_and_external_metadata(tmp_path: Path) -> None:
    payload = {
        "activities": [
            {
                "activityId": "X1",
                "sport": "run",
                "startDate": "2026-03-30T10:00:00Z",
                "distanceMeters": 10000,
                "movingTime": "00:50:00",
                "avgHeartRate": 130,
                "maxHeartRate": 170,
                "metadata": {"source": "api"},
            }
        ]
    }
    file_path = tmp_path / "wrapped.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")

    records = parse_json_file(file_path, external_metadata={"id": "meta-id", "owner": "me"})
    record = records[0]

    assert record.activity_id == "X1"
    assert record.type == "run"
    assert record.duration == "00:50:00"
    assert record.heart_rate.avg == 130
    assert record.raw_metadata["owner"] == "me"
    assert record.raw_metadata["source"] == "api"


def test_parse_json_file_laps_gps_and_distance_heuristics(tmp_path: Path) -> None:
    payload = {
        "id": "A2",
        "distance": 15.5,
        "duration_s": 600,
        "splits": [
            {"index": 7, "distance": 5, "duration": 300, "maxHeartRate": 160},
            {"distance_m": 1500, "duration_s": 360, "avgHeartRate": 140},
            "invalid",
        ],
        "points": [
            {"latitude": 46.0, "longitude": 6.0, "time": "2026-03-30T10:00:00Z", "hr": 120},
            {"lat": 46.1},
            "invalid",
        ],
    }
    file_path = tmp_path / "heuristics.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")

    records = parse_json_file(file_path)
    activity = records[0]

    assert activity.distance == 15.5
    assert activity.duration == "00:10:00"
    assert len(activity.laps) == 2
    assert activity.laps[0].lap_number == 7
    assert activity.laps[0].pace_avg == "01:00/km"
    assert activity.laps[1].distance_km == 1.5
    assert len(activity.gps_track) == 1
    assert activity.gps_track[0].heart_rate == 120


def test_parse_json_file_invalid_json_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "invalid.json"
    file_path.write_text("{invalid", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_json_file(file_path)


def test_parse_json_file_invalid_root_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "root.json"
    file_path.write_text("123", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_json_file(file_path)


def test_parse_json_file_list_root_and_missing_optional_fields(tmp_path: Path) -> None:
    payload = [{"id": "A3", "type": "walk"}, "invalid"]
    file_path = tmp_path / "list.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")

    records = parse_json_file(file_path)
    assert len(records) == 1
    assert records[0].duration is None
    assert records[0].distance is None
