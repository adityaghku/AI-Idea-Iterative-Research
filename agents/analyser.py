"""Analyser agent - scores and analyzes ideas."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db import Analysis, Idea
from utils.llm_client import async_llm_complete_json
from utils.logger import get_logger
from utils.prompts_utils import load_prompt

logger = get_logger(__name__)


class AnalyserAgent:
    """Agent 3: Scores ideas with monetization, complexity, tags, assumptions."""

    async def run(self, session: AsyncSession, ideas: list[Idea]) -> list[Analysis]:
        """Run analyser to score ideas."""
        prompt_template = load_prompt("analyser.md")
        logger.info("Analyser starting for %d ideas", len(ideas))

        analyses = []
        for idx, idea in enumerate(ideas, start=1):
            idea_text = f"""Title: {idea.title}
Problem: {idea.problem}
Target User: {idea.target_user}
Solution: {idea.solution}"""

            prompt = f"""{prompt_template}

Idea:
{idea_text}
"""
            logger.info("Analyser processing idea %d/%d: %s", idx, len(ideas), idea.title)
            result = await async_llm_complete_json(
                prompt, max_tokens=2000, temperature=0.3
            )

            analysis_data = result if isinstance(result, dict) else {}

            analysis = Analysis(
                idea_id=idea.id,
                score=analysis_data.get("score", 50),
                monetization_potential=analysis_data.get(
                    "monetization_potential", "unknown"
                ),
                complexity=analysis_data.get("complexity", "medium"),
                tags=analysis_data.get("tags", []),
                assumptions=analysis_data.get("assumptions", []),
                comments=analysis_data.get("comments"),
            )
            session.add(analysis)
            analyses.append(analysis)

            idea.status = "analysed"
            logger.info(
                "Analyser result for '%s': score=%s, monetization=%s, complexity=%s",
                idea.title,
                analysis.score,
                analysis.monetization_potential,
                analysis.complexity,
            )

        await session.commit()
        logger.info("Completed %d analyses", len(analyses))
        return analyses
