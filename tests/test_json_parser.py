from pathlib import Path

from suunto_export_activity.parsers.json_parser import parse_json_file


def test_parse_json_file(tmp_path: Path) -> None:
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
    file_path.write_text(__import__("json").dumps(payload), encoding="utf-8")

    records = parse_json_file(file_path)

    assert len(records) == 1
    activity = records[0]
    assert activity.activity_id == "A1"
    assert activity.type == "trail"
    assert activity.distance == 15.5
    assert activity.heart_rate.avg == 145
    assert len(activity.laps) == 2
    assert len(activity.gps_track) == 1
