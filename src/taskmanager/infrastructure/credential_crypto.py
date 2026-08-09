"""OS keyring machine key + Fernet encryption for source credentials."""

from __future__ import annotations

import base64
import logging
import secrets

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

KEYRING_SERVICE = "TaskManager"
KEYRING_USERNAME = "source-credentials-key"


class CredentialCryptoError(Exception):
    """Failed to encrypt/decrypt or access the machine key."""


def _get_keyring():
    try:
        import keyring
    except ImportError as exc:
        raise CredentialCryptoError(
            "Пакет keyring не установлен — нельзя хранить пароли модулей"
        ) from exc
    return keyring


def _ensure_machine_key() -> bytes:
    keyring = _get_keyring()
    try:
        stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except Exception as exc:
        raise CredentialCryptoError(
            f"Не удалось прочитать ключ из связки ключей ОС: {exc}"
        ) from exc
    if stored:
        try:
            return base64.urlsafe_b64decode(stored.encode("ascii"))
        except Exception as exc:
            raise CredentialCryptoError("Повреждённый ключ в связке ключей ОС") from exc
    raw = secrets.token_bytes(32)
    encoded = base64.urlsafe_b64encode(raw).decode("ascii")
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, encoded)
    except Exception as exc:
        raise CredentialCryptoError(
            f"Не удалось сохранить ключ в связку ключей ОС: {exc}"
        ) from exc
    return raw


def _fernet() -> Fernet:
    raw = _ensure_machine_key()
    # Fernet key must be url-safe base64-encoded 32 bytes
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def decrypt_secret(ciphertext: str) -> str:
    try:
        raw = _fernet().decrypt(ciphertext.encode("ascii"))
    except InvalidToken as exc:
        raise CredentialCryptoError(
            "Не удалось расшифровать пароль модуля (другая машина или сброшен ключ?)"
        ) from exc
    except Exception as exc:
        raise CredentialCryptoError(f"Ошибка расшифровки пароля: {exc}") from exc
    return raw.decode("utf-8")
