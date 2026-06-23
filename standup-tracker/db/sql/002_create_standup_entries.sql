-- =============================================================
-- 002_create_standup_entries.sql
-- Creates standup_tracker.standup_entries table + index.
-- Idempotent: IF NOT EXISTS guards on table and index.
-- =============================================================

SET search_path TO standup_tracker, public;

CREATE TABLE IF NOT EXISTS standup_tracker.standup_entries (
    id           UUID        NOT NULL DEFAULT gen_random_uuid(),
    team_member  VARCHAR(64) NOT NULL,
    standup_date DATE        NOT NULL,
    yesterday    TEXT        NOT NULL,
    today        TEXT        NOT NULL,
    blockers     TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT pk_standup_entries PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_entries_member_date
    ON standup_tracker.standup_entries (team_member, standup_date DESC);
