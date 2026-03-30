from __future__ import annotations

from suunto_export_activity.models import ActivityRecord, GpsPoint, HeartRateSummary, LapSummary


def test_activity_record_to_dict_drops_none_values() -> None:
    record = ActivityRecord(
        activity_id="A1",
        type="trail",
        heart_rate=HeartRateSummary(avg=145, max=None, zones={"z1": 1}),
        laps=[LapSummary(lap_number=1, distance_km=5.0, hr_avg=None)],
        gps_track=[GpsPoint(lat=46.1, lon=6.2, altitude=None)],
    )

    payload = record.to_dict()

    assert payload["activity_id"] == "A1"
    assert payload["heart_rate"]["avg"] == 145
    assert "max" not in payload["heart_rate"]
    assert "hr_avg" not in payload["laps"][0]
    assert "altitude" not in payload["gps_track"][0]
