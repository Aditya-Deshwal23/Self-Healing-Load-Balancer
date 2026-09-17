from __future__ import annotations

import base64
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SHLB_",
        case_sensitive=False,
        extra="ignore",
    )

    environment: str = "local"
    log_level: str = "INFO"

    database_host: str = "postgres"
    database_port: int = 5432
    database_name: str = "shlb"
    database_user: str = "shlb_api"
    database_password_file: Path = Path("/run/secrets/postgres_password")

    redis_host: str = "redis"
    redis_port: int = 6379
    redis_database: int = 0
    redis_password_file: Path = Path("/run/secrets/redis_password")

    field_encryption_key_file: Path = Path("/run/secrets/field_encryption_key")
    bootstrap_email: str = "admin@shlb.local"
    bootstrap_password_file: Path = Path("/run/secrets/bootstrap_password")

    cookie_name: str = "shlb_session"
    cookie_secure: bool = True
    cookie_domain: str | None = None
    session_idle_seconds: int = 8 * 60 * 60
    session_absolute_seconds: int = 24 * 60 * 60
    allowed_origins: Annotated[tuple[str, ...], NoDecode] = (
        "https://localhost:8443",
        "https://127.0.0.1:8443",
        "https://testserver",
    )
    request_body_limit: int = 1024 * 1024
    event_stream_max_length: int = 10_000
    event_heartbeat_seconds: int = 15

    @field_validator("bootstrap_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) > 320 or "@" not in normalized:
            raise ValueError("bootstrap email must be a bounded email address")
        return normalized

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(item.strip().rstrip("/") for item in value.split(",") if item.strip())
        return value

    @model_validator(mode="after")
    def validate_security_bounds(self) -> "Settings":
        if self.session_idle_seconds <= 0 or self.session_idle_seconds > self.session_absolute_seconds:
            raise ValueError("session idle timeout must be positive and no longer than the absolute timeout")
        if self.request_body_limit <= 0 or self.request_body_limit > 1024 * 1024:
            raise ValueError("ordinary request body limit may not exceed 1 MiB")
        if self.event_heartbeat_seconds < 5 or self.event_heartbeat_seconds > 60:
            raise ValueError("SSE heartbeat must stay within the bounded operational range")
        return self

    @staticmethod
    def _read_secret(path: Path, *, minimum_bytes: int) -> str:
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"required secret file is unavailable: {path}") from exc
        if len(value.encode("utf-8")) < minimum_bytes:
            raise RuntimeError(f"secret file does not meet the minimum length: {path}")
        return value

    @cached_property
    def database_password(self) -> str:
        return self._read_secret(self.database_password_file, minimum_bytes=24)

    @cached_property
    def redis_password(self) -> str:
        return self._read_secret(self.redis_password_file, minimum_bytes=24)

    @cached_property
    def bootstrap_password(self) -> str:
        return self._read_secret(self.bootstrap_password_file, minimum_bytes=20)

    @cached_property
    def field_encryption_key(self) -> bytes:
        encoded = self._read_secret(self.field_encryption_key_file, minimum_bytes=40)
        try:
            key = base64.urlsafe_b64decode(encoded)
        except ValueError as exc:
            raise RuntimeError("field encryption key is not valid URL-safe base64") from exc
        if len(key) != 32:
            raise RuntimeError("field encryption key must decode to exactly 32 bytes")
        return key

    @property
    def database_url(self) -> str:
        from urllib.parse import quote_plus

        return (
            f"postgresql+psycopg://{quote_plus(self.database_user)}:{quote_plus(self.database_password)}"
            f"@{self.database_host}:{self.database_port}/{quote_plus(self.database_name)}"
        )

    @property
    def redis_url(self) -> str:
        from urllib.parse import quote_plus

        return (
            f"redis://:{quote_plus(self.redis_password)}"
            f"@{self.redis_host}:{self.redis_port}/{self.redis_database}"
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Fail startup before serving if mandatory secrets are malformed or missing.
    _ = (
        settings.database_password,
        settings.redis_password,
        settings.bootstrap_password,
        settings.field_encryption_key,
    )
    return settings
