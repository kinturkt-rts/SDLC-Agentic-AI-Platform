"""Application entry-point for standup-tracker."""
from __future__ import annotations

import logging
import logging.config
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import health
from app.routers import standups
from app.routers import summaries
from app.startup_checks import validate_runtime_config

logger = logging.getLogger(__name__)

_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)s}',
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        }
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logging.config.dictConfig(_LOG_CONFIG)
    settings = get_settings()
    validate_runtime_config(settings)

    # Auto-create tables when the engine is SQLite (smoke test / local dev without Postgres)
    from app.database import Base, engine

    # Import models so SQLAlchemy registers them in metadata
    import app.models.standup_entry  # noqa: F401
    import app.models.weekly_summary  # noqa: F401

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)

    logger.info('"startup_checks_passed service=%s"', settings.service_name)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Standup Tracker",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception('"unhandled_error path=%s"', request.url.path)
        if (settings.app_env or "").strip().lower() == "development":
            return JSONResponse(
                status_code=500,
                content={"detail": str(exc), "type": exc.__class__.__name__},
            )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # Register routers
    application.include_router(health.router)
    application.include_router(standups.router, prefix="/standups")
    application.include_router(summaries.router, prefix="/summaries")

    @application.get("/")
    def root() -> dict[str, str]:
        return {"service": settings.service_name, "status": "ok"}

    return application


app = create_app()
