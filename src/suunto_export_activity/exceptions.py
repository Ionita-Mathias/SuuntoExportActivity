"""Custom exceptions for the Suunto export utility."""


class SuuntoExportError(Exception):
    """Base class for project errors."""


class ConfigError(SuuntoExportError):
    """Raised when configuration is missing or invalid."""


class AuthError(SuuntoExportError):
    """Raised for OAuth authentication/authorization failures."""


class ApiError(SuuntoExportError):
    """Raised for API communication errors."""


class ParseError(SuuntoExportError):
    """Raised when activity parsing fails."""


class ConsentError(SuuntoExportError):
    """Raised when explicit user consent is missing."""


class SecurityError(SuuntoExportError):
    """Raised for encryption/decryption or sensitive-data handling issues."""
