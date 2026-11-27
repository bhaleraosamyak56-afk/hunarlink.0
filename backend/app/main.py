"""HunarLink FastAPI Backend Application Entrypoint.

Wires together:
  - Strict CORS allowlist (never `*` with credentials)
  - Security headers + request correlation ID middleware
  - ASIGS Advanced Seller Input Guardrail System (`/api/v1/...`)
  - Razorpay Standard Checkout, Webhooks, Refunds, Admin Ops (`/api/v1/...`)
  - Safe health endpoints (`/healthz`, `/readyz`) with zero secret exposure
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import CorrelationAndHeadersMiddleware
from app.modules.auth.router import router as auth_router
from app.modules.craftproof.router import router as craftproof_router
from app.modules.demand_bridge.router import router as demand_bridge_router
from app.modules.guardrails.router import router as guardrails_router
from app.modules.payments.router import router as payments_router
from app.modules.payments.webhook_router import webhook_router as razorpay_webhook_router
from app.modules.storefront.router import router as storefront_router

logger = logging.getLogger("hunarlink.backend")


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()

    application = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        docs_url="/docs" if settings.app_env != "production" else None,
        redoc_url="/redoc" if settings.app_env != "production" else None,
        openapi_url="/openapi.json" if settings.app_env != "production" else None,
    )

    if settings_override is not None:
        application.dependency_overrides[get_settings] = lambda: settings_override

    application.add_middleware(
        CorrelationAndHeadersMiddleware,
        allow_dev_iframe=(settings.app_env == "development"),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            "X-Idempotency-Key",
            "X-Razorpay-Signature",
            "x-razorpay-event-id",
        ],
    )

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        corr_id = getattr(request.state, "correlation_id", "unknown")
        logger.error("Unhandled backend error [%s]: %s", corr_id, type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal error occurred.",
                "correlation_id": corr_id,
            },
        )

    @application.get("/", tags=["Health"])
    def root() -> dict:
        return {
            "service": settings.app_name,
            "status": "ok",
            "environment": settings.app_env,
            "docs": "/docs" if settings.app_env != "production" else None,
            "healthz": "/healthz",
            "readyz": "/readyz",
            "api_prefix": settings.api_v1_prefix,
        }

    @application.get("/healthz", tags=["Health"])
    def healthz() -> dict:
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.app_env,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @application.get("/readyz", tags=["Health"])
    def readyz(db: Session = Depends(get_db)) -> JSONResponse:
        db_connected = False
        dialect_name = None
        try:
            db.execute(text("SELECT 1"))
            db_connected = True
            if db.bind is not None:
                dialect_name = db.bind.dialect.name
        except Exception:
            logger.warning("Readiness probe could not reach configured database.")

        payload = {
            "status": "ready" if db_connected else "degraded",
            "database": "connected" if db_connected else "unavailable",
            "database_dialect": dialect_name,
            "clerk_configured": bool(
                (settings.clerk_issuer or "").strip() and (settings.clerk_jwks_url or "").strip()
            ),
            "malware_scanner_mode": settings.malware_scanner_mode,
            "razorpay_configured": bool(
                settings.razorpay_key_id and settings.razorpay_key_secret.get_secret_value()
            ),
        }
        return JSONResponse(
            status_code=status.HTTP_200_OK if db_connected else status.HTTP_503_SERVICE_UNAVAILABLE,
            content=payload,
        )

    application.include_router(auth_router, prefix=settings.api_v1_prefix)
    application.include_router(storefront_router, prefix=settings.api_v1_prefix)
    application.include_router(guardrails_router, prefix=settings.api_v1_prefix)
    application.include_router(payments_router, prefix=settings.api_v1_prefix)
    application.include_router(razorpay_webhook_router, prefix=settings.api_v1_prefix)
    application.include_router(craftproof_router, prefix=settings.api_v1_prefix)
    application.include_router(demand_bridge_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()
