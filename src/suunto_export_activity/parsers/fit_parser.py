"""FIT file parser to normalized ActivityRecord."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..exceptions import ParseError
from ..models import ActivityRecord, GpsPoint, HeartRateSummary, LapSummary
from ..utils import datetime_to_iso, format_pace, parse_datetime, safe_float, safe_int, seconds_to_hhmmss

_SEMICIRCLE_TO_DEG = 180.0 / (2**31)


def _message_to_dict(message: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for field in message:
        payload[field.name] = field.value
    return payload


def _latlon_to_deg(value: Any) -> float | None:
    numeric = safe_float(value)
    if numeric is None:
        return None
    # Some parsers expose lat/lon directly in degrees, others as FIT semicircles.
    if abs(numeric) <= 180:
        return numeric
    return numeric * _SEMICIRCLE_TO_DEG


def _compute_hr_zones(hr_samples: list[int], max_hr: int | None) -> dict[str, int]:
    if not hr_samples:
        return {}

    inferred_max_hr = max_hr or max(hr_samples)
    if inferred_max_hr <= 0:
        return {}

    zones = {
        "z1": 0,  # < 60%
        "z2": 0,  # 60-70%
        "z3": 0,  # 70-80%
        "z4": 0,  # 80-90%
        "z5": 0,  # >= 90%
    }

    for hr in hr_samples:
        ratio = hr / inferred_max_hr
        if ratio < 0.60:
            zones["z1"] += 1
        elif ratio < 0.70:
            zones["z2"] += 1
        elif ratio < 0.80:
            zones["z3"] += 1
        elif ratio < 0.90:
            zones["z4"] += 1
        else:
            zones["z5"] += 1

    return zones


def parse_fit_file(
    file_path: Path,
    *,
    max_hr: int | None = None,
    external_metadata: dict[str, Any] | None = None,
) -> ActivityRecord:
    try:
        from fitparse import FitFile

        fit_file = FitFile(str(file_path))

        session_data: dict[str, Any] = {}
        for msg in fit_file.get_messages("session"):
            session_data = _message_to_dict(msg)
            if session_data:
                break

        laps: list[LapSummary] = []
        for index, lap_msg in enumerate(fit_file.get_messages("lap"), start=1):
            lap = _message_to_dict(lap_msg)
            distance_m = safe_float(lap.get("total_distance"))
            duration_s = safe_float(lap.get("total_timer_time") or lap.get("total_elapsed_time"))
            avg_speed = safe_float(lap.get("avg_speed"))
            pace = None
            if duration_s and distance_m and distance_m > 0:
                pace = format_pace((duration_s / distance_m) * 1000)
            elif avg_speed and avg_speed > 0:
                pace = format_pace(1000 / avg_speed)

            laps.append(
                LapSummary(
                    lap_number=index,
                    distance_km=round(distance_m / 1000, 3) if distance_m else None,
                    duration_s=duration_s,
                    pace_avg=pace,
                    hr_avg=safe_int(lap.get("avg_heart_rate")),
                    hr_max=safe_int(lap.get("max_heart_rate")),
                    elevation_gain=safe_float(lap.get("total_ascent")),
                )
            )

        track: list[GpsPoint] = []
        hr_samples: list[int] = []

        for record_msg in fit_file.get_messages("record"):
            record = _message_to_dict(record_msg)

            hr = safe_int(record.get("heart_rate"))
            if hr is not None:
                hr_samples.append(hr)

            lat = _latlon_to_deg(record.get("position_lat"))
            lon = _latlon_to_deg(record.get("position_long"))
            if lat is None or lon is None:
                continue

            track.append(
                GpsPoint(
                    lat=round(lat, 7),
                    lon=round(lon, 7),
                    altitude=safe_float(record.get("altitude")),
                    timestamp=datetime_to_iso(parse_datetime(record.get("timestamp"))),
                    heart_rate=hr,
                    cadence=safe_int(record.get("cadence")),
                )
            )

        duration_s = safe_float(session_data.get("total_timer_time") or session_data.get("total_elapsed_time"))
        distance_m = safe_float(session_data.get("total_distance"))

        avg_hr = safe_int(session_data.get("avg_heart_rate"))
        max_hr_session = safe_int(session_data.get("max_heart_rate"))

        if avg_hr is None and hr_samples:
            avg_hr = int(round(sum(hr_samples) / len(hr_samples)))
        if max_hr_session is None and hr_samples:
            max_hr_session = max(hr_samples)

        heart_rate = HeartRateSummary(
            avg=avg_hr,
            max=max_hr_session,
            zones=_compute_hr_zones(hr_samples, max_hr=max_hr),
        )

        start_dt = parse_datetime(
            session_data.get("start_time")
            or session_data.get("timestamp")
            or session_data.get("local_timestamp")
        )

        sport = session_data.get("sport")
        sub_sport = session_data.get("sub_sport")
        activity_type = str(sub_sport or sport or "unknown")

        metadata = {
            "sport": sport,
            "sub_sport": sub_sport,
            "manufacturer": session_data.get("manufacturer"),
            "event": session_data.get("event"),
        }
        if external_metadata:
            metadata.update(external_metadata)

        record = ActivityRecord(
            activity_id=str(
                (external_metadata or {}).get("id")
                or (external_metadata or {}).get("workoutId")
                or file_path.stem
            ),
            type=activity_type,
            date=start_dt.date().isoformat() if start_dt else None,
            duration=seconds_to_hhmmss(duration_s),
            distance=round(distance_m / 1000, 3) if distance_m else None,
            elevation_gain=safe_float(session_data.get("total_ascent")),
            elevation_loss=safe_float(session_data.get("total_descent")),
            heart_rate=heart_rate,
            laps=laps,
            gps_track=track,
            notes=(external_metadata or {}).get("notes"),
            equipment=(external_metadata or {}).get("equipment"),
            source_file=str(file_path),
            raw_metadata=metadata,
        )
        return record
    except Exception as exc:  # noqa: BLE001 - bubble up as domain exception
        raise ParseError(f"Failed to parse FIT file {file_path}: {exc}") from exc
