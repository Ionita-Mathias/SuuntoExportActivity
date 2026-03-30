from suunto_export_activity.i18n import detect_system_language, resolve_language, set_language, t


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


def test_translation_switch() -> None:
    set_language("fr")
    assert "Compatible avec Suunto" == t("banner.compatible")

    set_language("en")
    assert "Compatible with Suunto" == t("banner.compatible")
