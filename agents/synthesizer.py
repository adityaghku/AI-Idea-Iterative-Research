"""Synthesizer agent - converts signals to app ideas."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db import Idea, Signal
from utils.llm_client import async_llm_complete_json
from utils.logger import get_logger
from utils.prompts_utils import load_prompt

logger = get_logger(__name__)


class SynthesizerAgent:
    """Agent 2: Converts signals to app ideas."""

    async def run(self, session: AsyncSession, signals: list[Signal]) -> list[Idea]:
        """Run synthesizer to convert signals to ideas."""
        prompt_template = load_prompt("synthesizer.md")
        logger.info("Synthesizer starting with %d input signals", len(signals))

        signal_texts = []
        for idx, s in enumerate(signals):
            source = f" ({s.source_url})" if s.source_url else ""
            signal_texts.append(f"{idx}. [{s.signal_type}] {s.content}{source}")

        signals_str = "\n".join(signal_texts)

        prompt = f"""{prompt_template}

Signals:
{signals_str}
"""
        logger.info("Converting %d signals to ideas...", len(signals))
        result = await async_llm_complete_json(prompt, max_tokens=3000, temperature=0.5)

        ideas_data = result if isinstance(result, list) else result.get("ideas", [])
        logger.info("Generated %d ideas", len(ideas_data))

        ideas = []
        for idx, idea_data in enumerate(ideas_data, start=1):
            raw_indices = idea_data.get("supporting_signal_indices", [])
            supporting_indices = [
                int(i)
                for i in raw_indices
                if isinstance(i, int) and 0 <= i < len(signals)
            ]
            if not supporting_indices:
                supporting_indices = [0] if signals else []

            idea = Idea(
                title=idea_data.get("title", "Untitled"),
                problem=idea_data.get("problem", ""),
                target_user=idea_data.get("target_user", ""),
                solution=idea_data.get("solution", ""),
                status="new",
            )
            idea.signals = [signals[i] for i in sorted(set(supporting_indices))]
            session.add(idea)
            ideas.append(idea)
            logger.info(
                "Synthesizer created idea %d/%d: %s (supports %d signal(s))",
                idx,
                len(ideas_data),
                idea.title,
                len(idea.signals),
            )

        await session.commit()
        logger.info("Synthesizer commit complete: %d ideas persisted", len(ideas))
        return ideas
