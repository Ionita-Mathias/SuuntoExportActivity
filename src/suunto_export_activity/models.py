"""Data models for normalized activities."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _drop_none(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _drop_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_drop_none(v) for v in value]
    return value


@dataclass(slots=True)
class HeartRateSummary:
    avg: int | None = None
    max: int | None = None
    zones: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class LapSummary:
    lap_number: int
    distance_km: float | None = None
    duration_s: float | None = None
    pace_avg: str | None = None
    hr_avg: int | None = None
    hr_max: int | None = None
    elevation_gain: float | None = None


@dataclass(slots=True)
class GpsPoint:
    lat: float
    lon: float
    altitude: float | None = None
    timestamp: str | None = None
    heart_rate: int | None = None
    cadence: int | None = None


@dataclass(slots=True)
class ActivityRecord:
    activity_id: str
    type: str | None = None
    date: str | None = None
    duration: str | None = None
    distance: float | None = None
    elevation_gain: float | None = None
    elevation_loss: float | None = None
    heart_rate: HeartRateSummary = field(default_factory=HeartRateSummary)
    laps: list[LapSummary] = field(default_factory=list)
    gps_track: list[GpsPoint] = field(default_factory=list)
    notes: str | None = None
    equipment: str | None = None
    source_file: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return _drop_none(payload)
