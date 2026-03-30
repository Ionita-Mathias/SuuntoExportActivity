"""Compliance helpers for personal Suunto data processing."""

from __future__ import annotations

from .exceptions import ConsentError
from .i18n import t


def get_compatibility_banner() -> str:
    return "\n".join(
        [
            t("banner.title"),
            t("banner.compatible"),
            t("banner.usage"),
        ]
    )


def normalize_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on", "oui", "o"}:
        return True
    if lowered in {"0", "false", "no", "n", "off", "non"}:
        return False
    return default


def require_explicit_consent(*, enabled: bool, auto_yes: bool, action_label: str) -> None:
    if not enabled or auto_yes:
        return

    print(f"\n{t('consent.title')}")
    print(t("consent.body"))
    expected = t("consent.expected_token")
    answer = input(t("consent.prompt", expected=expected, action_label=action_label)).strip()
    if answer.upper() != expected.upper():
        raise ConsentError(t("consent.cancelled"))
