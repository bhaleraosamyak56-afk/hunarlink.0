"""Password hashing (PBKDF2-HMAC-SHA256) & HS256 JWT helpers for dedicated Admin login.

Security rules:
  - Passwords are NEVER stored in plaintext; always salted PBKDF2-HMAC-SHA256
    with 390,000 iterations and constant-time comparison.
  - Admin JWTs carry `iss="hunarlink-admin"` and `token_type="admin_password_session"`,
    and every protected request still re-checks `admin_credentials`, `admin_profiles`,
    and `ADMIN` role live in the database.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import Settings

PBKDF2_ITERATIONS = 390_000
ADMIN_JWT_ISSUER = "hunarlink-admin"
ADMIN_TOKEN_TYPE = "admin_password_session"

# Ephemeral runtime fallback used only in local dev when ADMIN_JWT_SECRET is unset in .env
_PROCESS_FALLBACK_SECRET = secrets.token_urlsafe(48)


def _signing_secret(settings: Settings) -> str:
    configured = settings.admin_jwt_secret.get_secret_value().strip()
    if configured:
        return configured
    return _PROCESS_FALLBACK_SECRET


def hash_admin_password(plain_password: str) -> str:
    if not plain_password or len(plain_password) < 8:
        raise ValueError("Admin password must be at least 8 characters long.")
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        plain_password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_admin_password(plain_password: str, stored_hash: str) -> bool:
    if not plain_password or not stored_hash:
        return False
    try:
        parts = stored_hash.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hex = parts[3]
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(dk.hex(), expected_hex)
    except Exception:
        return False


def create_admin_session_token(
    *,
    user_id: str,
    email: str = "",
    settings: Settings,
) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    ttl = int(settings.admin_session_ttl_seconds)
    # Keep PII (such as email) out of JWT payloads; DB lookup loads current email.
    payload = {
        "sub": user_id,
        "iss": ADMIN_JWT_ISSUER,
        "token_type": ADMIN_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl)).timestamp()),
    }
    token = jwt.encode(payload, _signing_secret(settings), algorithm="HS256")
    return token, ttl


def verify_admin_session_token(token: str, settings: Settings) -> dict | None:
    """Return decoded claims if `token` is a valid HunarLink Admin HS256 JWT, else None."""
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return None
    if header.get("alg") != "HS256":
        return None
    try:
        claims = jwt.decode(
            token,
            _signing_secret(settings),
            algorithms=["HS256"],
            issuer=ADMIN_JWT_ISSUER,
            leeway=15,
        )
        if claims.get("token_type") != ADMIN_TOKEN_TYPE or not claims.get("sub"):
            return None
        return claims
    except Exception:
        return None
