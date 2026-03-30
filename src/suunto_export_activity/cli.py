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
from .config import Settings
from .exceptions import ApiError, AuthError, ConfigError
from .exporter import export_activities
from .processor import discover_activity_files, parse_many_files
from .utils import ensure_directory

LOGGER = logging.getLogger("suunto_export")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


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
    print(f"Token saved to {settings.token_path}")
    print(f"expires_at={token.expires_at}")
    return 0


def _persist_fallback_workout_json(workout: dict[str, Any], destination: Path) -> Path:
    ensure_directory(destination.parent)
    destination.write_text(json.dumps(workout, indent=2, ensure_ascii=False), encoding="utf-8")
    return destination


def cmd_export(args: argparse.Namespace) -> int:
    settings = _load_settings(args.env_file)
    oauth = OAuthClient(settings)
    api = SuuntoApiClient(settings, oauth)

    output_dir = Path(args.output_dir).resolve()
    raw_dir = ensure_directory(output_dir / "raw")

    workouts = api.list_workouts(
        start_date=args.start_date,
        end_date=args.end_date,
        page_size=args.page_size,
        max_items=args.max_items,
    )
    LOGGER.info("Workouts fetched: %s", len(workouts))

    files_to_parse: list[Path] = []
    metadata_by_stem: dict[str, dict[str, Any]] = {}

    for workout in workouts:
        workout_meta = _workout_metadata(workout)
        workout_id = str(workout_meta.get("id") or "unknown")
        try:
            downloaded = api.download_workout_resources(workout, raw_dir)
        except ApiError as exc:
            LOGGER.warning("Failed to download resources for workout %s: %s", workout_id, exc)
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
        LOGGER.warning(message)

    json_path, csv_path = export_activities(output_dir, activities)
    print(f"Activities parsed: {len(activities)}")
    print(f"JSON exported: {json_path}")
    print(f"CSV exported: {csv_path}")
    if parse_errors:
        print(f"Parsing warnings: {len(parse_errors)} (see logs)")
    return 0


def cmd_parse_local(args: argparse.Namespace) -> int:
    settings = _load_settings(args.env_file, require_api_credentials=False)
    input_path = Path(args.input).resolve()
    output_dir = Path(args.output_dir).resolve()

    files = discover_activity_files(input_path)
    if not files:
        print(f"No .fit or .json files found in {input_path}")
        return 1

    activities, parse_errors = parse_many_files(files, max_hr=settings.max_hr)
    for message in parse_errors:
        LOGGER.warning(message)

    json_path, csv_path = export_activities(output_dir, activities)
    print(f"Files scanned: {len(files)}")
    print(f"Activities parsed: {len(activities)}")
    print(f"JSON exported: {json_path}")
    print(f"CSV exported: {csv_path}")
    if parse_errors:
        print(f"Parsing warnings: {len(parse_errors)} (see logs)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    default_output_dir = os.getenv("SUUNTO_OUTPUT_DIR", "./output")
    default_start_date = os.getenv("SUUNTO_EXPORT_START_DATE")
    default_end_date = os.getenv("SUUNTO_EXPORT_END_DATE")
    default_local_input = os.getenv("SUUNTO_LOCAL_INPUT")

    parser = argparse.ArgumentParser(
        prog="suunto-export",
        description="Export and parse Suunto activities to JSON/CSV",
    )
    parser.add_argument("--env-file", type=Path, default=None, help="Path to .env file")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs")

    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_parser = subparsers.add_parser("auth-url", help="Generate OAuth authorization URL")
    auth_parser.add_argument("--state", default="suunto-export", help="OAuth state parameter")
    auth_parser.set_defaults(func=cmd_auth_url)

    exchange_parser = subparsers.add_parser("exchange-code", help="Exchange OAuth code for token")
    exchange_parser.add_argument("--code", required=True, help="Authorization code from callback")
    exchange_parser.set_defaults(func=cmd_exchange_code)

    export_parser = subparsers.add_parser("export", help="Fetch workouts via API and export parsed data")
    export_parser.add_argument(
        "--output-dir",
        default=default_output_dir,
        help="Output directory (or env SUUNTO_OUTPUT_DIR)",
    )
    export_parser.add_argument(
        "--start-date",
        default=default_start_date,
        help="Filter start date YYYY-MM-DD (or env SUUNTO_EXPORT_START_DATE)",
    )
    export_parser.add_argument(
        "--end-date",
        default=default_end_date,
        help="Filter end date YYYY-MM-DD (or env SUUNTO_EXPORT_END_DATE)",
    )
    export_parser.add_argument("--page-size", type=int, default=50, help="API page size")
    export_parser.add_argument("--max-items", type=int, default=None, help="Stop after N workouts")
    export_parser.set_defaults(func=cmd_export)

    parse_local = subparsers.add_parser("parse-local", help="Parse local .fit/.json files only")
    parse_local.add_argument(
        "--input",
        default=default_local_input,
        required=default_local_input is None,
        help="Input file/directory (or env SUUNTO_LOCAL_INPUT)",
    )
    parse_local.add_argument(
        "--output-dir",
        default=default_output_dir,
        help="Output directory (or env SUUNTO_OUTPUT_DIR)",
    )
    parse_local.set_defaults(func=cmd_parse_local)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    try:
        return args.func(args)
    except (ConfigError, AuthError, ApiError) as exc:
        LOGGER.error("%s", exc)
        return 1
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
