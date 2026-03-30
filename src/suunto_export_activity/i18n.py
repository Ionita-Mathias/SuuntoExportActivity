"""Lightweight i18n support (French/English) for CLI and user-facing errors."""

from __future__ import annotations

import locale
import os
from typing import Any

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "banner.title": "SuuntoExportActivity",
        "banner.compatible": "Compatible with Suunto",
        "banner.usage": "Personal use only. Suunto Cloud API is provided as-is without warranty.",
        "consent.title": "Data processing consent required",
        "consent.body": "This tool exports and processes your personal Suunto activity data locally.",
        "consent.prompt": "Type {expected} to continue with '{action_label}': ",
        "consent.expected_token": "YES",
        "consent.cancelled": "Operation cancelled: explicit consent not granted.",
        "cli.description": "Export and parse Suunto activities to JSON/CSV",
        "cli.arg_env_file": "Path to .env file",
        "cli.arg_verbose": "Enable debug logs",
        "cli.arg_lang": "Language for CLI output (default: system language)",
        "cli.cmd_auth_url": "Generate OAuth authorization URL",
        "cli.arg_state": "OAuth state parameter",
        "cli.cmd_exchange_code": "Exchange OAuth code for token",
        "cli.arg_code": "Authorization code from callback",
        "cli.cmd_export": "Fetch workouts via API and export parsed data",
        "cli.arg_output_dir": "Output directory (or env SUUNTO_OUTPUT_DIR)",
        "cli.arg_start_date": "Filter start date YYYY-MM-DD (or env SUUNTO_EXPORT_START_DATE)",
        "cli.arg_end_date": "Filter end date YYYY-MM-DD (or env SUUNTO_EXPORT_END_DATE)",
        "cli.arg_page_size": "API page size",
        "cli.arg_max_items": "Stop after N workouts",
        "cli.arg_auth_code": "Optional OAuth authorization code to exchange before export",
        "cli.arg_yes": "Skip interactive consent prompt",
        "cli.arg_encrypt_output": "Encrypt exported JSON/CSV",
        "cli.arg_no_encrypt_output": "Disable output encryption",
        "cli.arg_passphrase": "Encryption passphrase (or env SUUNTO_EXPORT_PASSPHRASE)",
        "cli.cmd_parse_local": "Parse local .fit/.json files only",
        "cli.arg_input": "Input file/directory (or env SUUNTO_LOCAL_INPUT)",
        "cli.cmd_delete_data": "Delete exported local data (and optional token cache)",
        "cli.arg_include_tokens": "Also clear token cache according to token storage mode",
        "cli.token_saved": "Token saved to {path}",
        "cli.token_memory_only": "Token stored in-memory for this process only.",
        "cli.token_tip": "Tip: run export with --auth-code in the same command invocation.",
        "cli.token_expires_at": "expires_at={expires_at}",
        "cli.workouts_fetched": "Workouts fetched after owner filter: {count}",
        "cli.download_failed": "Failed to download resources for workout {workout_id}: {error}",
        "cli.encryption_missing_passphrase": "Encryption is enabled but no passphrase provided. Use --passphrase or set SUUNTO_EXPORT_PASSPHRASE.",
        "cli.activities_parsed": "Activities parsed: {count}",
        "cli.json_exported": "JSON exported: {path}",
        "cli.csv_exported": "CSV exported: {path}",
        "cli.output_encrypted": "Output files encrypted.",
        "cli.parsing_warnings": "Parsing warnings: {count} (see logs)",
        "cli.no_files_found": "No .fit or .json files found in {path}",
        "cli.files_scanned": "Files scanned: {count}",
        "cli.deleted_output": "Deleted exported data directory: {path}",
        "cli.no_output": "No exported data directory found at: {path}",
        "cli.token_cache_cleared": "Token cache cleared.",
        "cli.unexpected_error": "Unexpected error: {error}",
        "config.client_id_required": "SUUNTO_CLIENT_ID is required.",
        "config.client_secret_required": "SUUNTO_CLIENT_SECRET is required.",
        "config.subscription_key_required": "SUUNTO_SUBSCRIPTION_KEY is required.",
        "config.max_hr_integer": "SUUNTO_MAX_HR must be an integer.",
        "config.token_storage_invalid": "SUUNTO_TOKEN_STORAGE must be 'memory' or 'file'.",
        "config.rate_limit_integer": "SUUNTO_RATE_LIMIT_PER_MINUTE must be an integer.",
        "config.rate_limit_positive": "SUUNTO_RATE_LIMIT_PER_MINUTE must be > 0.",
        "auth.token_exchange_failed": "Token exchange failed ({status}): {details}",
        "auth.token_payload_missing_access": "Received token payload without access_token.",
        "auth.token_refresh_failed": "Token refresh failed ({status}): {details}",
        "auth.token_refresh_payload_missing_access": "Received refreshed payload without access_token.",
        "auth.no_token_found": "No token found. Run 'suunto-export auth-url' and then provide an auth code via 'exchange-code' or 'export --auth-code'.",
        "auth.expired_no_refresh": "Access token expired and no refresh_token is available. Re-authenticate.",
        "api.rate_limit_reached": "Suunto API rate limit reached for {url}. Configured client-side throttle: {rate}/minute.",
        "api.request_failed": "API request failed ({status}) for {url}: {details}",
        "security.crypto_missing": "Encryption requested but 'cryptography' is not installed. Install with: pip install 'suunto-export-activity[crypto]'",
        "security.passphrase_empty": "Encryption passphrase cannot be empty.",
    },
    "fr": {
        "banner.title": "SuuntoExportActivity",
        "banner.compatible": "Compatible avec Suunto",
        "banner.usage": "Usage personnel uniquement. L'API Suunto Cloud est fournie en l'etat, sans garantie.",
        "consent.title": "Consentement requis pour le traitement des donnees",
        "consent.body": "Cet outil exporte et traite localement vos donnees d'activite Suunto personnelles.",
        "consent.prompt": "Tapez {expected} pour continuer '{action_label}' : ",
        "consent.expected_token": "OUI",
        "consent.cancelled": "Operation annulee : consentement explicite non accorde.",
        "cli.description": "Exporter et parser les activites Suunto en JSON/CSV",
        "cli.arg_env_file": "Chemin vers le fichier .env",
        "cli.arg_verbose": "Activer les logs detailles",
        "cli.arg_lang": "Langue de la CLI (par defaut : langue systeme)",
        "cli.cmd_auth_url": "Generer l'URL d'autorisation OAuth",
        "cli.arg_state": "Parametre state OAuth",
        "cli.cmd_exchange_code": "Echanger le code OAuth contre un token",
        "cli.arg_code": "Code d'autorisation recu sur le callback",
        "cli.cmd_export": "Recuperer les workouts via l'API et exporter les donnees parsees",
        "cli.arg_output_dir": "Dossier de sortie (ou env SUUNTO_OUTPUT_DIR)",
        "cli.arg_start_date": "Date de debut YYYY-MM-DD (ou env SUUNTO_EXPORT_START_DATE)",
        "cli.arg_end_date": "Date de fin YYYY-MM-DD (ou env SUUNTO_EXPORT_END_DATE)",
        "cli.arg_page_size": "Taille de page API",
        "cli.arg_max_items": "Arreter apres N workouts",
        "cli.arg_auth_code": "Code OAuth optionnel a echanger avant export",
        "cli.arg_yes": "Ignorer la demande de consentement interactive",
        "cli.arg_encrypt_output": "Chiffrer les fichiers JSON/CSV exportes",
        "cli.arg_no_encrypt_output": "Desactiver le chiffrement de sortie",
        "cli.arg_passphrase": "Passphrase de chiffrement (ou env SUUNTO_EXPORT_PASSPHRASE)",
        "cli.cmd_parse_local": "Parser uniquement des fichiers .fit/.json locaux",
        "cli.arg_input": "Fichier/dossier d'entree (ou env SUUNTO_LOCAL_INPUT)",
        "cli.cmd_delete_data": "Supprimer les donnees exportees locales (et optionnellement le cache token)",
        "cli.arg_include_tokens": "Effacer aussi le cache token selon le mode de stockage",
        "cli.token_saved": "Token enregistre dans {path}",
        "cli.token_memory_only": "Token conserve en memoire uniquement pour ce processus.",
        "cli.token_tip": "Astuce : lancez export avec --auth-code dans la meme commande.",
        "cli.token_expires_at": "expires_at={expires_at}",
        "cli.workouts_fetched": "Workouts recuperes apres filtrage proprietaire : {count}",
        "cli.download_failed": "Echec du telechargement des ressources pour le workout {workout_id} : {error}",
        "cli.encryption_missing_passphrase": "Le chiffrement est active mais aucune passphrase n'est fournie. Utilisez --passphrase ou SUUNTO_EXPORT_PASSPHRASE.",
        "cli.activities_parsed": "Activites parsees : {count}",
        "cli.json_exported": "JSON exporte : {path}",
        "cli.csv_exported": "CSV exporte : {path}",
        "cli.output_encrypted": "Fichiers de sortie chiffres.",
        "cli.parsing_warnings": "Avertissements de parsing : {count} (voir logs)",
        "cli.no_files_found": "Aucun fichier .fit ou .json trouve dans {path}",
        "cli.files_scanned": "Fichiers analyses : {count}",
        "cli.deleted_output": "Dossier de donnees exportees supprime : {path}",
        "cli.no_output": "Aucun dossier de donnees exportees trouve a : {path}",
        "cli.token_cache_cleared": "Cache token efface.",
        "cli.unexpected_error": "Erreur inattendue : {error}",
        "config.client_id_required": "SUUNTO_CLIENT_ID est obligatoire.",
        "config.client_secret_required": "SUUNTO_CLIENT_SECRET est obligatoire.",
        "config.subscription_key_required": "SUUNTO_SUBSCRIPTION_KEY est obligatoire.",
        "config.max_hr_integer": "SUUNTO_MAX_HR doit etre un entier.",
        "config.token_storage_invalid": "SUUNTO_TOKEN_STORAGE doit valoir 'memory' ou 'file'.",
        "config.rate_limit_integer": "SUUNTO_RATE_LIMIT_PER_MINUTE doit etre un entier.",
        "config.rate_limit_positive": "SUUNTO_RATE_LIMIT_PER_MINUTE doit etre > 0.",
        "auth.token_exchange_failed": "Echec de l'echange du token ({status}) : {details}",
        "auth.token_payload_missing_access": "La reponse token ne contient pas access_token.",
        "auth.token_refresh_failed": "Echec du rafraichissement du token ({status}) : {details}",
        "auth.token_refresh_payload_missing_access": "La reponse de refresh ne contient pas access_token.",
        "auth.no_token_found": "Aucun token trouve. Lancez 'suunto-export auth-url' puis fournissez un code via 'exchange-code' ou 'export --auth-code'.",
        "auth.expired_no_refresh": "Le token d'acces est expire et aucun refresh_token n'est disponible. Re-authentifiez-vous.",
        "api.rate_limit_reached": "Limite de taux Suunto API atteinte pour {url}. Limitation client configuree : {rate}/minute.",
        "api.request_failed": "Requete API en echec ({status}) pour {url} : {details}",
        "security.crypto_missing": "Le chiffrement est demande mais 'cryptography' n'est pas installe. Installez avec : pip install 'suunto-export-activity[crypto]'",
        "security.passphrase_empty": "La passphrase de chiffrement ne peut pas etre vide.",
    },
}


def _normalize_language_code(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    if not lowered:
        return None

    for separator in (".", "@"):
        lowered = lowered.split(separator, 1)[0]
    for separator in ("-", "_"):
        lowered = lowered.split(separator, 1)[0]

    if lowered == "fr":
        return "fr"
    if lowered == "en":
        return "en"
    return None


def detect_system_language() -> str:
    for env_key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        normalized = _normalize_language_code(os.getenv(env_key))
        if normalized is not None:
            return "fr" if normalized == "fr" else "en"

    try:
        locale_value = locale.getlocale()[0]
    except Exception:  # noqa: BLE001
        locale_value = None

    normalized = _normalize_language_code(locale_value)
    if normalized is not None:
        return "fr" if normalized == "fr" else "en"

    return "en"


def resolve_language(preferred: str | None = None) -> str:
    normalized = _normalize_language_code(preferred)
    if normalized is not None:
        return normalized

    env_normalized = _normalize_language_code(os.getenv("SUUNTO_LANG"))
    if env_normalized is not None:
        return env_normalized

    return detect_system_language()


_CURRENT_LANGUAGE = resolve_language()


def set_language(preferred: str | None = None) -> str:
    global _CURRENT_LANGUAGE
    _CURRENT_LANGUAGE = resolve_language(preferred)
    return _CURRENT_LANGUAGE


def get_language() -> str:
    return _CURRENT_LANGUAGE


def t(key: str, **kwargs: Any) -> str:
    language_pack = _TRANSLATIONS.get(_CURRENT_LANGUAGE, _TRANSLATIONS["en"])
    template = language_pack.get(key) or _TRANSLATIONS["en"].get(key) or key
    try:
        return template.format(**kwargs)
    except Exception:  # noqa: BLE001
        return template
