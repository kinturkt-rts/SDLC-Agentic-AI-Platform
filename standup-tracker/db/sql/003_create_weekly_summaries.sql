-- =============================================================
-- 003_create_weekly_summaries.sql
-- Creates standup_tracker.weekly_summaries table + index.
-- Idempotent: IF NOT EXISTS guards on table and index.
-- =============================================================

SET search_path TO standup_tracker, public;

CREATE TABLE IF NOT EXISTS standup_tracker.weekly_summaries (
    id               UUID        NOT NULL DEFAULT gen_random_uuid(),
    week_start       DATE        NOT NULL,
    week_end         DATE        NOT NULL,
    summary_markdown TEXT        NOT NULL,
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_weekly_summaries PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_summaries_week_start
    ON standup_tracker.weekly_summaries (week_start DESC);
