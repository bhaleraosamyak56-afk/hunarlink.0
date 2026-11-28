"""DigiLocker OAuth 2.0 + PKCE & Artisan Card Fetch Service.

Supports two explicit modes:
  1. LIVE (`DIGILOCKER_CLIENT_ID` + `DIGILOCKER_CLIENT_SECRET` configured):
     Redirects the registering artisan to MeriPehchaan / DigiLocker OAuth 2.0
     with PKCE (`S256`), exchanges the authorization `code` for an access token,
     queries `/public/oauth2/2/files/issued` for an official Artisan / Pehchan
     ID card, downloads the real issued document bytes from `/public/oauth2/1/file/{uri}`,
     and stores them in private encrypted/scanned storage (`file_security_scans`).
  2. SANDBOX (`DIGILOCKER_MODE=sandbox` in non-production when partner keys are not yet set):
     Provides an explicit DigiLocker Sandbox consent flow that fetches a deterministic
     Pehchan / J&K Handicrafts Artisan Card PNG (rendered with a QR code & metadata)
     into private scanned storage so end-to-end registration and Admin inspection
     work cleanly before live MeitY/API Setu credentials are provisioned.

In `APP_ENV=production`, sandbox fallback is strictly disabled (`503`) unless live
DigiLocker OAuth credentials are configured.
"""
from __future__ import annotations

import base64
import hashlib
import secrets
import struct
import urllib.parse
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import segno
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import record_audit_log
from app.core.auth import AuthenticatedPrincipal
from app.core.config import Settings
from app.models.base import new_uuid, utcnow
from app.models.core_models import DigiLockerVerification, User
from app.modules.guardrails.schemas import FileUploadResponse
from app.modules.guardrails.service import upload_private_document

# Supported official DigiLocker Artisan Card Issuers
DIGILOCKER_ISSUERS: dict[str, dict[str, str]] = {
    "in.gov.handicrafts": {
        "issuer_id": "in.gov.handicrafts",
        "issuer_name": "Office of DC (Handicrafts), Ministry of Textiles, Govt. of India",
        "doc_type": "PEHCHAN_ARTISAN_CARD",
        "label": "Pehchan Artisan ID Card (Ministry of Textiles)",
    },
    "in.gov.jk.handicrafts": {
        "issuer_id": "in.gov.jk.handicrafts",
        "issuer_name": "Directorate of Handicrafts & Handloom, Govt. of Jammu & Kashmir",
        "doc_type": "JK_ARTISAN_REG_CARD",
        "label": "J&K Handicrafts & Handloom Artisan Registration Card",
    },
}

# Compact 5x7 uppercase + digit + punctuation bitmap font for crisp pure-Python PNG cards
_FONT_5X7: dict[str, tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "J": ("00111", "00010", "00010", "00010", "10010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10011", "10101", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "00100", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
}


def render_artisan_card_png(
    *,
    holder_name: str,
    card_number: str,
    issuer_name: str,
    issuer_id: str,
    craft_category: str,
    district: str,
    issued_date: str,
    doc_uri: str,
    is_sandbox: bool = True,
) -> bytes:
    """Render an authentic 760x480 RGB PNG DigiLocker Artisan Card with embedded QR."""
    width, height = 760, 480
    # Warm ivory background (#FAF8F3)
    bg_r, bg_g, bg_b = 250, 248, 243
    row_base = bytes([bg_r, bg_g, bg_b]) * width
    buf = bytearray([0] * (height * (1 + width * 3)))
    stride = 1 + width * 3
    for y in range(height):
        off = y * stride
        buf[off] = 0  # PNG filter type 0
        buf[off + 1 : off + stride] = row_base

    def fill_rect(x0: int, y0: int, w: int, h: int, rgb: tuple[int, int, int]) -> None:
        r, g, b = rgb
        x_start = max(0, x0)
        x_end = min(width, x0 + w)
        y_start = max(0, y0)
        y_end = min(height, y0 + h)
        if x_start >= x_end or y_start >= y_end:
            return
        seg = bytes([r, g, b]) * (x_end - x_start)
        for yy in range(y_start, y_end):
            idx = yy * stride + 1 + x_start * 3
            buf[idx : idx + (x_end - x_start) * 3] = seg

    def draw_text(x: int, y: int, text: str, scale: int, rgb: tuple[int, int, int]) -> None:
        up = str(text or "").upper()
        cur_x = x
        for ch in up:
            glyph = _FONT_5X7.get(ch, _FONT_5X7[" "])
            for gy, line in enumerate(glyph):
                for gx, bit in enumerate(line):
                    if bit == "1":
                        fill_rect(cur_x + gx * scale, y + gy * scale, scale, scale, rgb)
            cur_x += 6 * scale
            if cur_x + 5 * scale >= width - 16:
                break

    # Outer card border (DigiLocker Navy + Kashmiri Forest accent)
    navy = (17, 56, 118)
    forest = (13, 43, 29)
    gold = (184, 133, 40)
    slate = (68, 79, 73)
    ink = (22, 30, 26)
    white = (255, 255, 255)
    soft_blue = (232, 241, 253)

    fill_rect(14, 14, width - 28, height - 28, white)
    # 2px outer frame
    fill_rect(14, 14, width - 28, 3, navy)
    fill_rect(14, height - 17, width - 28, 3, navy)
    fill_rect(14, 14, 3, height - 28, navy)
    fill_rect(width - 17, 14, 3, height - 28, navy)

    # Top header bar
    fill_rect(17, 17, width - 34, 82, navy)
    fill_rect(17, 99, width - 34, 4, gold)
    draw_text(34, 31, "GOVERNMENT OF INDIA  /  DIGILOCKER ISSUED DOCUMENT", 2, (242, 217, 138))
    draw_text(34, 57, "PEHCHAN ARTISAN IDENTITY CARD", 3, white)

    # Verification status strip
    fill_rect(34, 118, width - 68, 34, soft_blue)
    mode_tag = "DIGILOCKER SANDBOX FETCH (TEST)" if is_sandbox else "DIGILOCKER LIVE VERIFIED"
    draw_text(46, 128, f"STATUS: {mode_tag}", 2, navy)

    # Left metadata fields
    draw_text(36, 172, "ARTISAN NAME", 2, slate)
    draw_text(36, 192, holder_name[:28], 3, ink)

    draw_text(36, 228, "PEHCHAN / ARTISAN CARD NO.", 2, slate)
    draw_text(36, 248, card_number[:28], 3, forest)

    draw_text(36, 286, "CRAFT SPECIALTY", 2, slate)
    draw_text(36, 304, craft_category[:32], 2, ink)

    draw_text(36, 336, "DISTRICT / CLUSTER", 2, slate)
    draw_text(36, 354, district[:32], 2, ink)

    draw_text(36, 386, "ISSUING AUTHORITY", 2, slate)
    draw_text(36, 404, issuer_name[:44], 2, ink)

    # Right panel QR code box
    qr_payload = f"digilocker:{issuer_id}|{card_number}|{holder_name}|{issued_date}"
    qr = segno.make(qr_payload, error="m")
    matrix = qr.matrix
    q_size = len(matrix)
    cell = max(3, min(5, 165 // q_size))
    box_dim = q_size * cell + 20
    qx = width - box_dim - 36
    qy = 172
    fill_rect(qx, qy, box_dim, box_dim, (248, 250, 253))
    fill_rect(qx, qy, box_dim, 2, navy)
    fill_rect(qx, qy + box_dim - 2, box_dim, 2, navy)
    fill_rect(qx, qy, 2, box_dim, navy)
    fill_rect(qx + box_dim - 2, qy, 2, box_dim, navy)
    for r_idx, row in enumerate(matrix):
        for c_idx, val in enumerate(row):
            if val:
                fill_rect(qx + 10 + c_idx * cell, qy + 10 + r_idx * cell, cell, cell, forest)

    draw_text(qx, qy + box_dim + 10, "ISSUED DATE", 1, slate)
    draw_text(qx, qy + box_dim + 21, issued_date, 2, navy)
    draw_text(qx, qy + box_dim + 40, f"REF: {doc_uri[-22:]}", 1, slate)

    # Footer bar inside card
    fill_rect(34, height - 42, width - 68, 20, (242, 245, 243))
    draw_text(44, height - 36, f"DIGILOCKER VERIFIED ARTISAN RECORD  -  {doc_uri[:46]}", 1, slate)

    def _chunk(ctype: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(ctype + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    idat = _chunk(b"IDAT", zlib.compress(bytes(buf), level=6))
    iend = _chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def effective_digilocker_mode(settings: Settings) -> str:
    """Return 'live' when partner keys exist (or mode=='live'), else 'sandbox' in non-prod."""
    req_mode = (settings.digilocker_mode or "sandbox").strip().lower()
    if settings.digilocker_live_configured:
        return "live"
    if req_mode == "live" or settings.app_env.strip().lower() == "production":
        return "live"
    return "sandbox"


def _build_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def _sanitize_return_to(raw_return_to: str | None) -> str:
    val = (raw_return_to or "").strip()
    if val.startswith("/") and not val.startswith("//"):
        return val[:255]
    return "/auth?tab=verify"


def resolve_redirect_uri(settings: Settings, request_base_url: str) -> str:
    if settings.digilocker_redirect_uri.strip():
        return settings.digilocker_redirect_uri.strip()
    base = request_base_url.rstrip("/")
    prefix = settings.api_v1_prefix.rstrip("/")
    return f"{base}{prefix}/auth/digilocker/callback"


def get_digilocker_status(settings: Settings) -> dict[str, Any]:
    mode = effective_digilocker_mode(settings)
    return {
        "mode": mode,
        "live_configured": settings.digilocker_live_configured,
        "issuers": [
            DIGILOCKER_ISSUERS[k]
            for k in settings.digilocker_issuer_list
            if k in DIGILOCKER_ISSUERS
        ]
        or list(DIGILOCKER_ISSUERS.values()),
    }


def start_digilocker_auth(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    settings: Settings,
    request_base_url: str,
    return_to: str | None = None,
    correlation_id: str,
) -> dict[str, Any]:
    mode = effective_digilocker_mode(settings)
    if mode == "live" and not settings.digilocker_live_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DigiLocker Live OAuth credentials (DIGILOCKER_CLIENT_ID / DIGILOCKER_CLIENT_SECRET) are not configured.",
        )

    state_token = secrets.token_urlsafe(32)
    verifier, challenge = _build_pkce_pair()
    safe_return = _sanitize_return_to(return_to)

    row = DigiLockerVerification(
        id=new_uuid(),
        user_id=principal.user_id,
        state_token=state_token,
        pkce_verifier=verifier,
        mode="LIVE" if mode == "live" else "SANDBOX",
        status="INITIATED",
        return_to=safe_return,
        expires_at=utcnow() + timedelta(minutes=12),
    )
    db.add(row)
    record_audit_log(
        db,
        actor_user_id=principal.user_id,
        actor_role="DIRECT_SELLER",
        action="DIGILOCKER_AUTH_INITIATED",
        target_type="digilocker_verifications",
        target_id=row.id,
        correlation_id=correlation_id,
        new_values={"mode": row.mode},
    )
    db.commit()

    authorize_url = None
    if mode == "live":
        redirect_uri = resolve_redirect_uri(settings, request_base_url)
        qs = urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": settings.digilocker_client_id.strip(),
                "redirect_uri": redirect_uri,
                "state": state_token,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        base_auth = settings.digilocker_auth_base_url.rstrip("/")
        authorize_url = f"{base_auth}/public/oauth2/1/authorize?{qs}"

    return {
        "verification_id": row.id,
        "state": state_token,
        "mode": mode,
        "authorize_url": authorize_url,
        "issuers": get_digilocker_status(settings)["issuers"],
        "expires_at": row.expires_at,
    }


def _store_fetched_card_bytes(
    db: Session,
    *,
    user_id: str,
    filename: str,
    content_type: str,
    card_bytes: bytes,
    settings: Settings,
    correlation_id: str,
) -> FileUploadResponse:
    # Build a principal for uploader_user_id so FileSecurityScan ownership belongs strictly to the artisan
    user = db.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan user not found.")
    uploader_principal = AuthenticatedPrincipal(
        user_id=user.id,
        clerk_user_id=user.clerk_user_id,
        email=user.email,
        account_status=user.account_status,
        roles=frozenset({"DIRECT_SELLER"}),
    )
    return upload_private_document(
        db,
        principal=uploader_principal,
        owner_scope="artisan_card",
        original_filename=filename,
        claimed_content_type=content_type,
        payload=card_bytes,
        settings=settings,
        correlation_id=correlation_id,
    )


def _select_artisan_issued_doc(items: list[dict[str, Any]], issuer_allowlist: list[str]) -> dict[str, Any] | None:
    if not items:
        return None
    # Prefer official Pehchan / J&K Handicrafts issuers first
    for item in items:
        issuer = str(item.get("issuerid") or item.get("issuerId") or "").strip().lower()
        if any(issuer == allowed.lower() for allowed in issuer_allowlist):
            return item
    # Otherwise match Artisan / Pehchan / Handicraft keywords in doc name/doctype/uri
    for item in items:
        haystack = " ".join(
            str(item.get(k) or "") for k in ("name", "doctype", "description", "uri", "issuer")
        ).lower()
        if any(kw in haystack for kw in ("artisan", "pehchan", "handicraft", "handloom")):
            return item
    return None


def complete_live_digilocker_callback(
    db: Session,
    *,
    code: str,
    state: str,
    settings: Settings,
    request_base_url: str,
    correlation_id: str,
) -> DigiLockerVerification:
    row = db.scalar(
        select(DigiLockerVerification).where(DigiLockerVerification.state_token == state.strip())
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid DigiLocker OAuth state.")
    if row.status != "INITIATED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DigiLocker session already completed.")
    now = utcnow()
    exp = row.expires_at.replace(tzinfo=None) if row.expires_at.tzinfo is not None else row.expires_at
    if exp < now:
        row.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DigiLocker authorization expired. Please try again.")
    if not settings.digilocker_live_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DigiLocker live credentials are not configured.",
        )

    base_auth = settings.digilocker_auth_base_url.rstrip("/")
    redirect_uri = resolve_redirect_uri(settings, request_base_url)

    try:
        with httpx.Client(timeout=15.0) as client:
            token_resp = client.post(
                f"{base_auth}/public/oauth2/1/token",
                data={
                    "code": code,
                    "grant_type": "authorization_code",
                    "client_id": settings.digilocker_client_id.strip(),
                    "client_secret": settings.digilocker_client_secret.get_secret_value().strip(),
                    "redirect_uri": redirect_uri,
                    "code_verifier": row.pkce_verifier or "",
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="DigiLocker token exchange failed. Please retry authentication.",
                )
            token_data = token_resp.json()
            access_token = str(token_data.get("access_token") or "").strip()
            if not access_token:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="DigiLocker did not return an access token.",
                )

            auth_headers = {"Authorization": f"Bearer {access_token}"}
            issued_resp = client.get(
                f"{base_auth}/public/oauth2/2/files/issued",
                headers={**auth_headers, "Accept": "application/json"},
            )
            if issued_resp.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Could not fetch issued documents from DigiLocker.",
                )
            issued_payload = issued_resp.json()
            items = issued_payload.get("items") if isinstance(issued_payload, dict) else []
            doc_item = _select_artisan_issued_doc(
                items if isinstance(items, list) else [],
                settings.digilocker_issuer_list,
            )
            if doc_item is None or not doc_item.get("uri"):
                row.status = "FAILED"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        "No Pehchan / Artisan ID Card was found in your DigiLocker Issued Documents. "
                        "Please fetch your Artisan Card in DigiLocker first and retry."
                    ),
                )

            doc_uri = str(doc_item["uri"]).strip()
            encoded_uri = urllib.parse.quote(doc_uri, safe="")
            file_resp = client.get(
                f"{base_auth}/public/oauth2/1/file/{encoded_uri}",
                headers=auth_headers,
            )
            if file_resp.status_code != 200 or not file_resp.content:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Could not download the issued Artisan Card document from DigiLocker.",
                )

            content_type = (file_resp.headers.get("content-type") or "application/pdf").split(";")[0].strip().lower()
            ext = ".pdf" if "pdf" in content_type else ".png" if "png" in content_type else ".jpg"
            upload_res = _store_fetched_card_bytes(
                db,
                user_id=row.user_id,
                filename=f"digilocker_artisan_card_{row.id[:8]}{ext}",
                content_type=content_type,
                card_bytes=file_resp.content,
                settings=settings,
                correlation_id=correlation_id,
            )
    except HTTPException:
        raise
    except Exception:
        row.status = "FAILED"
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="DigiLocker service error while fetching your Artisan Card.",
        )

    holder_name = str(token_data.get("name") or doc_item.get("name") or "Verified Artisan").strip()[:160]
    issuer_id = str(doc_item.get("issuerid") or doc_item.get("issuerId") or "in.gov.handicrafts").strip()[:128]
    issuer_name = str(doc_item.get("issuer") or DIGILOCKER_ISSUERS.get(issuer_id, {}).get("issuer_name") or issuer_id).strip()[:255]
    card_number = str(doc_item.get("docid") or doc_uri.split("-")[-1] or row.id[:12]).strip()[:100]

    row.status = "FETCHED"
    row.mode = "LIVE"
    row.issuer_id = issuer_id
    row.issuer_name = issuer_name
    row.doc_type = str(doc_item.get("doctype") or "PEHCHAN_ARTISAN_CARD")[:64]
    row.doc_uri = doc_uri[:255]
    row.artisan_card_number = card_number
    row.card_holder_name = holder_name
    row.issued_date = str(doc_item.get("date") or utcnow().strftime("%Y-%m-%d"))[:32]
    row.file_scan_id = upload_res.scan_id
    row.fetched_at = utcnow()
    row.raw_claims_json = {
        "digilocker_id": token_data.get("digilockerid"),
        "issuer_id": issuer_id,
        "issuer_name": issuer_name,
        "doc_uri": doc_uri,
        "doctype": row.doc_type,
        "mime_type": upload_res.detected_mime_type,
    }

    record_audit_log(
        db,
        actor_user_id=row.user_id,
        actor_role="DIRECT_SELLER",
        action="DIGILOCKER_ARTISAN_CARD_FETCHED",
        target_type="digilocker_verifications",
        target_id=row.id,
        correlation_id=correlation_id,
        new_values={
            "mode": "LIVE",
            "issuer_id": issuer_id,
            "card_number": card_number,
            "scan_id": upload_res.scan_id,
        },
    )
    db.commit()
    db.refresh(row)
    return row


def complete_sandbox_digilocker(
    db: Session,
    *,
    principal: AuthenticatedPrincipal,
    verification_id: str,
    issuer_id: str,
    artisan_card_number: str,
    card_holder_name: str,
    craft_category: str,
    district: str,
    settings: Settings,
    correlation_id: str,
) -> DigiLockerVerification:
    if effective_digilocker_mode(settings) != "sandbox" or settings.app_env.strip().lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="DigiLocker Sandbox mode is disabled in this environment.",
        )

    row = db.scalar(
        select(DigiLockerVerification).where(DigiLockerVerification.id == verification_id.strip())
    )
    if row is None or row.user_id != principal.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DigiLocker session not found.")
    if row.status != "INITIATED":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DigiLocker session is already completed.")
    now = utcnow()
    exp = row.expires_at.replace(tzinfo=None) if row.expires_at.tzinfo is not None else row.expires_at
    if exp < now:
        row.status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DigiLocker session expired. Start again.")

    issuer_info = DIGILOCKER_ISSUERS.get(issuer_id.strip()) or DIGILOCKER_ISSUERS["in.gov.handicrafts"]
    clean_card_no = artisan_card_number.strip().upper()[:100]
    clean_holder = card_holder_name.strip()[:160]
    clean_craft = craft_category.strip()[:160] or "Handloom & Heritage Craft"
    clean_district = district.strip()[:120] or "Srinagar"
    issued_date = utcnow().strftime("%Y-%m-%d")
    doc_uri = f"{issuer_info['issuer_id']}-{issuer_info['doc_type']}-{clean_card_no}"[:255]

    png_bytes = render_artisan_card_png(
        holder_name=clean_holder,
        card_number=clean_card_no,
        issuer_name=issuer_info["issuer_name"],
        issuer_id=issuer_info["issuer_id"],
        craft_category=clean_craft,
        district=clean_district,
        issued_date=issued_date,
        doc_uri=doc_uri,
        is_sandbox=True,
    )

    upload_res = _store_fetched_card_bytes(
        db,
        user_id=row.user_id,
        filename=f"digilocker_{clean_card_no.lower().replace('/', '_')}.png",
        content_type="image/png",
        card_bytes=png_bytes,
        settings=settings,
        correlation_id=correlation_id,
    )

    row.status = "FETCHED"
    row.mode = "SANDBOX"
    row.issuer_id = issuer_info["issuer_id"]
    row.issuer_name = issuer_info["issuer_name"]
    row.doc_type = issuer_info["doc_type"]
    row.doc_uri = doc_uri
    row.artisan_card_number = clean_card_no
    row.card_holder_name = clean_holder
    row.craft_category = clean_craft
    row.district = clean_district
    row.issued_date = issued_date
    row.file_scan_id = upload_res.scan_id
    row.fetched_at = utcnow()
    row.raw_claims_json = {
        "issuer_id": row.issuer_id,
        "issuer_name": row.issuer_name,
        "doc_uri": doc_uri,
        "doctype": row.doc_type,
        "sandbox_verified": True,
    }

    record_audit_log(
        db,
        actor_user_id=row.user_id,
        actor_role="DIRECT_SELLER",
        action="DIGILOCKER_ARTISAN_CARD_FETCHED",
        target_type="digilocker_verifications",
        target_id=row.id,
        correlation_id=correlation_id,
        new_values={
            "mode": "SANDBOX",
            "issuer_id": row.issuer_id,
            "card_number": clean_card_no,
            "scan_id": upload_res.scan_id,
        },
    )
    db.commit()
    db.refresh(row)
    return row
