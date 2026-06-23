# Standup Tracker

Sprint Standup Tracker — FastAPI + PostgreSQL backend with Streamlit UI.  
Team members submit daily standups (yesterday / today / blockers).  
Engineering managers generate AI-powered weekly summaries via Amazon Bedrock (Claude Sonnet).

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup](#setup)
3. [Running the App](#running-the-app)
4. [Environment Variables](#environment-variables)
5. [Swagger / API Docs](#swagger--api-docs)
6. [Role & Endpoint Quick Reference](#role--endpoint-quick-reference)
7. [Seed Data (Stable UUIDs)](#seed-data-stable-uuids)
8. [RDS Smoke Test](#rds-smoke-test)
9. [Running Tests](#running-tests)
10. [Architecture Notes](#architecture-notes)

---

## Prerequisites

- Python 3.12+
- PostgreSQL (RDS or local Docker) with schema `standup_tracker` created and DDL applied
- AWS credentials configured for Bedrock (`bedrock:InvokeModel` permission in `us-east-2`)

---

## Setup

### Windows (PowerShell) + bash

```bash
# 1. Clone / navigate to repo root
cd target-apps/standup-tracker

# 2. Create and activate virtual environment
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1

# macOS / Linux / Git Bash:
source .venv/bin/activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Copy environment template and fill in values
cp .env.example .env
# Edit .env — replace placeholders (DATABASE_URL, API_KEY, etc.)
# IMPORTANT: every line must be KEY=value — e.g. DATABASE_URL=postgresql+psycopg://...
# Never paste a bare URL without the DATABASE_URL= prefix.
```

---

## Running the App

### Terminal 1 — FastAPI backend

```bash
cd target-apps/standup-tracker
source .venv/bin/activate   # or .venv\Scripts\Activate.ps1 on Windows
uvicorn app.main:app --reload --port 8000
```

API available at: http://localhost:8000  
Swagger UI: http://localhost:8000/docs

### Terminal 2 — Streamlit UI

```bash
cd target-apps/standup-tracker
source .venv/bin/activate   # or .venv\Scripts\Activate.ps1 on Windows
pip install -r ui/requirements.txt
cd ui
streamlit run streamlit_app.py --server.port 8501
```

UI available at: http://localhost:8501

> **Note:** Streamlit reads `API_BASE_URL` and `API_KEY` from the `.env` file in the
> repo root (`target-apps/standup-tracker/.env`). Ensure the file exists and the
> `API_KEY` matches what the FastAPI server is configured with.

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ | — | Full Postgres DSN: `postgresql+psycopg://user:pass@host:5432/db?sslmode=require` |
| `POSTGRES_SCHEMA` | ✅ | `standup_tracker` | Postgres schema name |
| `API_KEY` | ✅ | — | Shared API key for `X-API-Key` header |
| `APP_ENV` | | `development` | `development` / `production` / `test` |
| `LOG_LEVEL` | | `INFO` | Python log level |
| `AWS_REGION` | ✅ for Bedrock | `us-east-2` | AWS region for Bedrock |
| `BEDROCK_REGION` | | `us-east-2` | Bedrock region (defaults to `AWS_REGION`) |
| `BEDROCK_MODEL_ID` | | `us.anthropic.claude-sonnet-4-20250514-v1:0` | Claude Sonnet model ID |
| `BEDROCK_MAX_TOKENS` | | `4096` | Max tokens for Bedrock response |
| `API_BASE_URL` | UI only | `http://localhost:8000` | URL Streamlit uses to call the API |

> ⚠️ Never commit `.env` to source control. It is listed in `.gitignore`.

---

## Swagger / API Docs

1. Open http://localhost:8000/docs
2. Click **Authorize** (🔒 icon top-right)
3. Enter your `API_KEY` value in the `X-API-Key` field
4. Click **Authorize** and then **Close**
5. All protected endpoints will now send the API key automatically

---

## Role & Endpoint Quick Reference

This app uses a single shared `X-API-Key` — no role-based login.

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/health` | GET | None | DB health check |
| `/standups` | POST | X-API-Key | Create standup entry |
| `/standups` | GET | X-API-Key | List + filter entries |
| `/standups/{id}` | GET | X-API-Key | Get single entry |
| `/standups/{id}` | DELETE | X-API-Key | Delete entry |
| `/summaries/generate` | POST | X-API-Key | Generate AI weekly summary |
| `/summaries` | GET | X-API-Key | List summaries |
| `/summaries/{id}` | GET | X-API-Key | Get single summary |

**Quick curl example** (replace `YOUR_KEY`):

```bash
# Health check (no auth)
curl http://localhost:8000/health

# Create a standup entry
curl -X POST http://localhost:8000/standups \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"team_member":"Alice","standup_date":"2025-06-23","yesterday":"Wrote tests.","today":"Deploy to staging."}'

# List entries
curl http://localhost:8000/standups -H "X-API-Key: YOUR_KEY"

# Generate weekly summary
curl -X POST http://localhost:8000/summaries/generate \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"week_start":"2025-06-16","week_end":"2025-06-20"}'
```

---

## Seed Data (Stable UUIDs)

After running `db/sql/004_seed.sql` against your RDS instance, the following rows exist:

### `standup_tracker.standup_entries` (6 rows)

| UUID | Team Member | Date |
|------|-------------|------|
| `a1111111-0001-4000-8000-000000000001` | Alice | Monday this week |
| `a1111111-0002-4000-8000-000000000002` | Alice | Tuesday this week |
| `b2222222-0001-4000-8000-000000000003` | Bob | Monday this week |
| `b2222222-0002-4000-8000-000000000004` | Bob | Tuesday this week |
| `c3333333-0001-4000-8000-000000000005` | Carol | Monday this week |
| `c3333333-0002-4000-8000-000000000006` | Carol | Tuesday this week |

### `standup_tracker.weekly_summaries` (1 row)

| UUID | Week Start | Week End |
|------|------------|----------|
| `d4444444-0001-4000-8000-000000000007` | Last Monday | Last Friday |

**Retrieve a seed entry:**
```bash
curl http://localhost:8000/standups/a1111111-0001-4000-8000-000000000001 \
  -H "X-API-Key: YOUR_KEY"
```

---

## RDS Smoke Test

After configuring `.env` with real RDS credentials:

**Step 1** — Check API health and DB connectivity:
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","checks":{"api":"ok","database":"ok"}}
```

**Step 2** — List standup entries (exercises DB read):
```bash
curl "http://localhost:8000/standups?limit=5" -H "X-API-Key: YOUR_KEY"
# Expected: {"items":[...],"total":6,"limit":5,"offset":0}
```

**Step 3** — Retrieve a seed entry by stable UUID:
```bash
curl http://localhost:8000/standups/a1111111-0001-4000-8000-000000000001 \
  -H "X-API-Key: YOUR_KEY"
# Expected: 200 with Alice's Monday standup
```

If you see `{"status":"degraded","checks":{"database":"error:..."}}` on `/health`:
- Confirm `DATABASE_URL` in `.env` starts with `DATABASE_URL=` (not a bare URL)
- Check RDS security group allows inbound from your IP on port 5432
- Verify `sslmode=require` is present in the DSN

---

## Running Tests

```bash
cd target-apps/standup-tracker
source .venv/bin/activate
pytest -q
```

Tests use SQLite in-memory — no Postgres or Bedrock connection required.  
Bedrock is mocked at the router import site in `tests/test_summaries.py`.

---

## Architecture Notes

- **Auth:** Shared `X-API-Key` header. All routes except `GET /health` require the key.
- **Startup:** `app/startup_checks.py` validates `DATABASE_URL` and DB connectivity at boot;  
  exits non-zero with an actionable error if misconfigured.
- **Bedrock:** `app/services/bedrock_client.py` retries up to 3 times with exponential back-off;  
  returns `503` on exhaustion. Model: `us.anthropic.claude-sonnet-4-20250514-v1:0` in `us-east-2`.
- **Secret scrub:** Generated summaries are checked for `API_KEY`/`DATABASE_URL` patterns before  
  INSERT; matches are redacted (`[REDACTED]`).
- **Schema:** All tables live in `standup_tracker` schema; `POSTGRES_SCHEMA` env var controls this.
- **Data retention:** No automatic deletion in v1; use `DELETE /standups/{id}` manually.
- **team_member normalisation:** Names are stored as-entered with leading/trailing whitespace stripped.
