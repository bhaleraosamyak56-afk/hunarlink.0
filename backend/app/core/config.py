"""Typed application settings loaded from environment variables (never hardcoded)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = Field(default="development")
    app_name: str = Field(default="HunarLink API")
    api_v1_prefix: str = Field(default="/api/v1")
    debug: bool = Field(default=False)

    # Explicit CORS & Host allowlists (never wildcard in production)
    cors_allowed_origins: str = Field(
        default=(
            "http://localhost:5173,http://127.0.0.1:5173,"
            "http://localhost:5174,http://127.0.0.1:5174,"
            "http://localhost:5175,http://127.0.0.1:5175"
        )
    )
    trusted_hosts: str = Field(default="localhost,127.0.0.1,testserver")
    frontend_base_url: str = Field(default="http://localhost:5173")

    # MySQL 8.4 LTS connection parts
    mysql_host: str = Field(default="127.0.0.1")
    mysql_port: int = Field(default=3306)
    mysql_database: str = Field(default="hunarlink")
    mysql_user: str = Field(default="hunarlink_app")
    mysql_password: SecretStr = Field(default=SecretStr(""))
    mysql_charset: str = Field(default="utf8mb4")
    database_url: str = Field(default="")

    # Clerk authentication (identity only)
    clerk_issuer: str = Field(default="")
    clerk_jwks_url: str = Field(default="")
    clerk_audience: str = Field(default="")
    clerk_webhook_secret: SecretStr = Field(default=SecretStr(""))

    # Dedicated Admin Email+Password JWT signing secret (HS256; never hardcode in prod)
    admin_jwt_secret: SecretStr = Field(default=SecretStr(""))
    admin_session_ttl_seconds: int = Field(default=28800, ge=300, le=86400)

    # Razorpay Standard Checkout (India / INR initial release)
    razorpay_mode: str = Field(default="test")
    razorpay_key_id: str = Field(default="")
    razorpay_key_secret: SecretStr = Field(default=SecretStr(""))
    razorpay_webhook_secret: SecretStr = Field(default=SecretStr(""))
    razorpay_currency: str = Field(default="INR")
    razorpay_timeout_seconds: int = Field(default=15, ge=2, le=60)

    # Private document storage & ASIGS file security
    private_storage_dir: str = Field(default="./var/private_uploads")
    max_upload_size_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    malware_scanner_mode: str = Field(default="disabled")

    # GI reference dataset version for deterministic verification
    gi_reference_dataset_version: str = Field(default="unconfigured")

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def trusted_hosts_list(self) -> List[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def private_storage_path(self) -> Path:
        return Path(self.private_storage_dir).resolve()

    def build_mysql_url(self) -> URL:
        """Build a safe SQLAlchemy MySQL URL even when passwords contain special chars."""
        return URL.create(
            drivername="mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password.get_secret_value(),
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
            query={"charset": self.mysql_charset},
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
