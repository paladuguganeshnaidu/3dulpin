"""Security helpers: PBKDF2 password hashing + JWT creation/verification.

PBKDF2 is used instead of bcrypt/argon2 to keep the demo dependency-free;
iteration count is deliberately high.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from typing import Any

import jwt

_ITERATIONS = 260_000


def hash_password(password: str, *, iterations: int = _ITERATIONS) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2$" + str(iterations) + "$" + _b64(salt) + "$" + _b64(digest)


def verify_password(password: str, stored: str) -> bool:
    try:
        _scheme, iters_s, salt_b64, digest_b64 = stored.split("$", 3)
        if _scheme != "pbkdf2":
            return False
        iterations = int(iters_s)
    except (ValueError, TypeError):
        return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(digest_b64)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def create_access_token(
    subject: str,
    secret: str,
    *,
    expires_minutes: int,
    extra: dict[str, Any] | None = None,
    algorithm: str = "HS256",
) -> str:
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + expires_minutes * 60,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, secret, algorithm=algorithm)


def decode_access_token(token: str, secret: str, algorithm: str = "HS256") -> dict[str, Any]:
    return jwt.decode(token, secret, algorithms=[algorithm])
