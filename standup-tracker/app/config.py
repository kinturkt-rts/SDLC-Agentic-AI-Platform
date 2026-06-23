"""Service configuration for standup-tracker."""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return (init_settings, env_settings, dotenv_settings, file_secret_settings)
        skip = os.environ.get("SKIP_STARTUP_CHECKS", "").strip().lower()
        if skip in ("1", "true", "yes"):
            return (init_settings, env_settings, dotenv_settings, file_secret_settings)
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    # ── App ──────────────────────────────────────────────────────────────
    app_env: str = Field("development", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    service_name: str = Field("standup-tracker", alias="SERVICE_NAME")

    # ── Postgres (RDS) ───────────────────────────────────────────────────
    database_url: str = Field("", alias="DATABASE_URL")
    postgres_schema: str = Field("standup_tracker", alias="POSTGRES_SCHEMA")

    # ── Auth ─────────────────────────────────────────────────────────────
    api_key: str = Field("", alias="API_KEY")

    # ── CORS ─────────────────────────────────────────────────────────────
    cors_origins: list[str] = Field(default_factory=lambda: ["*"], alias="CORS_ORIGINS")

    # ── AWS / Bedrock ─────────────────────────────────────────────────────
    aws_region: str = Field("us-east-2", alias="AWS_REGION")
    bedrock_region: str = Field("us-east-2", alias="BEDROCK_REGION")
    bedrock_model_id: str = Field(
        "us.anthropic.claude-sonnet-4-20250514-v1:0", alias="BEDROCK_MODEL_ID"
    )
    bedrock_max_tokens: int = Field(4096, alias="BEDROCK_MAX_TOKENS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
