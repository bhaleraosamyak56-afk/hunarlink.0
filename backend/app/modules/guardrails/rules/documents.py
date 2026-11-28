"""Layer 3: Document & file upload security.

Enforces:
  - Strict extension allowlist (.jpg, .jpeg, .png, .webp, .pdf)
  - Real magic-byte signature verification (rejects spoofed extensions / MIME types)
  - File size ceiling (rejects empty or oversized files)
  - Server-generated UUID filenames (never trusts user filenames or paths)
  - Private storage strictly outside the public web root
  - SHA-256 hashing & malware scanner hook (PENDING_SCAN when AV unavailable)
"""
from __future__ import annotations

import hashlib
import os
import struct
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, status

from app.modules.guardrails.providers.malware_scanner import MalwareScanner

MAX_IMAGE_DIMENSION = 12_000
MAX_IMAGE_PIXELS = 50_000_000

ALLOWED_EXTENSIONS: dict[str, set[str]] = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
}


@dataclass(frozen=True)
class ValidatedUpload:
    detected_mime_type: str
    canonical_ext: str
    file_size_bytes: int
    sha256_hash: str
    storage_key: str
    absolute_path: Path
    scanner_engine: str
    scan_status: str
    scan_details: str


def _validate_image_dimensions(width: int, height: int) -> None:
    if width <= 0 or height <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image has invalid zero or negative dimensions.",
        )
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION or (width * height) > MAX_IMAGE_PIXELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image dimensions ({width}x{height}) exceed security limits.",
        )


def _strip_jpeg_metadata(payload: bytes) -> bytes:
    """Strip EXIF/GPS (APP1), IPTC (APP13), and COM markers while verifying SOF dimensions."""
    if len(payload) < 4 or payload[:2] != b"\xff\xd8":
        return payload
    out = bytearray(b"\xff\xd8")
    idx = 2
    n = len(payload)
    stripped_any = False

    while idx < n:
        if payload[idx] != 0xFF:
            # Reached entropy-coded scan or malformed stub -> return original if truncated
            return bytes(out) + payload[idx:] if stripped_any else payload
        while idx < n and payload[idx] == 0xFF:
            idx += 1
        if idx >= n:
            break
        marker = payload[idx]
        idx += 1

        if marker == 0xD9:  # EOI
            out.extend(b"\xff\xd9")
            break
        if marker == 0x00 or (0xD0 <= marker <= 0xD7) or marker == 0x01:
            out.extend((0xFF, marker))
            continue
        if marker == 0xDA:  # SOS — rest of stream until EOI
            out.extend((0xFF, marker))
            out.extend(payload[idx:])
            break
        if idx + 2 > n:
            return bytes(out) + payload[idx - 2 :] if stripped_any else payload

        seg_len = struct.unpack(">H", payload[idx : idx + 2])[0]
        if seg_len < 2 or idx + seg_len > n:
            return payload
        seg_body = payload[idx + 2 : idx + seg_len]

        # Validate SOF0/SOF1/SOF2 dimensions
        if marker in (0xC0, 0xC1, 0xC2) and len(seg_body) >= 5:
            height, width = struct.unpack(">HH", seg_body[1:5])
            _validate_image_dimensions(width, height)

        # Strip APP1 (EXIF/GPS/XMP), APP13 (IPTC), COM (0xFE)
        if marker in (0xE1, 0xED, 0xFE):
            stripped_any = True
        else:
            out.extend((0xFF, marker))
            out.extend(payload[idx : idx + seg_len])
        idx += seg_len

    return bytes(out) if stripped_any else payload


def _strip_png_metadata(payload: bytes) -> bytes:
    """Validate PNG IHDR dimensions and strip eXIf/tEXt/iTXt/zTXt metadata chunks."""
    sig = b"\x89PNG\r\n\x1a\n"
    if not payload.startswith(sig) or len(payload) < 24:
        return payload

    if payload[12:16] == b"IHDR" and len(payload) >= 24:
        width, height = struct.unpack(">II", payload[16:24])
        _validate_image_dimensions(width, height)

    # Support minimal 24-byte test fixtures gracefully if full chunks aren't present
    if len(payload) < 33:
        return payload

    out = bytearray(sig)
    idx = 8
    n = len(payload)
    stripped_any = False
    strip_types = {b"eXIf", b"tEXt", b"iTXt", b"zTXt"}

    while idx + 12 <= n:
        chunk_len = struct.unpack(">I", payload[idx : idx + 4])[0]
        chunk_type = payload[idx + 4 : idx + 8]
        total_chunk = 12 + chunk_len
        if idx + total_chunk > n:
            return payload
        if chunk_type in strip_types:
            stripped_any = True
        else:
            out.extend(payload[idx : idx + total_chunk])
        idx += total_chunk
        if chunk_type == b"IEND":
            break

    return bytes(out) if (stripped_any and idx == n) else payload


def _strip_webp_metadata(payload: bytes) -> bytes:
    """Validate WebP dimensions where present and strip EXIF/XMP metadata chunks."""
    if len(payload) < 12 or payload[:4] != b"RIFF" or payload[8:12] != b"WEBP":
        return payload
    idx = 12
    n = len(payload)
    body = bytearray()
    stripped_any = False

    while idx + 8 <= n:
        fourcc = payload[idx : idx + 4]
        chunk_size = struct.unpack("<I", payload[idx + 4 : idx + 8])[0]
        padded_size = chunk_size + (chunk_size & 1)
        if idx + 8 + padded_size > n:
            return payload
        chunk_data = payload[idx + 8 : idx + 8 + chunk_size]
        if fourcc == b"VP8X" and len(chunk_data) >= 10:
            width = 1 + int.from_bytes(chunk_data[4:7], "little")
            height = 1 + int.from_bytes(chunk_data[7:10], "little")
            _validate_image_dimensions(width, height)
        if fourcc in (b"EXIF", b"XMP "):
            stripped_any = True
        else:
            body.extend(payload[idx : idx + 8 + padded_size])
        idx += 8 + padded_size

    if not stripped_any:
        return payload
    riff_size = 4 + len(body)
    return b"RIFF" + struct.pack("<I", riff_size) + b"WEBP" + bytes(body)


def sanitize_image_metadata(payload: bytes, detected_mime: str) -> bytes:
    """Strip EXIF/GPS/XMP metadata and verify pixel bounds on uploaded images."""
    if detected_mime == "image/jpeg":
        return _strip_jpeg_metadata(payload)
    if detected_mime == "image/png":
        return _strip_png_metadata(payload)
    if detected_mime == "image/webp":
        return _strip_webp_metadata(payload)
    return payload


def detect_magic_mime(payload: bytes) -> str | None:
    """Inspect real leading file bytes rather than trusting extension or Content-Type."""
    if len(payload) < 8:
        return None
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload[:4] == b"RIFF" and len(payload) >= 12 and payload[8:12] == b"WEBP":
        return "image/webp"
    if payload.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def validate_and_store_private_document(
    *,
    original_filename: str,
    payload: bytes,
    owner_scope: str,
    uploader_user_id: str,
    storage_root: Path,
    max_size_bytes: int,
    malware_scanner: MalwareScanner,
) -> ValidatedUpload:
    clean_name = os.path.basename(original_filename or "").strip()
    if not clean_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded filename is missing.",
        )

    ext = Path(clean_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '{ext}' is not allowed. Permitted: {', '.join(sorted(ALLOWED_EXTENSIONS))}.",
        )

    size = len(payload)
    if size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )
    if size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File exceeds maximum allowed size of {max_size_bytes} bytes.",
        )

    detected_mime = detect_magic_mime(payload)
    if detected_mime is None or detected_mime not in ALLOWED_EXTENSIONS[ext]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "File content signature does not match its extension (possible spoofed file). "
                f"Extension='{ext}', detected='{detected_mime or 'unknown'}'."
            ),
        )

    # Extra defense for PDFs: block embedded JavaScript / launch actions in seller docs
    if detected_mime == "application/pdf" and (
        b"/JavaScript" in payload or b"/JS " in payload or b"/Launch" in payload
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF contains disallowed embedded script/launch actions.",
        )

    scan = malware_scanner.scan_bytes(payload)
    if scan.scan_status == "INFECTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Upload blocked by malware check: {scan.details}",
        )

    sanitized_payload = sanitize_image_metadata(payload, detected_mime)
    sanitized_size = len(sanitized_payload)
    sha256_hash = hashlib.sha256(sanitized_payload).hexdigest()
    safe_scope = "".join(c for c in owner_scope.lower() if c.isalnum() or c in ("_", "-")) or "general"
    server_filename = f"{uuid.uuid4().hex}{ext}"
    storage_key = f"{safe_scope}/{uploader_user_id}/{server_filename}"

    resolved_root = storage_root.resolve()
    target_path = (resolved_root / storage_key).resolve()
    if resolved_root not in target_path.parents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Resolved storage path escaped private storage root.",
        )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(sanitized_payload)

    return ValidatedUpload(
        detected_mime_type=detected_mime,
        canonical_ext=ext,
        file_size_bytes=sanitized_size,
        sha256_hash=sha256_hash,
        storage_key=storage_key,
        absolute_path=target_path,
        scanner_engine=scan.scanner_engine,
        scan_status=scan.scan_status,
        scan_details=scan.details,
    )
