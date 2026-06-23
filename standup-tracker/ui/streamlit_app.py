"""Standup Tracker — Streamlit UI.

Three tabs:
  1. Submit Standup  — POST /standups
  2. Standup History — GET /standups (filterable)
  3. Weekly Summary  — POST /summaries/generate + GET /summaries

Reads API_BASE_URL and API_KEY from .env (python-dotenv) or environment.
Never imports from app/ — all data comes from the API over HTTP.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import httpx
import streamlit as st

# ── Load .env if present (for local dev) ──────────────────────────────────────
try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.environ.get("API_KEY", "")

_HEADERS = {"X-API-Key": API_KEY}

# ── HTTP helpers ───────────────────────────────────────────────────────────────


def _get(path: str, **params: object) -> httpx.Response:
    return httpx.get(
        f"{API_BASE_URL}{path}",
        headers=_HEADERS,
        params={k: v for k, v in params.items() if v is not None},
        follow_redirects=True,
        timeout=30,
    )


def _post(path: str, body: dict) -> httpx.Response:
    return httpx.post(
        f"{API_BASE_URL}{path}",
        headers=_HEADERS,
        json=body,
        follow_redirects=True,
        timeout=60,
    )


def _delete(path: str) -> httpx.Response:
    return httpx.delete(
        f"{API_BASE_URL}{path}",
        headers=_HEADERS,
        follow_redirects=True,
        timeout=30,
    )


def _ensure_api_reachable() -> bool:
    """Check API health on startup; show clear error if not reachable."""
    try:
        resp = httpx.get(f"{API_BASE_URL}/health", timeout=5, follow_redirects=True)
        if resp.status_code == 200:
            return True
        st.error(
            f"⚠️ API health check returned **{resp.status_code}**. "
            f"Ensure the FastAPI server is running on {API_BASE_URL}."
        )
        return False
    except httpx.ConnectError:
        st.error(
            f"⚠️ Cannot reach API at **{API_BASE_URL}**. "
            "Start the backend first:\n\n"
            "```bash\nuvicorn app.main:app --reload --port 8000\n```"
        )
        return False
    except Exception as exc:  # noqa: BLE001
        st.error(f"⚠️ Unexpected error contacting API: {exc}")
        return False


def _show_api_error(resp: httpx.Response) -> None:
    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:  # noqa: BLE001
        detail = resp.text
    st.error(f"API error **{resp.status_code}**: {detail}")


# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Standup Tracker",
    page_icon="📋",
    layout="wide",
)
st.title("📋 Sprint Standup Tracker")

if not _ensure_api_reachable():
    st.stop()

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_submit, tab_history, tab_summary = st.tabs(
    ["✍️ Submit Standup", "📜 Standup History", "📊 Weekly Summary"]
)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: Submit Standup  (FR-10)
# ─────────────────────────────────────────────────────────────────────────────
with tab_submit:
    st.header("Submit Daily Standup")
    with st.form("submit_standup_form"):
        team_member = st.text_input("Your name *", max_chars=64, placeholder="e.g. Alice")
        standup_date = st.date_input("Standup date *", value=date.today())
        yesterday = st.text_area(
            "What did you do yesterday? *",
            placeholder="Completed X, reviewed PR #42 ...",
        )
        today_field = st.text_area(
            "What will you do today? *",
            placeholder="Work on Y, attend planning meeting ...",
        )
        blockers = st.text_area(
            "Any blockers? (optional)",
            placeholder="Waiting for RDS access ...",
        )
        submitted = st.form_submit_button("🚀 Submit Standup")

    if submitted:
        if not team_member.strip():
            st.warning("Please enter your name.")
        elif not yesterday.strip():
            st.warning("Please fill in what you did yesterday.")
        elif not today_field.strip():
            st.warning("Please fill in what you will do today.")
        else:
            payload: dict = {
                "team_member": team_member.strip(),
                "standup_date": str(standup_date),
                "yesterday": yesterday.strip(),
                "today": today_field.strip(),
                "blockers": blockers.strip() if blockers.strip() else None,
            }
            resp = _post("/standups", payload)
            if resp.status_code == 201:
                data = resp.json()
                st.success(
                    f"✅ Standup submitted! ID: `{data['id']}` "
                    f"({data['team_member']} — {data['standup_date']})"
                )
            else:
                _show_api_error(resp)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: Standup History  (FR-11)
# GET /standups collection view with filters
# ─────────────────────────────────────────────────────────────────────────────
with tab_history:
    st.header("Standup History")

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_member = st.text_input("Filter by team member", placeholder="Alice")
    with col2:
        filter_from = st.date_input(
            "Date from",
            value=date.today() - timedelta(days=14),
            key="hist_from",
        )
    with col3:
        filter_to = st.date_input("Date to", value=date.today(), key="hist_to")

    # Fetch standup list from GET /standups collection endpoint
    history_params: dict = {
        "limit": 100,
        "offset": 0,
    }
    if filter_member.strip():
        history_params["team_member"] = filter_member.strip()
    if filter_from:
        history_params["date_from"] = str(filter_from)
    if filter_to:
        history_params["date_to"] = str(filter_to)

    history_resp = _get("/standups", **history_params)

    if history_resp.status_code == 200:
        history_data = history_resp.json()
        items = history_data.get("items", [])
        total = history_data.get("total", 0)
        if not items:
            st.info("No standup entries found for the selected filters.")
        else:
            st.caption(f"Showing {len(items)} of {total} entries")
            for entry in items:
                with st.expander(
                    f"**{entry['team_member']}** — {entry['standup_date']}"
                ):
                    st.markdown(f"**Yesterday:** {entry['yesterday']}")
                    st.markdown(f"**Today:** {entry['today']}")
                    if entry.get("blockers"):
                        st.markdown(f"**Blockers:** {entry['blockers']}")
                    else:
                        st.markdown("**Blockers:** None")
                    st.caption(f"ID: `{entry['id']}` | Created: {entry['created_at']}")
                    if st.button(f"🗑️ Delete", key=f"del_{entry['id']}"):
                        del_resp = _delete(f"/standups/{entry['id']}")
                        if del_resp.status_code == 204:
                            st.success("Entry deleted.")
                            st.rerun()
                        else:
                            _show_api_error(del_resp)
    else:
        _show_api_error(history_resp)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3: Weekly Summary  (FR-12)
# POST /summaries/generate  +  GET /summaries collection view
# ─────────────────────────────────────────────────────────────────────────────
with tab_summary:
    st.header("Weekly AI Summary")
    st.caption(
        "Select the week range and click **Generate** to create an AI-powered summary "
        "using Amazon Bedrock (Claude Sonnet)."
    )

    # Calculate Monday/Friday of current week as defaults
    today_date = date.today()
    monday = today_date - timedelta(days=today_date.weekday())
    friday = monday + timedelta(days=4)

    col_a, col_b = st.columns(2)
    with col_a:
        week_start = st.date_input("Week start (Monday)", value=monday, key="ws_start")
    with col_b:
        week_end = st.date_input("Week end (Friday)", value=friday, key="ws_end")

    if st.button("✨ Generate Weekly Summary"):
        with st.spinner("Calling Bedrock (Claude Sonnet) … this may take up to 30 s"):
            gen_resp = _post(
                "/summaries/generate",
                {"week_start": str(week_start), "week_end": str(week_end)},
            )
        if gen_resp.status_code == 201:
            gen_data = gen_resp.json()
            st.success(f"✅ Summary generated! ID: `{gen_data['id']}`")
            st.markdown("---")
            st.markdown(gen_data["summary_markdown"])
            st.rerun()
        else:
            _show_api_error(gen_resp)

    st.markdown("---")
    st.subheader("Past Summaries")

    # Fetch summaries list from GET /summaries collection endpoint
    past_resp = _get("/summaries", limit=20, offset=0)
    if past_resp.status_code == 200:
        past_data = past_resp.json()
        past_items = past_data.get("items", [])
        if not past_items:
            st.info("No past summaries yet. Generate one above!")
        else:
            st.caption(f"{past_data.get('total', 0)} summaries found")
            for s in past_items:
                with st.expander(
                    f"Week {s['week_start']} → {s['week_end']}  |  "
                    f"Generated: {s['generated_at'][:10]}"
                ):
                    st.markdown(s["summary_markdown"])
                    st.caption(f"ID: `{s['id']}`")
    else:
        _show_api_error(past_resp)
