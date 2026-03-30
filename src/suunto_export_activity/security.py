"""Optional encryption for exported files."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from .exceptions import SecurityError
from .i18n import t

_MAGIC = b"SENC1"


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    except ImportError as exc:  # pragma: no cover - runtime dependency path
        raise SecurityError(t("security.crypto_missing")) from exc

    if not passphrase:
        raise SecurityError(t("security.passphrase_empty"))

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def encrypt_file(path: Path, passphrase: str, *, delete_plaintext: bool = True) -> Path:
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:  # pragma: no cover - runtime dependency path
        raise SecurityError(t("security.crypto_missing")) from exc

    plaintext = path.read_bytes()
    salt = os.urandom(16)
    key = _derive_key(passphrase, salt)
    token = Fernet(key).encrypt(plaintext)

    encrypted_path = path.with_suffix(path.suffix + ".enc")
    encrypted_path.write_bytes(_MAGIC + salt + token)

    if delete_plaintext:
        path.unlink(missing_ok=True)

    return encrypted_path
