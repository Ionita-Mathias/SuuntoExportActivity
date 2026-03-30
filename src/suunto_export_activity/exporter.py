"""Export normalized activities into JSON and CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import ActivityRecord
from .utils import ensure_directory


CSV_COLUMNS = [
    "activity_id",
    "type",
    "date",
    "duration",
    "distance_km",
    "elevation_gain",
    "elevation_loss",
    "hr_avg",
    "hr_max",
    "lap_count",
    "gps_points",
    "notes",
    "equipment",
    "source_file",
]


def export_activities(output_dir: Path, activities: list[ActivityRecord]) -> tuple[Path, Path]:
    ensure_directory(output_dir)

    json_path = output_dir / "activities.json"
    csv_path = output_dir / "activities.csv"

    json_payload = [activity.to_dict() for activity in activities]
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for activity in activities:
            writer.writerow(
                {
                    "activity_id": activity.activity_id,
                    "type": activity.type,
                    "date": activity.date,
                    "duration": activity.duration,
                    "distance_km": activity.distance,
                    "elevation_gain": activity.elevation_gain,
                    "elevation_loss": activity.elevation_loss,
                    "hr_avg": activity.heart_rate.avg,
                    "hr_max": activity.heart_rate.max,
                    "lap_count": len(activity.laps),
                    "gps_points": len(activity.gps_track),
                    "notes": activity.notes,
                    "equipment": activity.equipment,
                    "source_file": activity.source_file,
                }
            )

    return json_path, csv_path
