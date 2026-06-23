"""Router for /standups endpoints."""
from __future__ import annotations

import re
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import ApiKey, DbSession
from app.models.standup_entry import StandupEntry
from schemas.standups import StandupCreate, StandupListPage, StandupOut

logger = logging.getLogger(__name__)
router = APIRouter(tags=["standups"])

_SECRET_PATTERNS = re.compile(
    r"(API_KEY|DATABASE_URL|SECRET|PASSWORD|TOKEN)", re.IGNORECASE
)


@router.post("", response_model=StandupOut, status_code=status.HTTP_201_CREATED)
def create_standup(
    body: StandupCreate,
    db: DbSession,
    _key: ApiKey,
) -> StandupEntry:
    """FR-2: Create a new standup entry."""
    # Optionally normalise team_member (Open Q2 — lowercase to reduce fragmentation)
    team_member = body.team_member.strip()

    entry = StandupEntry(
        team_member=team_member,
        standup_date=str(body.standup_date),
        yesterday=body.yesterday,
        today=body.today,
        blockers=body.blockers,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    logger.info("standup_created id=%s member=%s", entry.id, team_member)
    return entry  # type: ignore[return-value]


@router.get("", response_model=StandupListPage)
def list_standups(
    db: DbSession,
    _key: ApiKey,
    team_member: Optional[str] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> StandupListPage:
    """FR-3: List standup entries with optional filters and pagination."""
    stmt = select(StandupEntry)
    count_stmt = select(func.count(StandupEntry.id))

    if team_member:
        stmt = stmt.where(StandupEntry.team_member == team_member)
        count_stmt = count_stmt.where(StandupEntry.team_member == team_member)
    if date_from:
        date_from_str = str(date_from)
        stmt = stmt.where(StandupEntry.standup_date >= date_from_str)
        count_stmt = count_stmt.where(StandupEntry.standup_date >= date_from_str)
    if date_to:
        date_to_str = str(date_to)
        stmt = stmt.where(StandupEntry.standup_date <= date_to_str)
        count_stmt = count_stmt.where(StandupEntry.standup_date <= date_to_str)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(stmt.offset(offset).limit(limit)).all()

    return StandupListPage(
        items=list(rows),  # type: ignore[arg-type]
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{entry_id}", response_model=StandupOut)
def get_standup(
    entry_id: str,
    db: DbSession,
    _key: ApiKey,
) -> StandupEntry:
    """FR-4: Retrieve a single standup entry."""
    entry = db.get(StandupEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standup entry not found")
    return entry  # type: ignore[return-value]


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
def delete_standup(
    entry_id: str,
    db: DbSession,
    _key: ApiKey,
) -> None:
    """FR-5: Hard-delete a standup entry."""
    entry = db.get(StandupEntry, entry_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Standup entry not found")
    db.delete(entry)
    db.commit()
    logger.info("standup_deleted id=%s", entry_id)
