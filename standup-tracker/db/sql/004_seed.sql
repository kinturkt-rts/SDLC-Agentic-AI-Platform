-- =============================================================
-- 004_seed.sql
-- Dev / test fixture rows for standup_tracker schema.
-- Design §6.2 / FR-14: 5-6 standup_entries (Alice, Bob, Carol)
-- for current week + 1 weekly_summaries row for previous week.
-- Stable UUIDs for reproducibility across environments.
-- ON CONFLICT DO NOTHING makes this idempotent.
-- =============================================================

SET search_path TO standup_tracker, public;

-- -------------------------------------------------------
-- standup_entries  (6 rows across 3 team members)
-- UUIDs are stable and hard-coded per design §6.2 / FR-14
-- Dates use CURRENT_DATE offsets so rows stay "this week"
-- -------------------------------------------------------
INSERT INTO standup_tracker.standup_entries
    (id, team_member, standup_date, yesterday, today, blockers, created_at)
VALUES
    -- Alice — Monday this week
    (
        'a1111111-0001-4000-8000-000000000001',
        'Alice',
        date_trunc('week', CURRENT_DATE)::date,
        'Completed the FastAPI router scaffolding and wrote unit tests for POST /standups.',
        'Integrate SQLAlchemy models with the standup_entries table and add pagination support.',
        NULL,
        now() - INTERVAL '4 days'
    ),
    -- Alice — Tuesday this week
    (
        'a1111111-0002-4000-8000-000000000002',
        'Alice',
        (date_trunc('week', CURRENT_DATE) + INTERVAL '1 day')::date,
        'Added pagination support to GET /standups; reviewed PR from Bob.',
        'Work on Bedrock prompt builder and wire up POST /summaries/generate route.',
        'Waiting for Bedrock IAM role ARN from DevOps before end-to-end test.',
        now() - INTERVAL '3 days'
    ),
    -- Bob — Monday this week
    (
        'b2222222-0001-4000-8000-000000000003',
        'Bob',
        date_trunc('week', CURRENT_DATE)::date,
        'Set up Streamlit UI skeleton with three tabs and httpx client helper.',
        'Build out the Submit Standup form and wire POST /standups call with error handling.',
        NULL,
        now() - INTERVAL '4 days'
    ),
    -- Bob — Tuesday this week
    (
        'b2222222-0002-4000-8000-000000000004',
        'Bob',
        (date_trunc('week', CURRENT_DATE) + INTERVAL '1 day')::date,
        'Completed Submit Standup tab; added inline validation for required fields.',
        'Build Standup History tab with date-range filter and expandable entry cards.',
        'Streamlit date_input widget behaves unexpectedly with None default — investigating.',
        now() - INTERVAL '3 days'
    ),
    -- Carol — Monday this week
    (
        'c3333333-0001-4000-8000-000000000005',
        'Carol',
        date_trunc('week', CURRENT_DATE)::date,
        'Wrote pytest suite for health endpoint and standup CRUD routes using SQLite in-memory.',
        'Add Bedrock mock and write tests for POST /summaries/generate happy and empty-range paths.',
        NULL,
        now() - INTERVAL '4 days'
    ),
    -- Carol — Tuesday this week
    (
        'c3333333-0002-4000-8000-000000000006',
        'Carol',
        (date_trunc('week', CURRENT_DATE) + INTERVAL '1 day')::date,
        'Finished Bedrock mock; all 12 unit tests passing in CI.',
        'Write integration smoke test against real RDS; update conftest with stable seed UUIDs.',
        'Need RDS security-group inbound rule opened for CI runner IP.',
        now() - INTERVAL '3 days'
    )
ON CONFLICT (id) DO NOTHING;

-- -------------------------------------------------------
-- weekly_summaries  (1 row for previous week)
-- week_start = last Monday, week_end = last Friday
-- -------------------------------------------------------
INSERT INTO standup_tracker.weekly_summaries
    (id, week_start, week_end, summary_markdown, generated_at)
VALUES
    (
        'd4444444-0001-4000-8000-000000000007',
        (date_trunc('week', CURRENT_DATE) - INTERVAL '7 days')::date,
        (date_trunc('week', CURRENT_DATE) - INTERVAL '3 days')::date,
        E'## Team Summary\n\nThe team completed API scaffolding, Streamlit UI skeleton, and the initial test suite during the week. All P0 routes are functional and passing unit tests.\n\n## Per-Member Updates\n\n**Alice** — Delivered FastAPI router, SQLAlchemy integration, and pagination for GET /standups. Started Bedrock prompt builder.\n\n**Bob** — Shipped Streamlit UI with Submit Standup and Standup History tabs; resolved date-picker edge case.\n\n**Carol** — Established pytest suite with SQLite in-memory fixtures; Bedrock mock fully operational.\n\n## Blockers\n\n- Bedrock IAM role ARN pending from DevOps (Alice).\n- RDS security-group inbound rule needed for CI runner IP (Carol).\n\n## Key Achievements\n\n- FastAPI + SQLAlchemy stack end-to-end validated against local Postgres.\n- Streamlit UI communicating with API exclusively over httpx (no direct DB imports).\n- 12 unit tests passing in CI with zero external network calls.',
        now() - INTERVAL '2 days'
    )
ON CONFLICT (id) DO NOTHING;
