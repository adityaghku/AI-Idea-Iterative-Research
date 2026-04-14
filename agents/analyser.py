"""Analyser agent - scores and analyzes ideas."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db import Analysis, Idea
from utils.idea_context import format_business_context
from utils.llm_client import async_llm_complete_json
from utils.logger import get_logger
from utils.prompts_utils import load_prompt

logger = get_logger(__name__)


class AnalyserAgent:
    """Agent 3: Scores ideas with monetization, complexity, tags, assumptions."""

    def __init__(self, portfolio_guidance: str | None = None):
        self.portfolio_guidance = (portfolio_guidance or "").strip()

    @staticmethod
    def _score_value(subscores: dict, key: str) -> int | None:
        value = subscores.get(key)
        if isinstance(value, (int, float)):
            return int(value)
        return None

    async def run(self, session: AsyncSession, ideas: list[Idea]) -> list[Analysis]:
        """Run analyser to score ideas."""
        prompt_template = load_prompt("analyser.md")
        logger.info("Analyser starting for %d ideas", len(ideas))

        analyses = []
        for idx, idea in enumerate(ideas, start=1):
            business_context = format_business_context(idea)
            idea_text = f"""Title: {idea.title}
Problem: {idea.problem}
Target User: {idea.target_user}
Solution: {idea.solution}"""
            if business_context:
                idea_text += f"\n{business_context}"

            guidance_section = ""
            if self.portfolio_guidance:
                guidance_section = f"""

## Portfolio Guidance
{self.portfolio_guidance}
"""

            prompt = f"""{prompt_template}{guidance_section}

Idea:
{idea_text}
"""
            logger.info("Analyser processing idea %d/%d: %s", idx, len(ideas), idea.title)
            result = await async_llm_complete_json(
                prompt, max_tokens=2000, temperature=0.3
            )

            analysis_data = result if isinstance(result, dict) else {}
            subscores = analysis_data.get("subscores", {})
            if not isinstance(subscores, dict):
                subscores = {}

            analysis = Analysis(
                idea_id=idea.id,
                score=analysis_data.get("score", 50),
                demand_score=self._score_value(subscores, "demand"),
                gtm_score=self._score_value(subscores, "gtm"),
                build_risk_score=self._score_value(subscores, "build_risk"),
                retention_score=self._score_value(subscores, "retention"),
                monetization_score=self._score_value(subscores, "monetization"),
                validation_score=self._score_value(subscores, "validation"),
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
