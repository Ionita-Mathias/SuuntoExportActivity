"""Compliance helpers for personal Suunto data processing."""

from __future__ import annotations

from .exceptions import ConsentError


COMPATIBILITY_BANNER = (
    "SuuntoExportActivity\n"
    "Compatible with Suunto\n"
    "Personal use only. Suunto Cloud API is provided as-is without warranty."
)


def normalize_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    return default


def require_explicit_consent(*, enabled: bool, auto_yes: bool, action_label: str) -> None:
    if not enabled or auto_yes:
        return

    print("\nData processing consent required")
    print("This tool exports and processes your personal Suunto activity data locally.")
    answer = input(f"Type YES to continue with '{action_label}': ").strip()
    if answer != "YES":
        raise ConsentError("Operation cancelled: explicit consent not granted.")
