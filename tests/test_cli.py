from __future__ import annotations

import argparse
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

from suunto_export_activity.cli import (
    _bootstrap_language_and_env,
    _configure_logging,
    _load_settings,
    _persist_fallback_workout_json,
    _require_consent_if_needed,
    _resolve_consent_auto_yes,
    _resolve_encrypt_choice,
    _show_banner,
    _workout_metadata,
    build_parser,
    cmd_auth_url,
    cmd_delete_data,
    cmd_exchange_code,
    cmd_export,
    cmd_parse_local,
    main,
)
from suunto_export_activity.exceptions import ApiError, ConfigError
from suunto_export_activity.models import ActivityRecord


def _settings(tmp_path: Path, **overrides) -> SimpleNamespace:
    base = {
        "token_storage_mode": "memory",
        "token_path": tmp_path / "token.json",
        "max_hr": None,
        "default_encrypt_export": False,
        "export_passphrase": None,
        "require_consent": False,
        "log_file": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_bootstrap_language_and_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_path = tmp_path / ".env.custom"
    env_path.write_text("", encoding="utf-8")

    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        "suunto_export_activity.cli.load_env_file",
        lambda path: calls.append(("env", path)),
    )
    monkeypatch.setattr(
        "suunto_export_activity.cli.set_language",
        lambda lang=None: calls.append(("lang", lang)),
    )

    _bootstrap_language_and_env(["--env-file", str(env_path), "--lang", "fr", "export"])

    assert calls[0] == ("env", env_path)
    assert calls[1] == ("lang", "fr")


def test_configure_logging_with_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "app.log"
    ensured: list[Path] = []
    basic_config_calls: list[dict] = []

    monkeypatch.setattr("suunto_export_activity.cli.ensure_directory", lambda path: ensured.append(path))
    monkeypatch.setattr(
        "suunto_export_activity.cli.logging.basicConfig",
        lambda **kwargs: basic_config_calls.append(kwargs),
    )
    monkeypatch.setattr(
        "suunto_export_activity.cli.logging.FileHandler",
        lambda *a, **k: object(),
    )

    _configure_logging(verbose=True, log_file=log_file)

    assert ensured == [log_file.resolve().parent]
    assert basic_config_calls
    assert basic_config_calls[0]["level"] == 10
    assert len(basic_config_calls[0]["handlers"]) == 2


def test_configure_logging_without_file(monkeypatch: pytest.MonkeyPatch) -> None:
    basic_config_calls: list[dict] = []
    monkeypatch.setattr(
        "suunto_export_activity.cli.logging.basicConfig",
        lambda **kwargs: basic_config_calls.append(kwargs),
    )
    _configure_logging(verbose=False, log_file=None)
    assert basic_config_calls[0]["level"] == 20
    assert len(basic_config_calls[0]["handlers"]) == 1


def test_show_banner(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr("suunto_export_activity.cli.get_compatibility_banner", lambda: "BANNER")
    _show_banner()
    assert capsys.readouterr().out.strip() == "BANNER"


def test_load_settings_wrapper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    expected = _settings(tmp_path)
    captured: dict = {}

    def _fake_from_env(*, env_file, require_api_credentials):  # noqa: ANN001
        captured["env_file"] = env_file
        captured["require_api_credentials"] = require_api_credentials
        return expected

    monkeypatch.setattr("suunto_export_activity.cli.Settings.from_env", _fake_from_env)
    result = _load_settings(Path("x.env"), require_api_credentials=False)
    assert result is expected
    assert captured["env_file"] == Path("x.env")
    assert captured["require_api_credentials"] is False


def test_workout_metadata_mapping() -> None:
    workout = {
        "id": "i1",
        "comment": "nice",
        "gear": "shoes",
        "sport": "run",
        "subSport": "trail",
    }
    metadata = _workout_metadata(workout)
    assert metadata["id"] == "i1"
    assert metadata["workoutId"] == "i1"
    assert metadata["notes"] == "nice"
    assert metadata["equipment"] == "shoes"
    assert metadata["sub_sport"] == "trail"


def test_resolve_encrypt_choice() -> None:
    settings = SimpleNamespace(default_encrypt_export=True)
    assert _resolve_encrypt_choice(argparse.Namespace(encrypt_output=None), settings) is True
    assert _resolve_encrypt_choice(argparse.Namespace(encrypt_output=False), settings) is False


def test_resolve_consent_auto_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUUNTO_AUTO_CONSENT", "true")
    assert _resolve_consent_auto_yes(argparse.Namespace(yes=False)) is True
    assert _resolve_consent_auto_yes(argparse.Namespace(yes=True)) is True


def test_require_consent_if_needed_forwards_parameters(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        "suunto_export_activity.cli.require_explicit_consent",
        lambda **kwargs: calls.append(kwargs),
    )
    settings = SimpleNamespace(require_consent=True)
    _require_consent_if_needed(settings, argparse.Namespace(yes=True), "export")
    assert calls == [{"enabled": True, "auto_yes": True, "action_label": "export"}]


def test_persist_fallback_workout_json(tmp_path: Path) -> None:
    destination = tmp_path / "raw" / "w1" / "w1_workout.json"
    output = _persist_fallback_workout_json({"id": "w1"}, destination)
    assert output == destination
    assert destination.exists()


def test_cmd_auth_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)

    class _OAuth:
        def __init__(self, _settings) -> None:  # noqa: ANN001
            pass

        def build_authorize_url(self, state: str = "x") -> str:
            return f"https://example.com/auth?state={state}"

    monkeypatch.setattr("suunto_export_activity.cli.OAuthClient", _OAuth)

    rc = cmd_auth_url(argparse.Namespace(env_file=None, state="abc"))
    assert rc == 0
    assert "state=abc" in capsys.readouterr().out


@pytest.mark.parametrize("mode", ["memory", "file"])
def test_cmd_exchange_code(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys, mode: str) -> None:
    settings = _settings(tmp_path, token_storage_mode=mode)
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)

    class _OAuth:
        def __init__(self, _settings) -> None:  # noqa: ANN001
            pass

        def exchange_code_for_token(self, code: str):  # noqa: ANN001
            return SimpleNamespace(expires_at=123456)

    monkeypatch.setattr("suunto_export_activity.cli.OAuthClient", _OAuth)

    rc = cmd_exchange_code(argparse.Namespace(env_file=None, code="CODE"))
    output = capsys.readouterr().out

    assert rc == 0
    assert "expires_at=123456" in output
    if mode == "file":
        assert "Token saved" in output
    else:
        assert "in-memory" in output


def test_cmd_export_success_with_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path, max_hr=190)
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)
    monkeypatch.setattr("suunto_export_activity.cli._require_consent_if_needed", lambda *a, **k: None)

    oauth_instance = SimpleNamespace(exchanged=None)

    class _OAuth:
        def __init__(self, _settings) -> None:  # noqa: ANN001
            pass

        def exchange_code_for_token(self, code: str) -> None:
            oauth_instance.exchanged = code

    class _Api:
        def __init__(self, _settings, _oauth) -> None:  # noqa: ANN001
            pass

        def list_workouts(self, **kwargs):  # noqa: ANN001
            return [{"id": "w1", "sport": "run"}, {"id": "w2", "sport": "trail"}]

        def download_workout_resources(self, workout: dict, raw_dir: Path) -> list[Path]:
            if workout["id"] == "w1":
                file_path = raw_dir / "w1" / "resource.fit"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_bytes(b"x")
                return [file_path]
            raise ApiError("download failed")

    captured: dict = {}

    def _fake_parse_many(files, **kwargs):  # noqa: ANN001
        captured["files"] = files
        captured["metadata_by_stem"] = kwargs["metadata_by_stem"]
        return [ActivityRecord(activity_id="a1")], ["warn-1"]

    monkeypatch.setattr("suunto_export_activity.cli.OAuthClient", _OAuth)
    monkeypatch.setattr("suunto_export_activity.cli.SuuntoApiClient", _Api)
    monkeypatch.setattr("suunto_export_activity.cli.parse_many_files", _fake_parse_many)
    monkeypatch.setattr(
        "suunto_export_activity.cli.export_activities",
        lambda output_dir, activities, **kwargs: (
            output_dir / "activities.json",
            output_dir / "activities.csv",
        ),
    )

    args = argparse.Namespace(
        env_file=None,
        auth_code="AUTH",
        output_dir=str(tmp_path / "out"),
        start_date=None,
        end_date=None,
        page_size=50,
        max_items=None,
        encrypt_output=None,
        passphrase=None,
    )
    rc = cmd_export(args)
    output = capsys.readouterr().out

    assert rc == 0
    assert oauth_instance.exchanged == "AUTH"
    assert len(captured["files"]) == 2
    assert "resource" in captured["metadata_by_stem"]
    assert "w2_workout" in captured["metadata_by_stem"]
    assert "Activities parsed: 1" in output
    assert "Parsing warnings: 1" in output


def test_cmd_export_missing_passphrase_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path, default_encrypt_export=True, export_passphrase=None)
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)
    monkeypatch.setattr("suunto_export_activity.cli._require_consent_if_needed", lambda *a, **k: None)
    monkeypatch.setattr("suunto_export_activity.cli.OAuthClient", lambda s: SimpleNamespace())
    monkeypatch.setattr(
        "suunto_export_activity.cli.SuuntoApiClient",
        lambda s, o: SimpleNamespace(
            list_workouts=lambda **k: [],
            download_workout_resources=lambda workout, raw_dir: [],
        ),
    )

    args = argparse.Namespace(
        env_file=None,
        auth_code=None,
        output_dir=str(tmp_path / "out"),
        start_date=None,
        end_date=None,
        page_size=10,
        max_items=None,
        encrypt_output=None,
        passphrase=None,
    )

    with pytest.raises(ConfigError):
        cmd_export(args)


def test_cmd_export_prints_encryption_notice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path, default_encrypt_export=True, export_passphrase="secret")
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)
    monkeypatch.setattr("suunto_export_activity.cli._require_consent_if_needed", lambda *a, **k: None)
    monkeypatch.setattr("suunto_export_activity.cli.OAuthClient", lambda s: SimpleNamespace())
    monkeypatch.setattr(
        "suunto_export_activity.cli.SuuntoApiClient",
        lambda s, o: SimpleNamespace(
            list_workouts=lambda **k: [],
            download_workout_resources=lambda workout, raw_dir: [],
        ),
    )
    monkeypatch.setattr("suunto_export_activity.cli.export_activities", lambda *a, **k: (Path("a"), Path("b")))

    args = argparse.Namespace(
        env_file=None,
        auth_code=None,
        output_dir=str(tmp_path / "out"),
        start_date=None,
        end_date=None,
        page_size=10,
        max_items=None,
        encrypt_output=None,
        passphrase=None,
    )
    rc = cmd_export(args)
    assert rc == 0
    assert "Output files encrypted." in capsys.readouterr().out


def test_cmd_parse_local_no_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)
    monkeypatch.setattr("suunto_export_activity.cli._require_consent_if_needed", lambda *a, **k: None)
    monkeypatch.setattr("suunto_export_activity.cli.discover_activity_files", lambda path: [])

    args = argparse.Namespace(env_file=None, input=str(tmp_path), output_dir=str(tmp_path / "out"), encrypt_output=None, passphrase=None)
    rc = cmd_parse_local(args)
    assert rc == 1
    assert "No .fit or .json files found" in capsys.readouterr().out


def test_cmd_parse_local_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path, max_hr=180)
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)
    monkeypatch.setattr("suunto_export_activity.cli._require_consent_if_needed", lambda *a, **k: None)

    sample_file = tmp_path / "activity.json"
    sample_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("suunto_export_activity.cli.discover_activity_files", lambda path: [sample_file])
    monkeypatch.setattr(
        "suunto_export_activity.cli.parse_many_files",
        lambda files, **kwargs: ([ActivityRecord(activity_id="a1")], ["warn"]),
    )
    monkeypatch.setattr(
        "suunto_export_activity.cli.export_activities",
        lambda output_dir, activities, **kwargs: (
            output_dir / "activities.json",
            output_dir / "activities.csv",
        ),
    )

    args = argparse.Namespace(
        env_file=None,
        input=str(tmp_path),
        output_dir=str(tmp_path / "out"),
        encrypt_output=True,
        passphrase="secret",
    )
    rc = cmd_parse_local(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Files scanned: 1" in out
    assert "Output files encrypted." in out


def test_cmd_parse_local_missing_passphrase_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path, default_encrypt_export=True, export_passphrase=None)
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)
    monkeypatch.setattr("suunto_export_activity.cli._require_consent_if_needed", lambda *a, **k: None)
    monkeypatch.setattr("suunto_export_activity.cli.discover_activity_files", lambda path: [tmp_path / "a.fit"])
    monkeypatch.setattr("suunto_export_activity.cli.parse_many_files", lambda files, **kwargs: ([], []))

    args = argparse.Namespace(
        env_file=None,
        input=str(tmp_path),
        output_dir=str(tmp_path / "out"),
        encrypt_output=None,
        passphrase=None,
    )
    with pytest.raises(ConfigError):
        cmd_parse_local(args)


def test_cmd_delete_data_with_token_cleanup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path, token_storage_mode="file")
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)
    monkeypatch.setattr("suunto_export_activity.cli._require_consent_if_needed", lambda *a, **k: None)
    monkeypatch.setattr("suunto_export_activity.cli.delete_exported_data", lambda output_dir: True)

    cleared = {"count": 0}

    class _Store:
        def __init__(self, path: Path, mode: str) -> None:  # noqa: ARG002
            pass

        def clear(self) -> None:
            cleared["count"] += 1

    monkeypatch.setattr("suunto_export_activity.cli.TokenStore", _Store)

    args = argparse.Namespace(env_file=None, output_dir=str(tmp_path / "out"), include_tokens=True, yes=True)
    rc = cmd_delete_data(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert cleared["count"] == 1
    assert "Token cache cleared." in out


def test_cmd_delete_data_when_nothing_to_delete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: settings)
    monkeypatch.setattr("suunto_export_activity.cli._require_consent_if_needed", lambda *a, **k: None)
    monkeypatch.setattr("suunto_export_activity.cli.delete_exported_data", lambda output_dir: False)

    args = argparse.Namespace(env_file=None, output_dir=str(tmp_path / "out"), include_tokens=False, yes=True)
    rc = cmd_delete_data(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert "No exported data directory found" in out


def test_build_parser_uses_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUUNTO_OUTPUT_DIR", "/tmp/out")
    monkeypatch.setenv("SUUNTO_EXPORT_START_DATE", "2026-01-01")
    monkeypatch.setenv("SUUNTO_EXPORT_END_DATE", "2026-12-31")
    monkeypatch.setenv("SUUNTO_LOCAL_INPUT", "/tmp/in")

    parser = build_parser()
    export_args = parser.parse_args(["export"])
    parse_local_args = parser.parse_args(["parse-local"])

    assert export_args.output_dir == "/tmp/out"
    assert export_args.start_date == "2026-01-01"
    assert export_args.end_date == "2026-12-31"
    assert parse_local_args.input == "/tmp/in"


def test_main_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("suunto_export_activity.cli._bootstrap_language_and_env", lambda argv: None)

    class _Parser:
        def parse_args(self, argv):  # noqa: ANN001
            return argparse.Namespace(
                lang=None,
                verbose=False,
                env_file=None,
                func=lambda args: 0,
            )

    monkeypatch.setattr("suunto_export_activity.cli.build_parser", lambda: _Parser())
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: _settings(tmp_path))
    monkeypatch.setattr("suunto_export_activity.cli._configure_logging", lambda *a, **k: None)
    monkeypatch.setattr("suunto_export_activity.cli._show_banner", lambda: None)

    assert main([]) == 0


def test_main_handles_domain_exception(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("suunto_export_activity.cli._bootstrap_language_and_env", lambda argv: None)

    def _boom(_args):  # noqa: ANN001
        raise ConfigError("bad config")

    class _Parser:
        def parse_args(self, argv):  # noqa: ANN001
            return argparse.Namespace(lang=None, verbose=False, env_file=None, func=_boom)

    monkeypatch.setattr("suunto_export_activity.cli.build_parser", lambda: _Parser())
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: _settings(tmp_path))
    monkeypatch.setattr("suunto_export_activity.cli._configure_logging", lambda *a, **k: None)
    monkeypatch.setattr("suunto_export_activity.cli._show_banner", lambda: None)

    assert main([]) == 1


def test_main_handles_unexpected_exception(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("suunto_export_activity.cli._bootstrap_language_and_env", lambda argv: None)

    def _boom(_args):  # noqa: ANN001
        raise RuntimeError("boom")

    class _Parser:
        def parse_args(self, argv):  # noqa: ANN001
            return argparse.Namespace(lang=None, verbose=False, env_file=None, func=_boom)

    monkeypatch.setattr("suunto_export_activity.cli.build_parser", lambda: _Parser())
    monkeypatch.setattr("suunto_export_activity.cli._load_settings", lambda *a, **k: _settings(tmp_path))
    monkeypatch.setattr("suunto_export_activity.cli._configure_logging", lambda *a, **k: None)
    monkeypatch.setattr("suunto_export_activity.cli._show_banner", lambda: None)

    assert main([]) == 1


@pytest.mark.filterwarnings(
    "ignore:'suunto_export_activity.cli' found in sys.modules.*:RuntimeWarning"
)
def test_cli_module_main_guard_executes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    monkeypatch.setattr(
        "sys.argv",
        [
            "suunto-export",
            "--lang",
            "en",
            "parse-local",
            "--yes",
            "--input",
            str(input_dir),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        runpy.run_module("suunto_export_activity.cli", run_name="__main__")
    assert exc.value.code == 1
