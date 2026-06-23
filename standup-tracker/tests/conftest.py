"""pytest configuration for standup-tracker — SQLite in-memory with schema ATTACH."""
from __future__ import annotations

import os
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

# ── 1. Env BEFORE any app import ────────────────────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POSTGRES_SCHEMA", "standup_tracker")
os.environ.setdefault("API_KEY", "test-key")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import String, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator


# ── 2. UUID TypeDecorator for SQLite ──────────────────────────────────────────────────
class _UUIDStr(TypeDecorator):
    """Stores UUID as 36-char string in SQLite; always returns str."""
    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value: Any, dialect: Any) -> str | None:
        if value is None:
            return None
        return str(value)


def _patch_uuid_columns_for_sqlite(metadata: Any) -> None:
    """Replace PG_UUID columns with _UUIDStr so sqlite3 can bind them."""
    from sqlalchemy.dialects.postgresql import UUID as PG_UUID
    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, PG_UUID):
                col.type = _UUIDStr()


# ── 3. Import app (AFTER env is set) ──────────────────────────────────────────────────
from app import database as _db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


# ── 4. Engine + session fixtures ─────────────────────────────────────────────────────
def _build_test_engine() -> Engine:
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    schema = os.environ.get("POSTGRES_SCHEMA", "standup_tracker")

    @event.listens_for(eng, "connect")
    def _on_connect(dbapi_conn: Any, _record: Any) -> None:
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        if schema and schema != "public":
            try:
                cur.execute(f"ATTACH DATABASE ':memory:' AS {schema}")
            except Exception:  # noqa: BLE001
                pass
        cur.close()

    return eng


@pytest.fixture(scope="session")
def engine() -> Engine:
    eng = _build_test_engine()
    _patch_uuid_columns_for_sqlite(Base.metadata)
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture()
def db_session(engine: Engine) -> Generator[Session, None, None]:
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                conn.exec_driver_sql(f"DELETE FROM {table.name}")


@pytest.fixture()
def client(engine: Engine, db_session: Session) -> Generator[TestClient, None, None]:
    _db_module.engine = engine
    _db_module.SessionLocal.configure(bind=engine)

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def _override() -> Generator[Session, None, None]:
        sess = TestingSession()
        try:
            yield sess
        finally:
            sess.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── 5. Auth fixture ───────────────────────────────────────────────────────────────────
@pytest.fixture()
def api_headers() -> dict[str, str]:
    """Valid X-API-Key headers for all protected routes."""
    return {"X-API-Key": os.environ["API_KEY"]}


# ── 6. Domain seed fixtures ───────────────────────────────────────────────────────────
from app.models.standup_entry import StandupEntry  # noqa: E402
from app.models.weekly_summary import WeeklySummary  # noqa: E402


@pytest.fixture()
def sample_entry(db_session: Session) -> StandupEntry:
    entry = StandupEntry(
        id=str(uuid.uuid4()),
        team_member="Alice",
        standup_date="2025-06-16",
        yesterday="Finished router tests.",
        today="Write integration tests.",
        blockers=None,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.fixture()
def sample_summary(db_session: Session) -> WeeklySummary:
    summary = WeeklySummary(
        id=str(uuid.uuid4()),
        week_start="2025-06-09",
        week_end="2025-06-13",
        summary_markdown="## Team Summary\nAll good.\n## Per-Member Updates\n**Alice** Done.\n## Blockers\nNone.\n## Key Achievements\nLaunched.",
    )
    db_session.add(summary)
    db_session.commit()
    db_session.refresh(summary)
    return summary
