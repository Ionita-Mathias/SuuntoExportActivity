from __future__ import annotations

from pathlib import Path

import pytest

from suunto_export_activity.exceptions import ParseError
from suunto_export_activity.models import ActivityRecord
from suunto_export_activity.processor import discover_activity_files, parse_activity_file, parse_many_files


def test_parse_activity_file_dispatches_fit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    file_path = tmp_path / "activity.fit"
    file_path.write_bytes(b"x")
    expected = ActivityRecord(activity_id="fit-1")
    monkeypatch.setattr("suunto_export_activity.processor.parse_fit_file", lambda *a, **k: expected)

    records = parse_activity_file(file_path, max_hr=190, external_metadata={"k": "v"})
    assert records == [expected]


def test_parse_activity_file_dispatches_json(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    file_path = tmp_path / "activity.json"
    file_path.write_text("[]", encoding="utf-8")
    expected = [ActivityRecord(activity_id="json-1")]
    monkeypatch.setattr("suunto_export_activity.processor.parse_json_file", lambda *a, **k: expected)

    records = parse_activity_file(file_path)
    assert records == expected


def test_parse_activity_file_unsupported_extension(tmp_path: Path) -> None:
    file_path = tmp_path / "activity.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(ParseError):
        parse_activity_file(file_path)


def test_parse_many_files_collects_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ok_file = tmp_path / "ok.fit"
    bad_file = tmp_path / "bad.fit"
    ok_file.write_bytes(b"x")
    bad_file.write_bytes(b"x")

    def _fake_parse(file_path: Path, **kwargs):  # noqa: ANN001
        if file_path == bad_file:
            raise ParseError("bad parse")
        return [ActivityRecord(activity_id=file_path.stem)]

    monkeypatch.setattr("suunto_export_activity.processor.parse_activity_file", _fake_parse)

    records, errors = parse_many_files(
        [ok_file, bad_file],
        metadata_by_stem={"ok": {"id": "ok"}},
    )

    assert [r.activity_id for r in records] == ["ok"]
    assert errors == ["bad parse"]


def test_discover_activity_files_for_file(tmp_path: Path) -> None:
    file_path = tmp_path / "single.fit"
    file_path.write_bytes(b"x")
    assert discover_activity_files(file_path) == [file_path]


def test_discover_activity_files_for_directory(tmp_path: Path) -> None:
    fit_file = tmp_path / "a.fit"
    json_file = tmp_path / "nested" / "b.json"
    fit_file.write_bytes(b"x")
    json_file.parent.mkdir(parents=True)
    json_file.write_text("{}", encoding="utf-8")

    files = discover_activity_files(tmp_path)
    assert fit_file.resolve() in files
    assert json_file.resolve() in files
