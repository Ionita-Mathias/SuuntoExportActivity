from __future__ import annotations

import pytest

from suunto_export_activity.compliance import (
    get_compatibility_banner,
    normalize_bool,
    require_explicit_consent,
)
from suunto_export_activity.exceptions import ConsentError
from suunto_export_activity.i18n import set_language


def test_get_compatibility_banner() -> None:
    set_language("en")
    banner = get_compatibility_banner()
    assert "SuuntoExportActivity" in banner
    assert "Compatible with Suunto" in banner


@pytest.mark.parametrize(
    ("value", "default", "expected"),
    [
        ("1", False, True),
        ("yes", False, True),
        ("oui", False, True),
        ("0", True, False),
        ("no", True, False),
        ("non", True, False),
        ("unknown", True, True),
        (None, False, False),
    ],
)
def test_normalize_bool(value: str | None, default: bool, expected: bool) -> None:
    assert normalize_bool(value, default) is expected


def test_require_explicit_consent_skips_when_disabled() -> None:
    require_explicit_consent(enabled=False, auto_yes=False, action_label="export")


def test_require_explicit_consent_skips_when_auto_yes() -> None:
    require_explicit_consent(enabled=True, auto_yes=True, action_label="export")


def test_require_explicit_consent_accepts_input(monkeypatch: pytest.MonkeyPatch) -> None:
    set_language("en")
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    require_explicit_consent(enabled=True, auto_yes=False, action_label="export")


def test_require_explicit_consent_rejects_input(monkeypatch: pytest.MonkeyPatch) -> None:
    set_language("fr")
    monkeypatch.setattr("builtins.input", lambda _: "non")
    with pytest.raises(ConsentError):
        require_explicit_consent(enabled=True, auto_yes=False, action_label="export")
