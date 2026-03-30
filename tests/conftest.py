import os

import pytest

from suunto_export_activity.i18n import set_language


@pytest.fixture(autouse=True)
def _reset_language_and_suunto_env(monkeypatch: pytest.MonkeyPatch) -> None:
    set_language("en")
    for key in list(os.environ):
        if key.startswith("SUUNTO_"):
            monkeypatch.delenv(key, raising=False)
