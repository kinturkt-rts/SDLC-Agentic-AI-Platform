"""Pydantic v2 schemas for weekly summaries."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator


class SummaryGenerateRequest(BaseModel):
    week_start: date
    week_end: date


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    week_start: date
    week_end: date
    summary_markdown: str
    generated_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str:
        return str(v) if v is not None else v  # type: ignore[return-value]

    @field_validator("week_start", "week_end", mode="before")
    @classmethod
    def coerce_date(cls, v: object) -> date:
        if isinstance(v, date):
            return v
        return date.fromisoformat(str(v))


class SummaryListPage(BaseModel):
    items: list[SummaryOut]
    total: int
    limit: int
    offset: int
