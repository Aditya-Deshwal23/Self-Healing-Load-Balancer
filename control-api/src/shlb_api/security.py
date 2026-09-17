from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from shlb_api.settings import get_settings


@lru_cache
def password_hasher() -> PasswordHasher:
    return PasswordHasher(time_cost=3, memory_cost=65_536, parallelism=2, hash_len=32, salt_len=16)


def hash_password(password: str) -> str:
    return password_hasher().hash(password)


@lru_cache
def dummy_password_hash() -> str:
    """One process-local Argon2 hash used to equalize unknown-account verification."""
    return hash_password("not-a-valid-user-password")


def verify_password(password_hash: str, candidate: str) -> tuple[bool, bool]:
    try:
        valid = password_hasher().verify(password_hash, candidate)
    except (VerifyMismatchError, InvalidHashError):
        return False, False
    return bool(valid), password_hasher().check_needs_rehash(password_hash)


def encrypt_field(value: str) -> bytes:
    nonce = os.urandom(12)
    ciphertext = AESGCM(get_settings().field_encryption_key).encrypt(
        nonce,
        value.encode("utf-8"),
        b"shlb-backend-address-v1",
    )
    return nonce + ciphertext


def decrypt_field(value: bytes) -> str:
    if len(value) < 29:
        raise ValueError("encrypted field is malformed")
    plaintext = AESGCM(get_settings().field_encryption_key).decrypt(
        value[:12],
        value[12:],
        b"shlb-backend-address-v1",
    )
    return plaintext.decode("utf-8")


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def session_key(session_id: str) -> str:
    return f"sess:{session_id}"


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def constant_time_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def encode_session(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def decode_session(value: str) -> dict[str, Any]:
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("session payload is not an object")
    return payload


def unix_time() -> int:
    return int(datetime.now(UTC).timestamp())

