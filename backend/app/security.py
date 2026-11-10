"""Password hashing (PBKDF2-HMAC-SHA256), JWT tokens and role permissions."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt

ROLES: dict[str, str] = {
    "admin": "Full administration, model promotion, user management",
    "linguist": "Qualified ISL reviewer: verifies signs, translations and annotations",
    "data_curator": "Manages signers, consent, sessions, recordings and dataset versions",
    "researcher": "Runs experiments and reads evaluation results",
    "learner": "Uses recognition, learning, communication and personal history",
    "teacher": "Creates classes and sees the learning progress of learners who joined them",
}

PERMISSIONS: dict[str, set[str]] = {
    "signs:write": {"admin", "linguist"},
    "signs:review": {"admin", "linguist"},
    "translations:write": {"admin", "linguist"},
    "dataset:read": {"admin", "linguist", "data_curator", "researcher"},
    "dataset:write": {"admin", "data_curator"},
    "dataset:review": {"admin", "linguist"},
    "dataset:version": {"admin", "data_curator"},
    "experiments:read": {"admin", "researcher", "data_curator"},
    "experiments:write": {"admin", "researcher"},
    "models:promote": {"admin"},
    "feedback:read": {"admin", "linguist"},
    "phrases:quick": {"admin", "linguist"},
    "admin:users": {"admin"},
    "admin:audit": {"admin"},
    "classes:manage": {"admin", "teacher"},
    "analytics:read": {"admin", "researcher"},
}

MIN_PASSWORD = 10


def has_perm(roles: set[str], perm: str) -> bool:
    return bool(roles & PERMISSIONS[perm])


def hash_password(password: str, iterations: int) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, it, salt, dk = encoded.split("$")
        if algo != "pbkdf2_sha256":
            return False
        calc = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(it))
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


# a fixed dummy hash keeps login timing similar for unknown emails
DUMMY_HASH = "pbkdf2_sha256$1000$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


def create_token(user_id: int, secret: str, ttl_minutes: int, token_version: int = 0) -> tuple[str, int]:
    """Signed access token. ``tv`` is the user's token version: bumping it
    (sign out everywhere) invalidates every token issued before."""
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=ttl_minutes)
    tok = jwt.encode({"sub": str(user_id), "iat": now, "exp": exp, "typ": "access", "tv": int(token_version)},
                     secret, algorithm="HS256")
    return tok, ttl_minutes * 60


def decode_token(token: str, secret: str) -> tuple[int, int] | None:
    """Returns (user_id, token_version) or None. Tokens without ``tv`` count as version 0."""
    try:
        data = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.PyJWTError:
        return None
    if data.get("typ") != "access":
        return None
    try:
        return int(data["sub"]), int(data.get("tv", 0))
    except (KeyError, ValueError, TypeError):
        return None
