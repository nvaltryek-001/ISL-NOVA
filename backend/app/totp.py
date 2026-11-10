"""RFC 6238 time-based one-time passwords (SHA-1, 6 digits, 30 s), standard library only.

Compatible with common authenticator apps (Google Authenticator, Aegis,
Microsoft Authenticator, FreeOTP). Verified against the RFC 6238 test vectors
in backend/tests/test_sessions.py.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP = 30
DIGITS = 6


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def hotp(key: bytes, counter: int, digits: int = DIGITS, digest=hashlib.sha1) -> str:
    mac = hmac.new(key, struct.pack(">Q", counter), digest).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp(secret: str, at: float | None = None) -> str:
    return hotp(_key(secret), int((time.time() if at is None else at) // STEP))


def verify(secret: str, code: str, at: float | None = None, window: int = 1) -> int | None:
    """Returns the matching time step (to block reuse) or None. Accepts ±window steps of clock drift."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != DIGITS:
        return None
    now = int((time.time() if at is None else at) // STEP)
    key = _key(secret)
    for step in range(now - window, now + window + 1):
        if hmac.compare_digest(hotp(key, step), code):
            return step
    return None


def otpauth_uri(secret: str, account: str, issuer: str = "ISL NOVA") -> str:
    return (f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}"
            f"&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP}")
