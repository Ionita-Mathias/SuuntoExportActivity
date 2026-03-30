"""High-level processing pipeline for activity files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .exceptions import ParseError
from .models import ActivityRecord
from .parsers import parse_fit_file, parse_json_file


def parse_activity_file(
    file_path: Path,
    *,
    max_hr: int | None = None,
    external_metadata: dict[str, Any] | None = None,
) -> list[ActivityRecord]:
    suffix = file_path.suffix.lower()
    if suffix == ".fit":
        return [parse_fit_file(file_path, max_hr=max_hr, external_metadata=external_metadata)]
    if suffix == ".json":
        return parse_json_file(file_path, external_metadata=external_metadata)
    raise ParseError(f"Unsupported file extension '{file_path.suffix}' for {file_path}")


def parse_many_files(
    files: list[Path],
    *,
    max_hr: int | None = None,
    metadata_by_stem: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[ActivityRecord], list[str]]:
    activities: list[ActivityRecord] = []
    errors: list[str] = []

    for file_path in files:
        external_metadata = (metadata_by_stem or {}).get(file_path.stem)
        try:
            activities.extend(
                parse_activity_file(
                    file_path,
                    max_hr=max_hr,
                    external_metadata=external_metadata,
                )
            )
        except ParseError as exc:
            errors.append(str(exc))

    return activities, errors


def discover_activity_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]

    files = [*path.rglob("*.fit"), *path.rglob("*.json")]
    return sorted({f.resolve() for f in files})
