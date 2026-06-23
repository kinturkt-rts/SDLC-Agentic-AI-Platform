"""ORM model for standup_tracker.standup_entries."""
from __future__ import annotations

import uuid

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class StandupEntry(Base):
    __tablename__ = "standup_entries"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    team_member: Mapped[str] = mapped_column(String(64), nullable=False)
    standup_date: Mapped[str] = mapped_column(String(10), nullable=False)  # DATE stored as text in SQLite
    yesterday: Mapped[str] = mapped_column(Text, nullable=False)
    today: Mapped[str] = mapped_column(Text, nullable=False)
    blockers: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now(),
        default=func.now(),
    )
