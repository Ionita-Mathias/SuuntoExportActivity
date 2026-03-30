from __future__ import annotations

import runpy

import pytest


def test_package_main_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("suunto_export_activity.cli.main", lambda argv: 0)
    monkeypatch.setattr("sys.argv", ["suunto-export"])

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("suunto_export_activity.__main__", run_name="__main__")

    assert exc.value.code == 0
