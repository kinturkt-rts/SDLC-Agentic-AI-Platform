"""Router for /summaries endpoints.

Routes (all under prefix=/summaries in main.py):
  GET  /summaries                - list summaries (FR-7)
  GET  /summaries/generate       - alias list for Streamlit selectbox/table (UI parity)
  GET  /summaries/{id}           - get single summary (FR-8)
  POST /summaries/generate       - generate AI summary via Bedrock (FR-6)
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.dependencies import ApiKey, DbSession
from app.models.standup_entry import StandupEntry
from app.models.weekly_summary import WeeklySummary
from app.services.bedrock_client import get_bedrock_client
from app.services.prompts import SYSTEM_PROMPT, build_summary_prompt
from schemas.summaries import SummaryGenerateRequest, SummaryListPage, SummaryOut

logger = logging.getLogger(__name__)
router = APIRouter(tags=["summaries"])

_SECRET_RE = re.compile(
    r"(API_KEY|DATABASE_URL|SECRET|PASSWORD|TOKEN|CREDENTIAL)", re.IGNORECASE
)


def _list_summaries_query(
    db: DbSession,
    limit: int,
    offset: int,
) -> SummaryListPage:
    """Shared implementation for list endpoints."""
    total = db.scalar(select(func.count(WeeklySummary.id))) or 0
    rows = db.scalars(
        select(WeeklySummary)
        .order_by(WeeklySummary.week_start.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return SummaryListPage(
        items=list(rows),  # type: ignore[arg-type]
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("", response_model=SummaryListPage)
def list_summaries(
    db: DbSession,
    _key: ApiKey,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SummaryListPage:
    """FR-7: List weekly summaries ordered by week_start DESC."""
    return _list_summaries_query(db, limit=limit, offset=offset)


@router.get("/generate", response_model=SummaryListPage)
def list_summaries_generate(
    db: DbSession,
    _key: ApiKey,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SummaryListPage:
    """Paginated GET alias on /generate path for UI parity — returns same list as GET /summaries."""
    return _list_summaries_query(db, limit=limit, offset=offset)


@router.post("/generate", response_model=SummaryOut, status_code=status.HTTP_201_CREATED)
def generate_summary(
    body: SummaryGenerateRequest,
    db: DbSession,
    _key: ApiKey,
) -> WeeklySummary:
    """FR-6: Fetch entries in range and generate AI summary via Bedrock."""
    week_start_str = str(body.week_start)
    week_end_str = str(body.week_end)

    # Fetch all entries in range
    rows = db.scalars(
        select(StandupEntry)
        .where(StandupEntry.standup_date >= week_start_str)
        .where(StandupEntry.standup_date <= week_end_str)
        .order_by(StandupEntry.team_member, StandupEntry.standup_date)
    ).all()

    entry_dicts = [
        {
            "team_member": r.team_member,
            "standup_date": r.standup_date,
            "yesterday": r.yesterday,
            "today": r.today,
            "blockers": r.blockers,
        }
        for r in rows
    ]

    user_msg = build_summary_prompt(week_start_str, week_end_str, entry_dicts)

    try:
        bedrock = get_bedrock_client()
        markdown = bedrock.invoke_text(SYSTEM_PROMPT, user_msg)
    except Exception as exc:
        logger.exception("bedrock_invoke_failed week=%s..%s", week_start_str, week_end_str)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Bedrock invocation failed: {exc}",
        ) from exc

    # Secret scrub before persist (NFR-5)
    if _SECRET_RE.search(markdown):
        logger.warning("secret_pattern_detected_in_summary — redacting")
        markdown = _SECRET_RE.sub("[REDACTED]", markdown)

    summary = WeeklySummary(
        week_start=week_start_str,
        week_end=week_end_str,
        summary_markdown=markdown,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    logger.info("summary_created id=%s week=%s..%s", summary.id, week_start_str, week_end_str)
    return summary  # type: ignore[return-value]


@router.get("/{summary_id}", response_model=SummaryOut)
def get_summary(
    summary_id: str,
    db: DbSession,
    _key: ApiKey,
) -> WeeklySummary:
    """FR-8: Retrieve a single weekly summary."""
    summary = db.get(WeeklySummary, summary_id)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Summary not found")
    return summary  # type: ignore[return-value]
