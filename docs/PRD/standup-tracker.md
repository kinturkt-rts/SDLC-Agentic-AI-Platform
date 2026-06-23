# Sprint Standup Tracker — PRD

## 1. Overview

Engineering teams lose standup context when notes are scattered across Slack threads or forgotten between meetings. Managers lack a consolidated view of weekly progress, blockers, and team accomplishments, making it difficult to identify recurring impediments or report sprint outcomes.

The Sprint Standup Tracker is a lightweight internal web application that lets team members submit structured daily standup entries (yesterday / today / blockers) via a Streamlit UI backed by a FastAPI REST API and a PostgreSQL database. At the end of each week, a manager or automation consumer can trigger an AI-generated weekly summary using Amazon Bedrock (Claude Sonnet), which groups updates by team member and highlights key achievements and blockers.

This document covers the MVP: a single-team deployment with shared API-key authentication, no user login table, no third-party integrations, and a complete Python stack (FastAPI + SQLAlchemy + Streamlit) deployed under `target-apps/standup-tracker/`. The primary purpose is also to serve as a medium-complexity end-to-end SDLC pipeline validation covering the product → architect → database → developer → QA agent chain using Pattern C (FastAPI backend + `ui/streamlit_app.py` calling the API over `httpx`).

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Standup capture | % of daily entries submitted via the app vs. Slack | Baseline established in first sprint of adoption | Manual tracking initially |
| AI summary quality | Summary generated without error for any valid week range | 100% success rate on non-empty ranges | Bedrock mock must pass in CI |
| API reliability | HTTP 5xx error rate | < 1% under normal load | (Assumption) |
| Test coverage | `pytest` suite passes with no failures | 100% pass rate before handoff | Covers all routes listed in brief |
| Developer onboarding | Time from `git clone` to running app | ≤ 15 minutes following README | `.env.example` copy workflow |
| Pipeline validation | `dev_validate_app` check passes | All checks green before handoff | env example + import + health smoke |

---

## 3. Non-Goals / Out of Scope

- Slack bot or Slack thread ingestion (Phase 2)
- Calendar or sprint-tool (Jira, Linear) integration (Phase 2)
- Team management CRUD (create/update/delete teams) (Phase 2)
- React or any non-Streamlit frontend (Phase 2)
- Auto-post summaries to Confluence or any wiki (Phase 2)
- SSO, OAuth, or JWT-based user authentication (Phase 2)
- Per-user login table or role-based access control beyond the shared API key (Phase 2)
- AWS infrastructure changes or new resource provisioning (read-only in v1)
- Multi-tenant or multi-team isolation at the data layer (Phase 2)
- Mobile-responsive design beyond default Streamlit behaviour (Assumption)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Team Member** (engineer, designer, QA) | Record daily standup without losing context in chat | Opens Streamlit → "Submit Standup" tab → enters name, date, yesterday/today/blockers → submits |
| **Engineering Manager** | Get a weekly digest of team progress and blockers | Opens Streamlit → "Weekly Summary" tab → selects week range → clicks "Generate Summary" → reads Markdown report |
| **Team Member (history review)** | Look up past entries for a given person or date range | Opens Streamlit → "Standup History" tab → filters by team member / date → browses table or cards |
| **Automation / CI Consumer** | Post standups or trigger summaries programmatically | Calls `POST /standups` or `POST /summaries/generate` with `X-API-Key` header; parses JSON response |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Health endpoint** — `GET /health` returns DB connectivity status | P0 | **Given** the API is running and Postgres is reachable, **When** `GET /health` is called without auth, **Then** the response is `200 OK` with a body indicating healthy DB; **Given** Postgres is unreachable, **Then** the response is `503 Service Unavailable`. |
| FR-2 | **Create standup entry** — `POST /standups` inserts a new `standup_entries` row | P0 | **Given** a valid `X-API-Key` header and a request body containing `team_member`, `standup_date`, `yesterday`, `today` (and optional `blockers`), **When** `POST /standups` is called, **Then** the response is `201 Created` with the full entry JSON including a generated UUID and `created_at`; the row is present in the `standup_tracker.standup_entries` table. |
| FR-3 | **List standup entries** — `GET /standups` returns paginated, filterable entries | P0 | **Given** a valid API key, **When** `GET /standups` is called with optional `?team_member=`, `?date_from=`, `?date_to=`, `?limit=`, `?offset=` parameters, **Then** the response is `200 OK` with a JSON object `{items, total, limit, offset}` containing only entries matching the filters; default `limit` is 50 and default `offset` is 0. |
| FR-4 | **Retrieve single standup entry** — `GET /standups/{id}` returns one entry | P1 | **Given** a valid API key and an existing entry UUID, **When** `GET /standups/{id}` is called, **Then** the response is `200 OK` with the entry JSON; **Given** an unknown UUID, **Then** the response is `404 Not Found`. |
| FR-5 | **Delete standup entry** — `DELETE /standups/{id}` hard-deletes the row | P1 | **Given** a valid API key and an existing entry UUID, **When** `DELETE /standups/{id}` is called, **Then** the response is `204 No Content` and the row no longer exists in the database; **Given** an unknown UUID, **Then** the response is `404 Not Found`. |
| FR-6 | **Generate weekly summary** — `POST /summaries/generate` fetches entries in range and calls Bedrock | P0 | **Given** a valid API key and a body with `week_start` and `week_end` dates, **When** `POST /summaries/generate` is called, **Then** (a) all `standup_entries` rows in the date range are fetched; (b) Bedrock Claude Sonnet is called with a system prompt requiring Markdown sections `## Team Summary`, `## Per-Member Updates`, `## Blockers`, `## Key Achievements`; (c) the resulting `summary_markdown` is inserted into `weekly_summaries`; (d) the response is `201 Created` with the full summary JSON; **Given** no entries exist in the range, **Then** the summary contains a `## No Data` section and is still stored and returned as `201`. |
| FR-7 | **List weekly summaries** — `GET /summaries` returns paginated summaries | P1 | **Given** a valid API key, **When** `GET /summaries` is called with optional `?limit=` (default 20), **Then** the response is `200 OK` with `{items, total, limit, offset}` ordered by `week_start DESC`. |
| FR-8 | **Retrieve single summary** — `GET /summaries/{id}` returns one summary | P1 | **Given** a valid API key and an existing summary UUID, **When** `GET /summaries/{id}` is called, **Then** the response is `200 OK` with the summary JSON including `summary_markdown`; **Given** an unknown UUID, **Then** the response is `404 Not Found`. |
| FR-9 | **API key authentication** — all non-health routes require `X-API-Key` | P0 | **Given** a request to any protected route without an `X-API-Key` header (or with a wrong key), **When** the request is processed, **Then** the response is `401 Unauthorized`; **Given** the correct key, **Then** the request proceeds normally. Bedrock never generates or includes secrets in output. |
| FR-10 | **Streamlit UI — Submit Standup tab** | P0 | **Given** the Streamlit app is running on port 8501, **When** a user navigates to the "Submit Standup" tab and fills in `team_member`, `standup_date` (date picker), `yesterday`, `today`, and optionally `blockers` and clicks "Submit", **Then** the app calls `POST /standups` via `httpx`, displays a success message on `201`, and displays a clear error message (including status code and `detail` when present) on `4xx`/`5xx`. |
| FR-11 | **Streamlit UI — Standup History tab** | P1 | **Given** the Streamlit app, **When** a user navigates to "Standup History" and optionally enters a team member name and/or date range, **Then** the app calls `GET /standups` with the corresponding filter parameters and displays results as a table or expandable cards; an empty result set shows a clear "no entries found" message. |
| FR-12 | **Streamlit UI — Weekly Summary tab** | P0 | **Given** the Streamlit app, **When** a user selects `week_start` and `week_end` dates and clicks "Generate Summary", **Then** the app calls `POST /summaries/generate`, renders the returned `summary_markdown` using `st.markdown`, and displays any API error with status + detail; the tab also lists past summaries retrieved from `GET /summaries`. |
| FR-13 | **Startup fail-fast check** | P0 | **Given** the API process starts with `DATABASE_URL` missing or malformed in environment, **When** `app/startup_checks.py` runs, **Then** the process exits with a non-zero code and a human-readable error before accepting requests. |
| FR-14 | **Database seed data** | P1 | **Given** the DDL is applied to the target Postgres schema, **When** the seed script is run, **Then** 5–6 `standup_entries` rows across 2–3 team members for the current week and 1 `weekly_summaries` row for the previous week are present, all with stable UUIDs. |
| FR-15 | **Bedrock prompt contract** | P0 | **Given** Bedrock is called for summary generation, **When** the prompt is built in `app/services/prompts.py`, **Then** the system prompt instructs the model to produce Markdown with exactly the four required sections, to use only the provided standup data (never invent updates), and to never include secrets or credentials in its output. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | `POST /standups` and `GET /standups` p95 latency ≤ 200 ms (excluding Bedrock) | Load test with 10 concurrent users; measure via uvicorn access logs or APM | (Assumption) |
| NFR-2 | Performance | `POST /summaries/generate` end-to-end latency ≤ 30 s (Bedrock-bound) | Measured in integration test with real Bedrock; mocked in unit tests | (Assumption) |
| NFR-3 | Availability | API uptime ≥ 99.5% during business hours | Uptime monitoring on `/health` endpoint | (Assumption) |
| NFR-4 | Security / Auth | All protected routes reject requests without a valid `X-API-Key`; key stored only in `.env` (never committed) | Automated test `test_401_without_api_key`; `.gitignore` includes `.env` | Shared secret only; no JWT in v1 |
| NFR-5 | Security / Secrets | Bedrock-generated Markdown must not contain `API_KEY`, `DATABASE_URL`, or any credential patterns | Regex assertion in QA test on generated summary text | System prompt instructs model; post-generation check recommended |
| NFR-6 | Privacy / Data | No PII beyond free-text `team_member` name entered by the user; no external data export | Code review confirms no third-party analytics SDK; no Slack/Jira calls in v1 | (Assumption) |
| NFR-7 | Scalability | Schema supports up to 10,000 standup entries without query degradation | Index on `(team_member, standup_date DESC)` and `(week_start DESC)` verified in migration DDL; EXPLAIN output reviewed | (Assumption) |
| NFR-8 | Observability | Structured JSON logs for every API request (method, path, status, latency) and every Bedrock invocation (model, input tokens, output tokens, duration) | Log output inspected in local run; log lines parseable by CloudWatch Logs | (Assumption) |
| NFR-9 | Compliance / Data retention | No retention policy enforced in v1; entries persist until manually deleted via `DELETE /standups/{id}` | Confirmed by absence of TTL/cron job; documented in README | Out-of-scope for MVP; revisit Phase 2 |
| NFR-10 | Operability | App starts cleanly from `venv` + `pip install -r requirements.txt` + `.env` copy in ≤ 15 minutes on a new machine following README | Verified by developer walkthrough using README instructions | |
| NFR-11 | Compatibility | Python 3.12; FastAPI with Pydantic v2; SQLAlchemy 2.x sync; `psycopg[binary]`; Streamlit (latest stable); `httpx` for UI→API calls | `pip install` succeeds with pinned `requirements.txt`; `ui/requirements.txt` separate from backend | UI never imports from `app/`; HTTP only |
| NFR-12 | Testability | `pytest` suite runs entirely in-process using SQLite in-memory and a mocked Bedrock client; no external network calls during CI | `pytest` passes with `--no-header -q` in a clean venv; Bedrock mock patched at import site | |

---

## 7. Data & Integrations

### Data Entities

**`standup_tracker.standup_entries`**

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `uuid` | PK |
| `team_member` | `varchar(64)` | NOT NULL |
| `standup_date` | `date` | NOT NULL |
| `yesterday` | `text` | NOT NULL |
| `today` | `text` | NOT NULL |
| `blockers` | `text` | NULLABLE |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

Index: `(team_member, standup_date DESC)`

**`standup_tracker.weekly_summaries`**

| Column | Type | Constraints |
|--------|------|-------------|
| `id` | `uuid` | PK |
| `week_start` | `date` | NOT NULL (Monday) |
| `week_end` | `date` | NOT NULL (Friday) |
| `summary_markdown` | `text` | NOT NULL |
| `generated_at` | `timestamptz` | NOT NULL, DEFAULT `now()` |

Index: `(week_start DESC)`

### External Integrations

| System | Direction | Purpose | Notes |
|--------|-----------|---------|-------|
| **Amazon Bedrock** (Claude Sonnet `us.anthropic.claude-sonnet-4-20250514-v1:0`) | Outbound from API | Generate weekly Markdown summary | Invoked via `app/services/bedrock_client.py`; mocked in tests |
| **PostgreSQL on RDS** | Outbound from API | Persistent storage for entries and summaries | Schema `standup_tracker`; `sslmode=require`; connection string via `DATABASE_URL` env var |
| **Streamlit UI** (`ui/streamlit_app.py`) | Calls API over `httpx` | User-facing interface | Port 8501; never imports `app/` modules directly |

### File Layout

```
target-apps/standup-tracker/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── startup_checks.py
│   ├── health.py
│   ├── routers/
│   │   ├── standups.py
│   │   └── summaries.py
│   └── services/
│       ├── bedrock_client.py
│       └── prompts.py
├── schemas/
│   ├── standups.py
│   └── summaries.py
├── db/
│   └── sql/           ← DDL + seed SQL files
├── ui/
│   ├── streamlit_app.py
│   └── requirements.txt
├── tests/
│   └── conftest.py
├── .env.example
├── requirements.txt
└── README.md
```

---

## 8. Analytics & Observability

**Application Logging**
- Every HTTP request logged at INFO level: method, path, response status, latency (ms).
- Every Bedrock invocation logged: model ID, approximate input/output token counts, wall-clock duration, success/failure.
- Startup check outcomes logged at INFO (pass) or CRITICAL (fail/exit).

**Metrics (Assumption)**
- Request count and error rate by route and status code, derivable from structured logs.
- Bedrock invocation count and latency tracked per summary generation event.

**Health Check**
- `GET /health` performs a live DB ping (e.g., `SELECT 1`) and returns `{"status": "ok", "db": "connected"}` or `{"status": "degraded", "db": "unreachable"}` with appropriate HTTP status.

**Alerts (Assumption)**
- CloudWatch Log Insights query on `status >= 500` rate > 1% over 5-minute window → alert to on-call.
- Bedrock invocation failures (3 consecutive) → alert.

**Test Observability**
- `pytest` output captured to stdout; CI runner reports pass/fail per test function with names matching route and scenario.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bedrock API unavailable or rate-limited during summary generation | Users cannot generate weekly summaries; `POST /summaries/generate` returns 5xx | Return descriptive error to UI; implement retry with exponential back-off (max 3 attempts) in `bedrock_client.py`; document manual retry in README |
| RDS connectivity lost (network / credentials) | All API routes (except `/health`) fail; 503 responses | `startup_checks.py` fail-fast prevents silent failures; `/health` surfaces DB status; connection pool auto-reconnect via SQLAlchemy |
| `DATABASE_URL` or `API_KEY` accidentally committed to source control | Secret exposure | `.env` in `.gitignore`; `.env.example` contains placeholder values only; CI lint check for secrets (Assumption) |
| Bedrock-generated summary accidentally echoes injected prompt content containing secrets | Secret leakage in stored Markdown | System prompt explicitly prohibits repeating secrets; post-generation regex check before INSERT (Assumption) |
| Free-text `team_member` field causes duplicate identity (e.g., "alice" vs "Alice") | Fragmented history views; inaccurate summaries | Document naming convention in README; consider normalisation (lowercasing) in router before INSERT (Assumption) |
| SQLite ↔ Postgres dialect differences break tests | Tests pass in CI but fail on real Postgres | Review SQLAlchemy queries for Postgres-specific types (UUID, timestamptz); run smoke test against real RDS before handoff |
| Streamlit session state lost on page refresh | User loses unsaved form data | Acceptable for MVP; state is ephemeral by design; submitted entries are persisted in DB immediately on submit |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the data retention policy for standup entries? Should entries older than N days be automatically archived or deleted? | Engineering Manager / Product |
| 2 | Should `team_member` names be normalised (e.g., lowercased or validated against a fixed list) to prevent fragmentation? | Developer agent |
| 3 | Is a single shared `API_KEY` sufficient long-term, or will per-consumer keys be needed before Phase 2? | Security / Product |
| 4 | What CloudWatch log group and retention period should structured logs be shipped to on RDS? | Infrastructure / DevOps |
| 5 | Should `POST /summaries/generate` be idempotent for the same `week_start`/`week_end` pair (upsert vs. always insert a new row)? | Product / Architect |
| 6 | What is the expected maximum number of team members and entries per week (for capacity planning)? | Engineering Manager |
| 7 | Should `DELETE /standups/{id}` be restricted to a specific role or remain open to all API-key holders in v1? | Product / Security |
| 8 | Is there a requirement to export summaries as PDF or email them to stakeholders, or is Streamlit display sufficient for MVP? | Product |
| 9 | What Bedrock IAM role / instance profile is pre-configured on the execution environment? (Read-only infra constraint means this must already exist.) | DevOps / Infrastructure |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** (`ui/streamlit_app.py`) | Three tabs: Submit Standup, Standup History, Weekly Summary. All API calls via `httpx`; never imports from `app/`. |
| API | **FastAPI** under `target-apps/standup-tracker/` | REST + OpenAPI (auto-generated Swagger at `/docs`); uvicorn on port 8000. |
| UI location | `ui/streamlit_app.py` + `ui/requirements.txt` | Streamlit on port 8501; reads `API_BASE_URL` and `API_KEY` from `.env` via `python-dotenv`. |
| Auth for UI | Shared `X-API-Key` header (same as API) | Streamlit reads `API_KEY` from environment / session state; passes as header on every `httpx` call. |
| API auth | `X-API-Key` header validated in FastAPI dependency | Key loaded from `API_KEY` env var via `app/config.py`; missing/wrong key → `401`. |
| Backend entry point | `uvicorn app.main:app --reload --port 8000` | `app/startup_checks.py` runs at startup; aborts if `DATABASE_URL` missing or malformed. |
| UI entry point | `streamlit run ui/streamlit_app.py --server.port 8501` | Separate terminal / process from API. |
| Database schema | `POSTGRES_SCHEMA=standup_tracker` | DDL files in `db/sql/`; applied manually to RDS before first run. |
| Environment config | `.env.example` → `.env` copy workflow | Every variable on its own `KEY=value` line; includes `DATABASE_URL=postgresql+psycopg://...?sslmode=require`, `API_KEY=`, `AWS_REGION=`, `BEDROCK_MODEL_ID=`. |
| Testing | `pytest` + `TestClient`; SQLite in-memory; Bedrock mocked at import site | `tests/conftest.py` from golden template; `dev_validate_app` smoke check must pass before handoff. |

---

## Appendix: Assumptions

- The shared `API_KEY` is a static secret rotated manually; no automated key rotation is in scope for v1.
- The RDS instance, VPC, security groups, and Bedrock IAM permissions are pre-provisioned and accessible from the developer's environment; no infrastructure changes are required.
- `POSTGRES_SCHEMA=standup_tracker` is used as the search path; the schema must be created (`CREATE SCHEMA IF NOT EXISTS standup_tracker`) before DDL is applied.
- `week_start` is always a Monday and `week_end` is always the following Friday; no validation of day-of-week is enforced by the API in v1 (caller's responsibility).
- The Bedrock model `us.anthropic.claude-sonnet-4-20250514-v1:0` is available in the target AWS region and the execution environment has the necessary `bedrock:InvokeModel` permission.
- Streamlit is deployed locally or on a single internal server; no public-facing deployment, load balancer, or HTTPS termination is in scope for v1.
- UI error handling covers `401` (bad/missing API key) and `5xx` (server errors) with a user-readable message including HTTP status and `detail` field when present; other status codes show a generic error.
- `team_member` is a free-text string with a max length of 64 characters; no authoritative user list exists in v1.
- Seed data UUIDs are hard-coded (stable) in the seed SQL file to ensure reproducibility across environments.
- p95 API latency target of 200 ms applies to database-bound routes on a properly sized RDS instance; no performance testing harness is explicitly required for MVP.
- Structured logging uses Python's `logging` module with a JSON formatter; no dedicated log aggregation pipeline is set up in v1 beyond what CloudWatch provides natively on the host.
- Post-generation secret-scrubbing regex is a best-effort check in the router before INSERT; it is not a hard security guarantee.
- `team_member` name normalisation (lowercasing) may be applied in the router at the developer agent's discretion to reduce fragmentation; final decision deferred to Open Question 2.
- `POST /summaries/generate` always inserts a new row (no upsert); duplicate summaries for the same week are possible until addressed in Phase 2 (see Open Question 5).
- No email, notification, or webhook is triggered on summary generation in v1.
