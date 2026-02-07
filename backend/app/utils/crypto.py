from __future__ import annotations

from typing import Optional

from cryptography.fernet import Fernet

from app.core.config import settings


def _get_fernet() -> Optional[Fernet]:
    key = settings.api_key_encryption_key
    if not key:
        return None
    return Fernet(key.encode("utf-8"))


def encrypt_value(value: str) -> str:
    fernet = _get_fernet()
    if not fernet:
        return value
    return fernet.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_value(value: str) -> str:
    fernet = _get_fernet()
    if not fernet:
        return value
    try:
        return fernet.decrypt(value.encode("utf-8")).decode("utf-8")
    except Exception:
        # Backward-compat: older rows may store plaintext when encryption was not enabled.
        return value
