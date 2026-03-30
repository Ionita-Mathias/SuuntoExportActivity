from __future__ import annotations

import base64
import sys
import types
from pathlib import Path

import pytest

from suunto_export_activity.exceptions import SecurityError
from suunto_export_activity.security import _derive_key, encrypt_file


def _install_fake_cryptography(monkeypatch: pytest.MonkeyPatch) -> None:
    cryptography_module = types.ModuleType("cryptography")

    hazmat_module = types.ModuleType("cryptography.hazmat")
    primitives_module = types.ModuleType("cryptography.hazmat.primitives")
    hashes_module = types.ModuleType("cryptography.hazmat.primitives.hashes")
    kdf_module = types.ModuleType("cryptography.hazmat.primitives.kdf")
    pbkdf2_module = types.ModuleType("cryptography.hazmat.primitives.kdf.pbkdf2")
    fernet_module = types.ModuleType("cryptography.fernet")

    class SHA256:  # noqa: D401
        pass

    class PBKDF2HMAC:
        def __init__(self, **kwargs):  # noqa: ANN003, D401
            self.length = kwargs["length"]

        def derive(self, value: bytes) -> bytes:
            return (value + b"x" * self.length)[: self.length]

    class Fernet:
        def __init__(self, key: bytes) -> None:
            self.key = key

        def encrypt(self, plaintext: bytes) -> bytes:
            return b"enc:" + plaintext

    hashes_module.SHA256 = SHA256
    pbkdf2_module.PBKDF2HMAC = PBKDF2HMAC
    fernet_module.Fernet = Fernet

    monkeypatch.setitem(sys.modules, "cryptography", cryptography_module)
    monkeypatch.setitem(sys.modules, "cryptography.hazmat", hazmat_module)
    monkeypatch.setitem(sys.modules, "cryptography.hazmat.primitives", primitives_module)
    monkeypatch.setitem(sys.modules, "cryptography.hazmat.primitives.hashes", hashes_module)
    monkeypatch.setitem(sys.modules, "cryptography.hazmat.primitives.kdf", kdf_module)
    monkeypatch.setitem(sys.modules, "cryptography.hazmat.primitives.kdf.pbkdf2", pbkdf2_module)
    monkeypatch.setitem(sys.modules, "cryptography.fernet", fernet_module)


def test_derive_key_requires_non_empty_passphrase(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_cryptography(monkeypatch)
    with pytest.raises(SecurityError):
        _derive_key("", b"0123456789abcdef")


def test_derive_key_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_cryptography(monkeypatch)
    key = _derive_key("secret", b"0123456789abcdef")
    assert key == base64.urlsafe_b64encode((b"secret" + b"x" * 32)[:32])


def test_encrypt_file_success_and_delete_plaintext(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_cryptography(monkeypatch)
    monkeypatch.setattr("suunto_export_activity.security.os.urandom", lambda n: b"0" * n)

    file_path = tmp_path / "activity.json"
    file_path.write_text("payload", encoding="utf-8")

    encrypted = encrypt_file(file_path, "passphrase", delete_plaintext=True)
    raw = encrypted.read_bytes()

    assert encrypted.name.endswith(".enc")
    assert raw.startswith(b"SENC1" + b"0" * 16 + b"enc:")
    assert not file_path.exists()


def test_encrypt_file_can_keep_plaintext(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _install_fake_cryptography(monkeypatch)
    monkeypatch.setattr("suunto_export_activity.security.os.urandom", lambda n: b"1" * n)

    file_path = tmp_path / "activity.csv"
    file_path.write_text("csv", encoding="utf-8")

    encrypted = encrypt_file(file_path, "passphrase", delete_plaintext=False)
    assert encrypted.exists()
    assert file_path.exists()
