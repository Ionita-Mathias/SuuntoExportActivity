from pathlib import Path

from suunto_export_activity.exporter import export_activities
from suunto_export_activity.models import ActivityRecord


def test_export_activities(tmp_path: Path) -> None:
    activities = [ActivityRecord(activity_id="1", type="run", distance=10.0)]
    json_path, csv_path = export_activities(tmp_path, activities)

    assert json_path.exists()
    assert csv_path.exists()
    assert "activity_id" in csv_path.read_text(encoding="utf-8")
