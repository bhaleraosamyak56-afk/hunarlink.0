"""Pure-Python QR code rendering and HMAC-SHA256 tag signing for CraftProof Passports."""
from __future__ import annotations

import hashlib
import hmac
import io
import secrets
from typing import Any

import segno

_PROCESS_FALLBACK_QR_SECRET = secrets.token_urlsafe(48)


def resolve_qr_secret(secret_or_settings: Any) -> str:
    """Resolve CraftProof QR HMAC secret from Settings or SecretStr/str with dev fallback."""
    if hasattr(secret_or_settings, "qr_signing_secret"):
        raw = secret_or_settings.qr_signing_secret.get_secret_value().strip()
        if raw:
            return raw
        if getattr(secret_or_settings, "is_production", False):
            raise RuntimeError("QR_SIGNING_SECRET must be configured in production.")
        return _PROCESS_FALLBACK_QR_SECRET
    if hasattr(secret_or_settings, "get_secret_value"):
        raw = secret_or_settings.get_secret_value().strip()
        return raw or _PROCESS_FALLBACK_QR_SECRET
    raw = str(secret_or_settings or "").strip()
    return raw or _PROCESS_FALLBACK_QR_SECRET


def make_passport_serial(passport_code: str, listing_id: str) -> str:
    """Derive a deterministic, human-readable anti-counterfeit tag serial number."""
    digest = hashlib.sha256(f"{passport_code}:{listing_id}".encode("utf-8")).hexdigest().upper()
    return f"HL-TAG-{digest[:10]}"


def sign_passport_qr(
    *,
    passport_code: str,
    serial_number: str,
    secret: Any,
) -> str:
    """Compute a compact HMAC-SHA256 tag signature bound to passport_code + serial_number."""
    key = resolve_qr_secret(secret)
    message = f"{passport_code.strip()}:{serial_number.strip()}".encode("utf-8")
    return hmac.new(key.encode("utf-8"), message, hashlib.sha256).hexdigest()[:24]


def verify_passport_qr_signature(
    *,
    passport_code: str,
    serial_number: str,
    sig: str | None,
    secret: Any,
) -> bool:
    """Constant-time verification of a scanned CraftProof QR signature."""
    if not sig or not serial_number:
        return False
    expected = sign_passport_qr(
        passport_code=passport_code,
        serial_number=serial_number,
        secret=secret,
    )
    return hmac.compare_digest(expected, sig.strip().lower())


def generate_passport_qr_svg(passport_url: str, scale: int = 6) -> bytes:
    """Render a crisp, high-contrast SVG QR code pointing to a signed Craft Passport URL."""
    qr = segno.make(passport_url, error="m")
    buf = io.BytesIO()
    qr.save(
        buf,
        kind="svg",
        scale=scale,
        border=2,
        dark="#14382A",
        light="#FFFDF8",
        xmldecl=False,
        svgclass="craftproof-qr-svg",
    )
    return buf.getvalue()
