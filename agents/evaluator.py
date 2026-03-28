"""Evaluator agent - scores ideas using learned criteria from internet research."""
from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, cast

from .config import (
    EvaluatorInput,
    EvaluatorOutput,
    Idea,
    IdeaScore,
    DEFAULT_DB_PATH,
)
from .utils import get_knowledge
from .meta_learning import MetaLearningAgent
from .llm_client import async_llm_complete_json
from .logger import get_logger, log_structured
from .filter import ContentFilter
from .cache import ResponseCache


class EvaluatorAgent:
    """Scores ideas using dynamically learned criteria about startup success."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH, max_concurrent: int = 1):
        self.db_path = db_path
        self.meta_learning = MetaLearningAgent(db_path=db_path)
        self.logger = get_logger()
        self._semaphore = asyncio.Semaphore(max_concurrent)
    
    async def evaluate(self, input_data: EvaluatorInput) -> EvaluatorOutput:
        """Evaluate extracted content and score ideas using learned criteria."""
        self.logger.info(f"[iter {input_data.iteration_number}] Evaluator starting: {len(input_data.extracted_content)} content items")

        # Get learned evaluation criteria
        evaluation_criteria = self.meta_learning.research_startup_criteria(
            input_data.run_task_id
        )

        all_ideas = []

        async def extract_with_semaphore(content_item: dict[str, Any]) -> list[Idea]:
            async with self._semaphore:
                return await self._extract_ideas(content_item, input_data.run_task_id, evaluation_criteria, input_data.iteration_number)

        tasks = [extract_with_semaphore(item) for item in input_data.extracted_content]
        results = await asyncio.gather(*tasks)
        
        for result in results:
            all_ideas.extend(cast(list[Idea], result))
        
        # Filter to top ideas (avoid overwhelming)
        top_ideas = all_ideas[:15]  # Max 15 ideas per iteration
        
        # Update criteria based on which ideas scored well
        high_scoring = [i for i in top_ideas if i.score >= 75]
        low_scoring = [i for i in top_ideas if i.score < 60]
        self.meta_learning.update_criteria_from_results(
            input_data.run_task_id,
            [i.to_dict() for i in high_scoring],
            [i.to_dict() for i in low_scoring],
        )
        
        summary = f"Evaluated {len(input_data.extracted_content)} sources, extracted {len(all_ideas)} ideas, selected top {len(top_ideas)}"
        self.logger.info(f"[iter {input_data.iteration_number}] Evaluator complete: {len(top_ideas)} ideas")

        return EvaluatorOutput(
            ideas=top_ideas,
            iteration_summary=summary,
        )
    
    async def _extract_ideas(
        self,
        content_item: dict[str, Any],
        run_task_id: str,
        evaluation_criteria: dict[str, Any],
        iteration_number: int = 0,
    ) -> list[Idea]:
        """Extract and score ideas from content using learned criteria."""
        
        content = content_item.get("content", {})
        url = content_item.get("url", "")
        
        text = content.get("text", "")
        if not text:
            return []
        
        is_worthy, reason = ContentFilter.is_content_worthy(text, url)
        if not is_worthy:
            self.logger.info(f"Filtered content from {url}: {reason}")
            log_structured("content_filtered", url=url, reason=reason, iteration=iteration_number)
            return []
        
        return await self._llm_extract_ideas_with_criteria(
            text, url, run_task_id, evaluation_criteria
        )
    
    async def _llm_extract_ideas_with_criteria(
        self,
        text: str,
        url: str,
        run_task_id: str,
        evaluation_criteria: dict[str, Any],
    ) -> list[Idea]:
        """Use LLM with learned criteria to extract and score ideas."""

        content_hash = ResponseCache.content_hash(text)
        cache = ResponseCache.get_instance()
        
        is_hit, cached_ideas = cache.get(content_hash)
        if is_hit:
            self.logger.info(f"Cache hit for {url[:80]}...")
            return cached_ideas
        
        self.logger.info(f"Cache miss for {url[:80]}...")

        # Build criteria context
        criteria_context = self._build_criteria_prompt(evaluation_criteria)

        prompt = f"""You are an expert startup evaluator with deep knowledge of what makes AI startups succeed or fail.

{criteria_context}

Analyze this text and extract 1-3 innovative AI app/product ideas:

TEXT:
{text[:3000]}

For each idea, evaluate using the learned criteria above and provide:

1. **Title** (short, catchy)
2. **Summary** (1-2 sentences describing the product)
3. **Detailed Scores (0-100)** based on learned success factors:
   - problem_clarity: How clear and painful is the problem?
   - ai_advantage: Does this genuinely need AI or is it AI-for-AI's-sake?
   - market_timing: Is now the right time for this?
   - solo_founder_feasibility: Can one person build and launch this?
   - distribution_path: Is there a clear way to reach customers?
   - monetization_clarity: Will people pay for this?
   - defensibility: Can this have sustainable competitive advantage?
   - technical_feasibility: Can this be built with today's AI?

4. **Overall Assessment**:
   - Total Score (weighted average of above)
   - Verdict: "Exceptional", "Strong", "Promising", "Marginal", or "Weak"
   - Key strengths (2-3 points)
   - Key risks/concerns (2-3 points)
   - Specific advice for improvement

5. **Red Flags Check**: Does this idea exhibit any of the failure patterns mentioned above?

IMPORTANT: Think out loud before assigning scores. Show your reasoning process.

Output as JSON array:
[
  {{
    "thinking": "Your step-by-step reasoning about this idea's strengths, weaknesses, and why you're assigning these specific scores...",
    "idea_title": "...",
    "idea_summary": "...",
    "detailed_scores": {{
      "problem_clarity": 85,
      "ai_advantage": 90,
      "market_timing": 75,
      "solo_founder_feasibility": 80,
      "distribution_path": 70,
      "monetization_clarity": 85,
      "defensibility": 65,
      "technical_feasibility": 90
    }},
    "total_score": 82,
    "verdict": "Strong",
    "strengths": ["...", "..."],
    "risks": ["...", "..."],
    "advice": "...",
    "red_flags": ["..."],
    "citations": ["Specific URL or text evidence from source", "Another piece of evidence"]
  }}
]

CRITICAL REQUIREMENTS:
- You MUST provide citations (specific URLs or quoted text evidence from the source material) for any score above 70.
- Without citations, high scores will be capped at 70.
- Be critical and honest. Most ideas should score 40-70. Only truly exceptional opportunities should score 80+.
- Only output valid JSON, no markdown."""

        ideas_data = await async_llm_complete_json(
            prompt=prompt,
            max_tokens=3000,
            temperature=0.4,
        )

        if not isinstance(ideas_data, list):
            self.logger.warning(f"LLM returned non-list response type: {type(ideas_data).__name__}, expected list of ideas")
            ideas_data = []

        ideas = []
        for idea_data in ideas_data:
            # Extract detailed scores
            detailed = idea_data.get("detailed_scores", {})
            
            # Map to traditional score breakdown for compatibility
            # Use None if scores missing - don't silently default to middle values
            novelty = detailed.get("ai_advantage")
            feasibility = detailed.get("solo_founder_feasibility")
            market_potential = detailed.get("monetization_clarity")
            
            if novelty is None or feasibility is None or market_potential is None:
                missing = []
                if novelty is None:
                    missing.append("ai_advantage")
                if feasibility is None:
                    missing.append("solo_founder_feasibility")
                if market_potential is None:
                    missing.append("monetization_clarity")
                self.logger.warning(f"Missing evaluation scores for idea: {missing}")
            
            score_breakdown = IdeaScore(
                novelty=novelty if novelty is not None else 0,  # Novelty = AI advantage
                feasibility=feasibility if feasibility is not None else 0,  # Feasibility = solo founder feasibility
                market_potential=market_potential if market_potential is not None else 0,  # Market = monetization
            )
            
            # Use total score if provided, otherwise calculate
            total_score = idea_data.get("total_score", score_breakdown.total())
            
            thinking = idea_data.get("thinking", "")
            citations = idea_data.get("citations", [])
            
            # Cap scores > 70 if no citations provided
            if total_score > 70 and not citations:
                self.logger.warning(f"Score capped to 70 for '{idea_data.get('idea_title', 'Untitled')}' - no citations provided")
                total_score = 70
            
            # Build rich explanation
            explanation_parts = [
                f"Verdict: {idea_data.get('verdict', 'N/A')}",
                "",
                "Strengths:",
            ]
            explanation_parts.extend([f"  + {s}" for s in idea_data.get("strengths", [])])
            explanation_parts.extend([
                "",
                "Risks:",
            ])
            explanation_parts.extend([f"  - {r}" for r in idea_data.get("risks", [])])
            explanation_parts.extend([
                "",
                f"Advice: {idea_data.get('advice', 'N/A')}",
            ])
            
            if idea_data.get("red_flags"):
                explanation_parts.extend([
                    "",
                    "Red Flags Detected:",
                ])
                explanation_parts.extend([f"  - {rf}" for rf in idea_data.get("red_flags", [])])
            
            idea = Idea(
                thinking=thinking,
                idea_title=idea_data.get("idea_title", "Untitled"),
                idea_summary=idea_data.get("idea_summary", ""),
                source_urls=[url],
                score=int(total_score),
                score_breakdown=score_breakdown,
                evaluator_explain="\n".join(explanation_parts),
                citations=citations,
                idea_payload={
                    "detailed_scores": detailed,
                    "verdict": idea_data.get("verdict"),
                    "strengths": idea_data.get("strengths"),
                    "risks": idea_data.get("risks"),
                    "advice": idea_data.get("advice"),
                    "red_flags": idea_data.get("red_flags"),
                    "evaluation_method": "learned_criteria",
                },
            )
            ideas.append(idea)
        
        cache.set(content_hash, ideas)
        return ideas
    
    def _build_criteria_prompt(self, criteria: dict[str, Any]) -> str:
        """Build prompt section for evaluation criteria."""
        
        lines = [
            "=== LEARNED STARTUP SUCCESS CRITERIA ===",
            "",
            "Success Factors (with relative importance):",
        ]
        
        for factor in criteria.get("success_factors", [])[:6]:
            lines.append(f"\n{factor['factor']} (Importance: {factor['importance']}, Weight: {factor.get('weight', 0.1):.0%})")
            lines.append(f"  Description: {factor['description']}")
            lines.append(f"  What to look for:")
            for indicator in factor.get("indicators", [])[:2]:
                lines.append(f"    - {indicator}")
        
        lines.extend([
            "",
            "FAILURE PATTERNS TO AVOID (Red Flags):",
        ])
        
        for pattern in criteria.get("failure_patterns", [])[:4]:
            lines.append(f"\n- {pattern['pattern']} (Severity: {pattern['red_flag_level']})")
            lines.append(f"  {pattern['description']}")
            lines.append(f"  Warning signs:")
            for sign in pattern.get("warning_signs", [])[:2]:
                lines.append(f"    - {sign}")
        
        lines.extend([
            "",
            "=== END CRITERIA ===",
        ])
        
        return "\n".join(lines)
