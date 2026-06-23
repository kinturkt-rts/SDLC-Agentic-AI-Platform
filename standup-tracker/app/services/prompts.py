"""Bedrock prompt builder for weekly standup summaries."""
from __future__ import annotations

SYSTEM_PROMPT = """You are a technical project manager assistant that creates concise weekly
standup summaries for engineering teams.

When given standup data, produce a Markdown report with EXACTLY these four sections:
## Team Summary
## Per-Member Updates
## Blockers
## Key Achievements

Rules:
- Use ONLY the standup data provided. Never invent, fabricate, or add updates.
- Do NOT include or repeat any API keys, DATABASE_URL, passwords, tokens, or credentials.
- Keep the tone professional and concise.
- Under ## Per-Member Updates, group entries by team member with bold name heading.
- Under ## Blockers, list all blockers; if none, write "None reported."
- Under ## Key Achievements, highlight significant completions from the week.
- If no entries are provided, output a single section ## No Data with a note that
  no standup entries were found for this date range."""


def build_summary_prompt(
    week_start: str,
    week_end: str,
    entries: list[dict],
) -> str:
    """Build the user message for Claude summarising the given standup entries."""
    if not entries:
        return (
            f"No standup entries were recorded for the week of {week_start} to {week_end}."
            " Please produce a summary with a ## No Data section noting this."
        )

    lines: list[str] = [
        f"Weekly Standup Report: {week_start} to {week_end}",
        "",
        f"Total entries: {len(entries)}",
        "",
    ]
    for e in entries:
        lines.append(f"--- {e['team_member']} ({e['standup_date']}) ---")
        lines.append(f"Yesterday: {e['yesterday']}")
        lines.append(f"Today: {e['today']}")
        blockers = e.get("blockers") or "None"
        lines.append(f"Blockers: {blockers}")
        lines.append("")

    lines.append("Please produce the Markdown summary now.")
    return "\n".join(lines)
