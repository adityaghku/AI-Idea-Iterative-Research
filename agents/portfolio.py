"""Portfolio agent - distills recurring human rejection patterns into guidance."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import FeedbackEvent, Idea, PortfolioMemory
from utils.logger import get_logger

logger = get_logger(__name__)


def summarize_crossout_feedback(
    feedback: Iterable[dict], min_count: int = 2, max_examples: int = 2
) -> dict:
    """Keep only recurring crossed-out reason patterns for learning."""
    examples_by_code: dict[str, list[str]] = defaultdict(list)
    counts: Counter[str] = Counter()
    for item in feedback:
        if item.get("reason_code") in (None, ""):
            continue
        code = str(item["reason_code"]).strip()
        if not code:
            continue
        counts[code] += 1
        reason_text = str(item.get("reason_text") or "").strip()
        if reason_text and len(examples_by_code[code]) < max_examples:
            examples_by_code[code].append(reason_text)

    recurring_patterns: list[dict] = []
    for code, count in counts.most_common():
        if count < min_count:
            continue
        recurring_patterns.append(
            {
                "reason_code": code,
                "count": count,
                "examples": examples_by_code.get(code, []),
            }
        )
    return {"recurring_patterns": recurring_patterns}


def select_active_crossout_feedback(feedback: Iterable[dict]) -> list[dict]:
    """Use only the latest crossed-out feedback per idea that is still crossed out."""
    latest_by_idea: dict[int, dict] = {}
    for item in feedback:
        if not item.get("is_crossed_out"):
            continue
        idea_id = item.get("idea_id")
        if not isinstance(idea_id, int):
            continue
        previous = latest_by_idea.get(idea_id)
        if previous is None or item.get("created_at", 0) > previous.get("created_at", 0):
            latest_by_idea[idea_id] = item
    return list(latest_by_idea.values())


class PortfolioAgent:
    """Summarize negative feedback into compact, reusable guidance."""

    def __init__(self, min_recurring_count: int = 2):
        self.min_recurring_count = min_recurring_count

    async def run(
        self, session: AsyncSession, pipeline_run_id: int | None = None
    ) -> PortfolioMemory:
        rows = (
            await session.execute(
                select(FeedbackEvent, Idea)
                .join(Idea, FeedbackEvent.idea_id == Idea.id)
                .where(FeedbackEvent.event_type == "crossed_out")
            )
        ).all()
        feedback = select_active_crossout_feedback(
            [
                {
                    "idea_id": event.idea_id,
                    "reason_code": event.reason_code,
                    "reason_text": event.reason_text,
                    "created_at": event.created_at.timestamp(),
                    "is_crossed_out": bool(idea.is_crossed_out),
                }
                for event, idea in rows
            ]
        )
        summary = summarize_crossout_feedback(
            feedback,
            min_count=self.min_recurring_count,
        )
        scout_guidance = self._guidance_text(summary["recurring_patterns"])
        memory = PortfolioMemory(
            pipeline_run_id=pipeline_run_id,
            recurring_patterns=summary["recurring_patterns"],
            scout_guidance=scout_guidance,
            synthesizer_guidance=scout_guidance,
            analyser_guidance=scout_guidance,
            summary=scout_guidance,
        )
        session.add(memory)
        await session.commit()
        logger.info(
            "Portfolio guidance updated with %d recurring rejection pattern(s)",
            len(summary["recurring_patterns"]),
        )
        return memory

    def _guidance_text(self, patterns: list[dict]) -> str:
        if not patterns:
            return "No recurring crossed-out rationale yet."
        lines = ["Avoid recurring rejection patterns:"]
        for pattern in patterns:
            lines.append(f"- {pattern['reason_code']} ({pattern['count']}x)")
        return "\n".join(lines)
