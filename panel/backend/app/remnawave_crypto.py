import base64
import hashlib
import os

from cryptography.fernet import Fernet

_MIN_SECRET_LENGTH = 32


def _get_fernet() -> Fernet:
    secret = os.environ.get('REMNAWAVE_SECRET_KEY')
    if not secret or len(secret) < _MIN_SECRET_LENGTH:
        raise RuntimeError('REMNAWAVE_SECRET_KEY must be at least 32 characters')
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(value: str | None) -> str | None:
    if value is None:
        return None
    return _get_fernet().decrypt(value.encode()).decode()
