# Standup Tracker MVP — Solution Design

## 1. Summary
Internal daily standup tracking tool: team members submit yesterday/today/blockers via Streamlit; managers generate AI-powered weekly summaries via Amazon Bedrock (Claude Sonnet). FastAPI + PostgreSQL backend, single-tenant, API-key auth only.
Diagram: `docs/diagrams/generated-diagrams/standup-tracker.png`
TBD: `team_member` normalisation policy (Open Q2); `POST /summaries/generate` upsert-vs-insert behaviour (Open Q5).

## 2. Stack
| Layer | Technology | Path / Notes |
|-------|------------|--------------|
| UI | Streamlit | `ui/streamlit_app.py` calls FastAPI over HTTP (port 8501) |
| API | FastAPI + Uvicorn | `target-apps/standup-tracker/app/`; port 8000 |
| ORM | SQLAlchemy 2.x sync + psycopg[binary] | `app/database.py` |
| DB | PostgreSQL (schema `standup_tracker`) | RDS or local Docker; `DATABASE_URL` env var |
| AI | Amazon Bedrock Claude Sonnet | `app/services/bedrock_client.py`; mocked in tests |
| Scheduler | APScheduler (in-process) | Daily reminders; no SQS/Lambda |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|-------|---------|-----------------------|
| `standup_tracker.standup_entries` | `id uuid PK`, `team_member varchar(64) NOT NULL`, `standup_date date NOT NULL`, `yesterday text NOT NULL`, `today text NOT NULL`, `blockers text`, `created_at timestamptz NOT NULL DEFAULT now()` | `idx_entries_member_date ON (team_member, standup_date DESC)` |
| `standup_tracker.weekly_summaries` | `id uuid PK`, `week_start date NOT NULL`, `week_end date NOT NULL`, `summary_markdown text NOT NULL`, `generated_at timestamptz NOT NULL DEFAULT now()` | `idx_summaries_week_start ON (week_start DESC)` |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/health` | — | `{status, db}` 200/503 | No auth (FR-1) |
| POST | `/standups` | `{team_member, standup_date, yesterday, today, blockers?}` | `StandupOut` 201 | FR-2 |
| GET | `/standups` | `?team_member&date_from&date_to&limit=50&offset=0` | `{items, total, limit, offset}` 200 | FR-3 |
| GET | `/standups/{id}` | — | `StandupOut` 200/404 | FR-4 |
| DELETE | `/standups/{id}` | — | 204/404 | FR-5 |
| POST | `/summaries/generate` | `{week_start, week_end}` | `SummaryOut` 201 | FR-6; calls Bedrock |
| GET | `/summaries` | `?limit=20&offset=0` | `{items, total, limit, offset}` 200 | FR-7; ordered `week_start DESC` |
| GET | `/summaries/{id}` | — | `SummaryOut` 200/404 | FR-8 |

## 5. Rules
- **Auth**: `X-API-Key` header required on all routes except `GET /health`; missing/wrong key → `401` (FR-9, NFR-4). Key loaded from `API_KEY` env var in `app/config.py`.
- **Startup guard**: `app/startup_checks.py` validates `DATABASE_URL` presence and DB reachability; exits non-zero on failure (FR-13).
- **Bedrock prompt**: built in `app/services/prompts.py`; system prompt requires four Markdown sections, forbids inventing data or emitting secrets (FR-15, NFR-5).
- **Secret scrub**: post-generation regex in router checks `summary_markdown` for `API_KEY`/`DATABASE_URL` patterns before INSERT (NFR-5).
- **Logging**: structured JSON per request (method, path, status, latency) and per Bedrock call (model, tokens, duration) via Python `logging` + JSON formatter (NFR-8).
- **Bedrock retry**: exponential back-off, max 3 attempts in `bedrock_client.py`; returns `503` on exhaustion.
- **No audit table**: no RBAC beyond shared key in v1; all deletes are hard-deletes (FR-5).

## 6. DB delivery
1. Migration order: `001_create_schema.sql`, `002_create_standup_entries.sql`, `003_create_weekly_summaries.sql`
2. Seed (`004_seed.sql`): 5–6 `standup_entries` rows across 3 members (Alice, Bob, Carol) for current week with stable UUIDs; 1 `weekly_summaries` row for previous week with stable UUID (FR-14).
3. Pre-DDL: `CREATE SCHEMA IF NOT EXISTS standup_tracker;` at top of `001_create_schema.sql`; all tables qualified with schema name.
