"""Parser for JSON activity files into normalized ActivityRecord."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..exceptions import ParseError
from ..models import ActivityRecord, GpsPoint, HeartRateSummary, LapSummary
from ..utils import datetime_to_iso, format_pace, parse_datetime, safe_float, safe_int, seconds_to_hhmmss


def _first(payload: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in payload and payload[key] is not None:
            return payload[key]
    return None


def _extract_heart_rate(payload: dict[str, Any]) -> HeartRateSummary:
    hr_node = _first(payload, ["heart_rate", "heartRate", "heartrate"])
    if isinstance(hr_node, dict):
        return HeartRateSummary(
            avg=safe_int(_first(hr_node, ["avg", "average", "mean"])),
            max=safe_int(_first(hr_node, ["max", "maximum"])),
            zones=hr_node.get("zones") if isinstance(hr_node.get("zones"), dict) else {},
        )

    return HeartRateSummary(
        avg=safe_int(_first(payload, ["avg_hr", "averageHeartRate", "avgHeartRate"])),
        max=safe_int(_first(payload, ["max_hr", "maxHeartRate"])),
        zones={},
    )


def _extract_laps(payload: dict[str, Any]) -> list[LapSummary]:
    lap_nodes = _first(payload, ["laps", "intervals", "kmSplits", "splits"])
    if not isinstance(lap_nodes, list):
        return []

    laps: list[LapSummary] = []
    for idx, lap in enumerate(lap_nodes, start=1):
        if not isinstance(lap, dict):
            continue

        distance_m = safe_float(
            _first(lap, ["distance", "distance_m", "distanceMeters", "total_distance"])
        )
        distance_km = None
        if distance_m is not None:
            # Heuristic: if value is tiny, it might already be km.
            distance_km = distance_m if distance_m < 100 else (distance_m / 1000)

        duration_s = safe_float(
            _first(lap, ["duration", "duration_s", "elapsed", "movingTime", "total_timer_time"])
        )
        pace = None
        if duration_s and distance_km and distance_km > 0:
            pace = format_pace(duration_s / distance_km)

        laps.append(
            LapSummary(
                lap_number=safe_int(_first(lap, ["lap_number", "lap", "index"])) or idx,
                distance_km=round(distance_km, 3) if distance_km is not None else None,
                duration_s=duration_s,
                pace_avg=pace,
                hr_avg=safe_int(_first(lap, ["hr_avg", "avg_hr", "avgHeartRate"])),
                hr_max=safe_int(_first(lap, ["hr_max", "max_hr", "maxHeartRate"])),
                elevation_gain=safe_float(_first(lap, ["elevation_gain", "gain", "ascent"])),
            )
        )

    return laps


def _extract_gps(payload: dict[str, Any]) -> list[GpsPoint]:
    gps_nodes = _first(payload, ["gps_track", "track", "records", "samples", "points"])
    if not isinstance(gps_nodes, list):
        return []

    points: list[GpsPoint] = []
    for node in gps_nodes:
        if not isinstance(node, dict):
            continue
        lat = safe_float(_first(node, ["lat", "latitude", "position_lat"]))
        lon = safe_float(_first(node, ["lon", "lng", "longitude", "position_long"]))
        if lat is None or lon is None:
            continue
        points.append(
            GpsPoint(
                lat=lat,
                lon=lon,
                altitude=safe_float(_first(node, ["altitude", "alt"])),
                timestamp=datetime_to_iso(parse_datetime(_first(node, ["timestamp", "time"]))),
                heart_rate=safe_int(_first(node, ["heart_rate", "hr"])),
                cadence=safe_int(_first(node, ["cadence"])),
            )
        )
    return points


def _normalize_duration(payload: dict[str, Any]) -> str | None:
    raw = _first(payload, ["duration", "duration_s", "elapsedTime", "movingTime", "total_timer_time"])
    if raw is None:
        return None
    if isinstance(raw, str) and ":" in raw:
        return raw
    return seconds_to_hhmmss(safe_float(raw))


def _normalize_distance_km(payload: dict[str, Any]) -> float | None:
    distance_value = _first(payload, ["distance", "distance_m", "distanceMeters", "total_distance"])
    distance_float = safe_float(distance_value)
    if distance_float is None:
        return None
    if distance_float < 100:
        return round(distance_float, 3)
    return round(distance_float / 1000, 3)


def parse_json_file(
    file_path: Path,
    *,
    external_metadata: dict[str, Any] | None = None,
) -> list[ActivityRecord]:
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"Failed to load JSON file {file_path}: {exc}") from exc

    items: list[dict[str, Any]]
    if isinstance(payload, list):
        items = [x for x in payload if isinstance(x, dict)]
    elif isinstance(payload, dict):
        for key in ("activities", "workouts", "items", "data"):
            nested = payload.get(key)
            if isinstance(nested, list):
                items = [x for x in nested if isinstance(x, dict)]
                break
        else:
            items = [payload]
    else:
        raise ParseError(f"JSON root in {file_path} is not an object or array.")

    records: list[ActivityRecord] = []

    for item in items:
        metadata = dict(external_metadata or {})
        metadata.update(item.get("metadata") if isinstance(item.get("metadata"), dict) else {})

        date_dt = parse_datetime(_first(item, ["date", "start_date", "startDate", "startTime"]))
        activity_id = _first(item, ["id", "activity_id", "activityId", "workoutId"]) or file_path.stem

        record = ActivityRecord(
            activity_id=str(activity_id),
            type=str(_first(item, ["type", "sport", "activityType", "sportMode"]) or "unknown"),
            date=date_dt.date().isoformat() if date_dt else None,
            duration=_normalize_duration(item),
            distance=_normalize_distance_km(item),
            elevation_gain=safe_float(_first(item, ["elevation_gain", "total_ascent", "ascent", "gain"])),
            elevation_loss=safe_float(_first(item, ["elevation_loss", "total_descent", "descent", "loss"])),
            heart_rate=_extract_heart_rate(item),
            laps=_extract_laps(item),
            gps_track=_extract_gps(item),
            notes=str(_first(item, ["notes", "comment", "feeling"]) or "") or None,
            equipment=str(_first(item, ["equipment", "gear", "shoes"]) or "") or None,
            source_file=str(file_path),
            raw_metadata=metadata,
        )
        records.append(record)

    return records
