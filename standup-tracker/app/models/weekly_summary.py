"""ORM model for standup_tracker.weekly_summaries."""
from __future__ import annotations

import uuid

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.pg_types import TimestampTZ, pg_uuid_column


class WeeklySummary(Base):
    __tablename__ = "weekly_summaries"

    id: Mapped[str] = mapped_column(
        pg_uuid_column(),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        server_default=func.gen_random_uuid(),
    )
    week_start: Mapped[str] = mapped_column(String(10), nullable=False)  # DATE stored as text in SQLite
    week_end: Mapped[str] = mapped_column(String(10), nullable=False)  # DATE stored as text in SQLite
    summary_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    generated_at: Mapped[object] = mapped_column(
        TimestampTZ,
        nullable=False,
        server_default=func.now(),
        default=func.now(),
    )
