"""Command line interface for Suunto export utility."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

from .api import SuuntoApiClient
from .auth import OAuthClient
from .cleanup import delete_exported_data
from .compliance import get_compatibility_banner, normalize_bool, require_explicit_consent
from .config import Settings
from .exceptions import ApiError, AuthError, ConfigError, ConsentError, SecurityError
from .exporter import export_activities
from .i18n import set_language, t
from .processor import discover_activity_files, parse_many_files
from .token_store import TokenStore
from .utils import ensure_directory, load_env_file

LOGGER = logging.getLogger("suunto_export")


def _bootstrap_language_and_env(argv: list[str] | None) -> None:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument("--env-file", type=Path, default=None)
    bootstrap.add_argument("--lang", choices=("fr", "en"), default=None)
    known_args, _ = bootstrap.parse_known_args(argv or [])

    load_env_file(known_args.env_file if known_args.env_file else Path(".env"))
    set_language(known_args.lang)


def _configure_logging(verbose: bool, log_file: Path | None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file is not None:
        ensure_directory(log_file.resolve().parent)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", handlers=handlers)


def _show_banner() -> None:
    print(get_compatibility_banner())


def _workout_metadata(workout: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": workout.get("id") or workout.get("workoutId"),
        "workoutId": workout.get("workoutId") or workout.get("id"),
        "notes": workout.get("notes") or workout.get("comment"),
        "equipment": workout.get("equipment") or workout.get("gear"),
        "sport": workout.get("sport"),
        "sub_sport": workout.get("subSport") or workout.get("sub_sport"),
    }


def _load_settings(env_file: Path | None, *, require_api_credentials: bool = True) -> Settings:
    return Settings.from_env(
        env_file=env_file,
        require_api_credentials=require_api_credentials,
    )


def _resolve_encrypt_choice(args: argparse.Namespace, settings: Settings) -> bool:
    if args.encrypt_output is None:
        return settings.default_encrypt_export
    return bool(args.encrypt_output)


def _resolve_consent_auto_yes(args: argparse.Namespace) -> bool:
    env_auto = normalize_bool(os.getenv("SUUNTO_AUTO_CONSENT"), False)
    return bool(getattr(args, "yes", False) or env_auto)


def _require_consent_if_needed(settings: Settings, args: argparse.Namespace, action_label: str) -> None:
    require_explicit_consent(
        enabled=settings.require_consent,
        auto_yes=_resolve_consent_auto_yes(args),
        action_label=action_label,
    )


def _persist_fallback_workout_json(workout: dict[str, Any], destination: Path) -> Path:
    ensure_directory(destination.parent)
    destination.write_text(json.dumps(workout, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination


def cmd_auth_url(args: argparse.Namespace) -> int:
    settings = _load_settings(args.env_file)
    oauth = OAuthClient(settings)
    url = oauth.build_authorize_url(state=args.state)
    print(url)
    return 0


def cmd_exchange_code(args: argparse.Namespace) -> int:
    settings = _load_settings(args.env_file)
    oauth = OAuthClient(settings)
    token = oauth.exchange_code_for_token(args.code)

    if settings.token_storage_mode == "file":
        print(t("cli.token_saved", path=settings.token_path))
    else:
        print(t("cli.token_memory_only"))
        print(t("cli.token_tip"))

    print(t("cli.token_expires_at", expires_at=token.expires_at))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    settings = _load_settings(args.env_file)
    _require_consent_if_needed(settings, args, action_label="export")

    oauth = OAuthClient(settings)
    if args.auth_code:
        oauth.exchange_code_for_token(args.auth_code)

    api = SuuntoApiClient(settings, oauth)

    output_dir = Path(args.output_dir).resolve()
    raw_dir = ensure_directory(output_dir / "raw")

    workouts = api.list_workouts(
        start_date=args.start_date,
        end_date=args.end_date,
        page_size=args.page_size,
        max_items=args.max_items,
    )
    LOGGER.info("%s", t("cli.workouts_fetched", count=len(workouts)))

    files_to_parse: list[Path] = []
    metadata_by_stem: dict[str, dict[str, Any]] = {}

    for workout in workouts:
        workout_meta = _workout_metadata(workout)
        workout_id = str(workout_meta.get("id") or "unknown")
        try:
            downloaded = api.download_workout_resources(workout, raw_dir)
        except ApiError as exc:
            LOGGER.warning(
                "%s",
                t("cli.download_failed", workout_id=workout_id, error=exc),
            )
            downloaded = []

        if not downloaded:
            fallback_file = raw_dir / workout_id / f"{workout_id}_workout.json"
            downloaded = [_persist_fallback_workout_json(workout, fallback_file)]

        for file_path in downloaded:
            files_to_parse.append(file_path)
            metadata_by_stem[file_path.stem] = workout_meta

    activities, parse_errors = parse_many_files(
        files_to_parse,
        max_hr=settings.max_hr,
        metadata_by_stem=metadata_by_stem,
    )

    for message in parse_errors:
        LOGGER.warning("%s", message)

    encrypt_output = _resolve_encrypt_choice(args, settings)
    passphrase = args.passphrase or settings.export_passphrase
    if encrypt_output and not passphrase:
        raise ConfigError(t("cli.encryption_missing_passphrase"))

    json_path, csv_path = export_activities(
        output_dir,
        activities,
        encrypt=encrypt_output,
        passphrase=passphrase,
    )

    print(t("cli.activities_parsed", count=len(activities)))
    print(t("cli.json_exported", path=json_path))
    print(t("cli.csv_exported", path=csv_path))
    if encrypt_output:
        print(t("cli.output_encrypted"))
    if parse_errors:
        print(t("cli.parsing_warnings", count=len(parse_errors)))
    return 0


def cmd_parse_local(args: argparse.Namespace) -> int:
    settings = _load_settings(args.env_file, require_api_credentials=False)
    _require_consent_if_needed(settings, args, action_label="parse-local")

    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()

    files = discover_activity_files(input_path)
    if not files:
        print(t("cli.no_files_found", path=input_path))
        return 1

    activities, parse_errors = parse_many_files(files, max_hr=settings.max_hr)
    for message in parse_errors:
        LOGGER.warning("%s", message)

    encrypt_output = _resolve_encrypt_choice(args, settings)
    passphrase = args.passphrase or settings.export_passphrase
    if encrypt_output and not passphrase:
        raise ConfigError(t("cli.encryption_missing_passphrase"))

    json_path, csv_path = export_activities(
        output_dir,
        activities,
        encrypt=encrypt_output,
        passphrase=passphrase,
    )
    print(t("cli.files_scanned", count=len(files)))
    print(t("cli.activities_parsed", count=len(activities)))
    print(t("cli.json_exported", path=json_path))
    print(t("cli.csv_exported", path=csv_path))
    if encrypt_output:
        print(t("cli.output_encrypted"))
    if parse_errors:
        print(t("cli.parsing_warnings", count=len(parse_errors)))
    return 0


def cmd_delete_data(args: argparse.Namespace) -> int:
    settings = _load_settings(args.env_file, require_api_credentials=False)
    _require_consent_if_needed(settings, args, action_label="delete-data")

    output_dir = Path(args.output_dir).resolve()
    deleted = delete_exported_data(output_dir)

    if deleted:
        print(t("cli.deleted_output", path=output_dir))
    else:
        print(t("cli.no_output", path=output_dir))

    if args.include_tokens:
        store = TokenStore(settings.token_path, mode=settings.token_storage_mode)
        store.clear()
        print(t("cli.token_cache_cleared"))

    return 0


def build_parser() -> argparse.ArgumentParser:
    default_output_dir = os.getenv("SUUNTO_OUTPUT_DIR", "./output")
    default_start_date = os.getenv("SUUNTO_EXPORT_START_DATE")
    default_end_date = os.getenv("SUUNTO_EXPORT_END_DATE")
    default_local_input = os.getenv("SUUNTO_LOCAL_INPUT")

    parser = argparse.ArgumentParser(
        prog="suunto-export",
        description=t("cli.description"),
    )
    parser.add_argument("--env-file", type=Path, default=None, help=t("cli.arg_env_file"))
    parser.add_argument("--verbose", action="store_true", help=t("cli.arg_verbose"))
    parser.add_argument("--lang", choices=("fr", "en"), default=None, help=t("cli.arg_lang"))

    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_parser = subparsers.add_parser("auth-url", help=t("cli.cmd_auth_url"))
    auth_parser.add_argument("--state", default="suunto-export", help=t("cli.arg_state"))
    auth_parser.set_defaults(func=cmd_auth_url)

    exchange_parser = subparsers.add_parser("exchange-code", help=t("cli.cmd_exchange_code"))
    exchange_parser.add_argument("--code", required=True, help=t("cli.arg_code"))
    exchange_parser.set_defaults(func=cmd_exchange_code)

    export_parser = subparsers.add_parser("export", help=t("cli.cmd_export"))
    export_parser.add_argument("--output-dir", default=default_output_dir, help=t("cli.arg_output_dir"))
    export_parser.add_argument("--start-date", default=default_start_date, help=t("cli.arg_start_date"))
    export_parser.add_argument("--end-date", default=default_end_date, help=t("cli.arg_end_date"))
    export_parser.add_argument("--page-size", type=int, default=50, help=t("cli.arg_page_size"))
    export_parser.add_argument("--max-items", type=int, default=None, help=t("cli.arg_max_items"))
    export_parser.add_argument("--auth-code", default=None, help=t("cli.arg_auth_code"))
    export_parser.add_argument("--yes", action="store_true", help=t("cli.arg_yes"))
    export_parser.set_defaults(encrypt_output=None)
    export_parser.add_argument(
        "--encrypt-output",
        dest="encrypt_output",
        action="store_true",
        help=t("cli.arg_encrypt_output"),
    )
    export_parser.add_argument(
        "--no-encrypt-output",
        dest="encrypt_output",
        action="store_false",
        help=t("cli.arg_no_encrypt_output"),
    )
    export_parser.add_argument("--passphrase", default=None, help=t("cli.arg_passphrase"))
    export_parser.set_defaults(func=cmd_export)

    parse_local = subparsers.add_parser("parse-local", help=t("cli.cmd_parse_local"))
    parse_local.add_argument(
        "--input",
        default=default_local_input,
        required=default_local_input is None,
        help=t("cli.arg_input"),
    )
    parse_local.add_argument("--output-dir", default=default_output_dir, help=t("cli.arg_output_dir"))
    parse_local.add_argument("--yes", action="store_true", help=t("cli.arg_yes"))
    parse_local.set_defaults(encrypt_output=None)
    parse_local.add_argument(
        "--encrypt-output",
        dest="encrypt_output",
        action="store_true",
        help=t("cli.arg_encrypt_output"),
    )
    parse_local.add_argument(
        "--no-encrypt-output",
        dest="encrypt_output",
        action="store_false",
        help=t("cli.arg_no_encrypt_output"),
    )
    parse_local.add_argument("--passphrase", default=None, help=t("cli.arg_passphrase"))
    parse_local.set_defaults(func=cmd_parse_local)

    delete_parser = subparsers.add_parser("delete-data", help=t("cli.cmd_delete_data"))
    delete_parser.add_argument("--output-dir", default=default_output_dir, help=t("cli.arg_output_dir"))
    delete_parser.add_argument("--include-tokens", action="store_true", help=t("cli.arg_include_tokens"))
    delete_parser.add_argument("--yes", action="store_true", help=t("cli.arg_yes"))
    delete_parser.set_defaults(func=cmd_delete_data)

    return parser


def main(argv: list[str] | None = None) -> int:
    _bootstrap_language_and_env(argv)

    parser = build_parser()
    args = parser.parse_args(argv)

    set_language(args.lang)

    settings_for_logging = _load_settings(args.env_file, require_api_credentials=False)
    _configure_logging(args.verbose, settings_for_logging.log_file)
    _show_banner()

    try:
        return args.func(args)
    except (ConfigError, AuthError, ApiError, ConsentError, SecurityError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("%s", t("cli.unexpected_error", error=exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
