"""Critic agent - performs adversarial vetting of ideas to find failure modes."""
from __future__ import annotations

from typing import Any

from .config import CriticInput, CriticOutput, Idea
from .llm_client import async_llm_complete_json
from .logger import get_logger


class CriticAgent:
    """Performs adversarial vetting of ideas to identify failure modes and weak assumptions."""

    def __init__(self):
        self.logger = get_logger()

    async def vet(self, input_data: CriticInput) -> CriticOutput:
        """Vet ideas by challenging assumptions and identifying failure modes.
        
        Args:
            input_data: CriticInput containing run_task_id, iteration_number, and ideas to vet
            
        Returns:
            CriticOutput with thinking and vetted_ideas containing failure modes and recommendations
        """
        self.logger.info(f"[iter {input_data.iteration_number}] Critic starting: {len(input_data.ideas)} ideas to vet")

        if not input_data.ideas:
            self.logger.info("Critic received empty input, returning empty output")
            return CriticOutput(thinking="No ideas to vet.", vetted_ideas=[])

        # Build prompt for adversarial analysis
        prompt = self._build_adversarial_prompt(input_data.ideas)

        # Call LLM for adversarial vetting
        response = await async_llm_complete_json(
            prompt=prompt,
            max_tokens=4000,
            temperature=0.5,
        )

        # Parse and validate response
        vetted_ideas = self._parse_response(response, input_data.ideas)
        thinking = response.get("thinking", "") if isinstance(response, dict) else ""

        self.logger.info(f"[iter {input_data.iteration_number}] Critic complete: {len(vetted_ideas)} ideas vetted")

        return CriticOutput(
            thinking=thinking,
            vetted_ideas=vetted_ideas,
        )

    def _build_adversarial_prompt(self, ideas: list[Idea]) -> str:
        """Build adversarial prompt that challenges ideas."""
        
        ideas_text = self._format_ideas_for_prompt(ideas)

        prompt = f"""You are a skeptical investor and startup critic. Your job is to find the WEAKNESSES in every idea.

IDEAS TO CHALLENGE:
{ideas_text}

YOUR TASK:
For each idea, think adversarially. Ask: "Why might this fail?"

Challenge assumptions:
- Is the problem real or imagined?
- Is AI actually necessary, or is this AI-for-AI's-sake?
- Can a solo founder realistically build and scale this?
- Is the market timing right, or is it too early/late?
- Are there hidden competitors or saturated markets?
- Is monetization realistic?
- What could kill this idea?

Think out loud about ALL ideas first, then provide vetted ideas.

Output as JSON:
{{
  "thinking": "Your adversarial analysis of all ideas. Challenge assumptions, identify patterns of weakness, and think about what separates good ideas from bad ones. Be thorough and critical.",
  "vetted_ideas": [
    {{
      "idea_title": "<exact title from input>",
      "idea_summary": "<exact summary from input>",
      "score": <original score or adjusted if you find major flaws>,
      "failure_modes": [
        "Specific reason this might fail",
        "Another failure risk"
      ],
      "weak_assumptions": [
        "Assumption that may not hold",
        "Another weak assumption"
      ],
      "recommendations": [
        "How to improve or pivot",
        "Another recommendation"
      ],
      "vetted": true
    }}
  ]
}}

Rules:
1. Be genuinely critical - find real weaknesses
2. Failure modes should be specific, not generic
3. Weak assumptions should identify what the idea is taking for granted
4. Recommendations should be actionable
5. Adjust score down if you find major flaws (but don't arbitrarily raise scores)
6. Preserve exact idea_title and idea_summary from input
7. Set vetted=true for all ideas (they've been through vetting process)

Only output valid JSON, no markdown."""

        return prompt

    def _format_ideas_for_prompt(self, ideas: list[Idea]) -> str:
        """Format ideas for the LLM prompt."""
        lines = []
        
        for idx, idea in enumerate(ideas, 1):
            # Handle both dict and Idea object
            if isinstance(idea, dict):
                title = idea.get("idea_title", "")
                summary = idea.get("idea_summary", "")
                score = idea.get("score", 0)
                explain = idea.get("evaluator_explain", "")
            else:
                title = idea.idea_title
                summary = idea.idea_summary
                score = idea.score
                explain = idea.evaluator_explain
            
            lines.append(f"\n{idx}. Title: {title}")
            lines.append(f"   Summary: {summary}")
            lines.append(f"   Score: {score}")
            if explain:
                explain_preview = explain[:300] + "..." if len(explain) > 300 else explain
                lines.append(f"   Evaluator Notes: {explain_preview}")

        return "\n".join(lines)

    def _parse_response(self, response: Any, original_ideas: list[Idea]) -> list[dict[str, Any]]:
        """Parse and validate LLM response."""
        
        if not isinstance(response, dict):
            self.logger.warning(f"LLM returned non-dict response: {type(response).__name__}")
            return self._create_default_vetted_ideas(original_ideas)

        vetted_ideas = response.get("vetted_ideas", [])
        
        if not isinstance(vetted_ideas, list):
            self.logger.warning(f"LLM returned non-list vetted_ideas: {type(vetted_ideas).__name__}")
            return self._create_default_vetted_ideas(original_ideas)

        # Validate and clean response
        validated = []
        # Handle both dict and Idea objects
        original_titles = set()
        for idea in original_ideas:
            if isinstance(idea, dict):
                original_titles.add(idea.get("idea_title", ""))
            else:
                original_titles.add(idea.idea_title)
        
        for item in vetted_ideas:
            if not isinstance(item, dict):
                continue

            idea_title = item.get("idea_title", "")
            
            # Verify this matches an original idea
            if idea_title not in original_titles:
                self.logger.warning(f"LLM returned unknown idea title: {idea_title}")
                continue

            # Find original idea for summary
            original_idea = None
            for i in original_ideas:
                if isinstance(i, dict):
                    if i.get("idea_title") == idea_title:
                        original_idea = i
                        break
                else:
                    if i.idea_title == idea_title:
                        original_idea = i
                        break
            
            if isinstance(original_idea, dict):
                original_summary = original_idea.get("idea_summary", "")
                original_score = original_idea.get("score", 0)
            else:
                original_summary = original_idea.idea_summary if original_idea else ""
                original_score = original_idea.score if original_idea else 0

            # Validate and clean fields
            failure_modes = item.get("failure_modes", [])
            if not isinstance(failure_modes, list):
                failure_modes = []

            weak_assumptions = item.get("weak_assumptions", [])
            if not isinstance(weak_assumptions, list):
                weak_assumptions = []

            recommendations = item.get("recommendations", [])
            if not isinstance(recommendations, list):
                recommendations = []

            # Use original summary if LLM modified it
            summary = item.get("idea_summary", original_summary)
            
            # Use LLM score if valid, otherwise original
            score = item.get("score", original_score)
            if not isinstance(score, (int, float)):
                score = original_score

            validated.append({
                "idea_title": idea_title,
                "idea_summary": summary,
                "score": int(score),
                "failure_modes": failure_modes,
                "weak_assumptions": weak_assumptions,
                "recommendations": recommendations,
                "vetted": True,
            })

        # If we lost ideas during validation, add them back with defaults
        validated_titles = {v["idea_title"] for v in validated}
        for idea in original_ideas:
            title = idea.get("idea_title", "") if isinstance(idea, dict) else idea.idea_title
            if title not in validated_titles:
                self.logger.warning(f"Adding missing idea back: {title}")
                if isinstance(idea, dict):
                    validated.append({
                        "idea_title": idea.get("idea_title", ""),
                        "idea_summary": idea.get("idea_summary", ""),
                        "score": idea.get("score", 0),
                        "failure_modes": ["Unable to analyze - LLM response incomplete"],
                        "weak_assumptions": [],
                        "recommendations": [],
                        "vetted": True,
                    })
                else:
                    validated.append({
                        "idea_title": idea.idea_title,
                        "idea_summary": idea.idea_summary,
                        "score": idea.score,
                        "failure_modes": ["Unable to analyze - LLM response incomplete"],
                        "weak_assumptions": [],
                        "recommendations": [],
                        "vetted": True,
                    })

        return validated

    def _create_default_vetted_ideas(self, ideas: list[Idea]) -> list[dict[str, Any]]:
        """Create default vetted ideas when LLM response is invalid."""
        result = []
        for idea in ideas:
            if isinstance(idea, dict):
                result.append({
                    "idea_title": idea.get("idea_title", ""),
                    "idea_summary": idea.get("idea_summary", ""),
                    "score": idea.get("score", 0),
                    "failure_modes": ["Unable to perform adversarial analysis"],
                    "weak_assumptions": [],
                    "recommendations": [],
                    "vetted": True,
                })
            else:
                result.append({
                    "idea_title": idea.idea_title,
                    "idea_summary": idea.idea_summary,
                    "score": idea.score,
                    "failure_modes": ["Unable to perform adversarial analysis"],
                    "weak_assumptions": [],
                    "recommendations": [],
                    "vetted": True,
                })
        return result