"""Pydantic v2 schemas for standup entries."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class StandupCreate(BaseModel):
    team_member: str
    standup_date: date
    yesterday: str
    today: str
    blockers: Optional[str] = None


class StandupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    team_member: str
    standup_date: date
    yesterday: str
    today: str
    blockers: Optional[str] = None
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_uuid(cls, v: object) -> str:
        return str(v) if v is not None else v  # type: ignore[return-value]

    @field_validator("standup_date", mode="before")
    @classmethod
    def coerce_date(cls, v: object) -> date:
        if isinstance(v, date):
            return v
        return date.fromisoformat(str(v))


class StandupListPage(BaseModel):
    items: list[StandupOut]
    total: int
    limit: int
    offset: int
