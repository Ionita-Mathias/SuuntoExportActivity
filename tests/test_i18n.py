import locale

from suunto_export_activity.i18n import detect_system_language, get_language, resolve_language, set_language, t


def test_resolve_language_explicit() -> None:
    assert resolve_language("fr") == "fr"
    assert resolve_language("en") == "en"
    assert resolve_language("fr_CH") == "fr"
    assert resolve_language("en_US") == "en"


def test_detect_system_language_from_env(monkeypatch) -> None:
    monkeypatch.setenv("LANG", "fr_CH.UTF-8")
    assert detect_system_language() == "fr"

    monkeypatch.setenv("LANG", "de_CH.UTF-8")
    assert detect_system_language() == "en"


def test_detect_system_language_from_locale_fallback(monkeypatch) -> None:
    monkeypatch.delenv("LANG", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setattr(locale, "getlocale", lambda: ("fr_CH", "UTF-8"))
    assert detect_system_language() == "fr"


def test_detect_system_language_when_locale_raises(monkeypatch) -> None:
    monkeypatch.delenv("LANG", raising=False)
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.setattr(locale, "getlocale", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert detect_system_language() == "en"


def test_resolve_language_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("SUUNTO_LANG", "fr_FR")
    assert resolve_language(None) == "fr"


def test_resolve_language_with_blank_preferred_uses_fallback(monkeypatch) -> None:
    monkeypatch.setenv("SUUNTO_LANG", "en_US")
    assert resolve_language("   ") == "en"


def test_translation_switch() -> None:
    set_language("fr")
    assert "Compatible avec Suunto" == t("banner.compatible")

    set_language("en")
    assert "Compatible with Suunto" == t("banner.compatible")


def test_get_language_and_translation_fallback() -> None:
    set_language("en")
    assert get_language() == "en"
    assert t("unknown.key") == "unknown.key"


def test_translation_format_failure_returns_template() -> None:
    set_language("en")
    # Missing kwargs for template placeholders should gracefully return template.
    assert "{expected}" in t("consent.prompt")
