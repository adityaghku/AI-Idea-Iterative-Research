"""Critic agent - adversarial vetting of ideas."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db import Critique, Idea
from utils.agent_validators import validate_critic_output
from utils.idea_context import format_business_context
from utils.llm_client import async_llm_complete_json
from utils.logger import get_logger
from utils.prompts_utils import load_prompt

logger = get_logger(__name__)


class CriticAgent:
    """Agent 5: Criticizes enriched ideas on saturation, distribution, technical issues."""

    async def run(self, session: AsyncSession, ideas: list[Idea]) -> list[Critique]:
        """Run critic to vet ideas."""
        prompt_template = load_prompt("critic.md")
        logger.info("Critic starting for %d ideas", len(ideas))

        critiques = []
        for idx, idea in enumerate(ideas, start=1):
            enrichment = idea.enrichment
            business_context = format_business_context(idea)
            competitors = getattr(enrichment, "competitor_details", None) if enrichment else None
            evidence = getattr(enrichment, "evidence_snippets", None) if enrichment else None
            risks = getattr(enrichment, "risks", None) if enrichment else None
            gtm = getattr(enrichment, "go_to_market_hypotheses", None) if enrichment else None
            idea_text = f"""Title: {idea.title}
Problem: {idea.problem}
Target User: {idea.target_user}
Solution: {idea.solution}
Competitors: {(competitors or [])[:3]}
Monetization Strategies: {getattr(enrichment, 'monetization_strategies', None) if enrichment else 'N/A'}
Evidence Snippets: {(evidence or [])[:4]}
Risks: {(risks or [])[:4]}
Go-to-Market Hypotheses: {(gtm or [])[:3]}
Enrichment Notes: {enrichment.additional_notes if enrichment else 'N/A'}"""
            if business_context:
                idea_text += f"\n{business_context}"

            prompt = f"""{prompt_template}

Idea:
{idea_text}
"""
            logger.info("Critic processing idea %d/%d: %s", idx, len(ideas), idea.title)
            result = await async_llm_complete_json(
                prompt,
                max_tokens=1700,
                temperature=0.25,
                agent_name="critic",
                validator=validate_critic_output,
                tool_policy="no_tools",
            )

            critique_data = result if isinstance(result, dict) else {}

            critique = Critique(
                idea_id=idea.id,
                saturation_issues=critique_data.get("saturation_issues", []),
                distribution_blockers=critique_data.get("distribution_blockers", []),
                technical_blockers=critique_data.get("technical_blockers", []),
                monetization_blockers=critique_data.get("monetization_blockers", []),
                validation_blockers=critique_data.get("validation_blockers", []),
                additional_concerns=critique_data.get("additional_concerns"),
            )
            session.add(critique)
            critiques.append(critique)

            idea.status = "critiqued"
            logger.info(
                "Critic result for '%s': saturation=%d, distribution=%d, technical=%d",
                idea.title,
                len(critique.saturation_issues or []),
                len(critique.distribution_blockers or []),
                len(critique.technical_blockers or []),
            )

        await session.commit()
        logger.info("Completed %d critiques", len(critiques))
        return critiques
