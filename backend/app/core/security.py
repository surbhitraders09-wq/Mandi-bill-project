"""
Security utilities for encrypting/decrypting sensitive credentials.
Uses Fernet symmetric encryption from the cryptography library.
"""

import base64
import hashlib

import bcrypt
from cryptography.fernet import Fernet

from app.config import settings


def _derive_fernet_key() -> bytes:
    raw = settings.ENCRYPTION_KEY.encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_derive_fernet_key())


def encrypt_value(value: str) -> str:
    encrypted_bytes = _fernet.encrypt(value.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_value(encrypted: str) -> str:
    decrypted_bytes = _fernet.decrypt(encrypted.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
