"""Planner agent - generates search plans using learned startup success criteria."""
from __future__ import annotations

import json
from typing import Any

from .config import PlannerInput, PlannerOutput, DEFAULT_DB_PATH
from .utils import get_knowledge
from .meta_learning import MetaLearningAgent
from .llm_client import llm_complete_json
from .logger import get_logger


class PlannerAgent:
    """Generates strategic search plans informed by learned startup success criteria."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self.meta_learning = MetaLearningAgent(db_path=db_path)
        self.logger = get_logger()
    
    def plan(self, input_data: PlannerInput) -> PlannerOutput:
        """Generate a search plan based on goal, knowledge, learned criteria, and previous failures."""
        self.logger.info(f"[iter {input_data.iteration_number}] Planner starting")

        # Get learned evaluation criteria to inform planning
        evaluation_criteria = self.meta_learning.research_startup_criteria(
            input_data.run_task_id
        )

        # Build context for the LLM
        context = self._build_context(input_data, evaluation_criteria)

        # Call LLM to generate search plan
        search_plan = self._call_llm(context)

        num_queries = len(search_plan.get("search_queries", []))
        self.logger.info(f"[iter {input_data.iteration_number}] Planner generated {num_queries} queries")

        return PlannerOutput(
            thinking=search_plan.get("thinking", ""),
            search_queries=search_plan.get("search_queries", []),
            target_sources=search_plan.get("target_sources", []),
            scraping_depth=search_plan.get("scraping_depth", 1),
            filters=search_plan.get("filters", {}),
        )
    
    def _build_context(
        self,
        input_data: PlannerInput,
        evaluation_criteria: dict[str, Any],
    ) -> dict[str, Any]:
        """Build context for LLM prompt including learned criteria."""
        return {
            "goal": input_data.goal,
            "iteration": input_data.iteration_number,
            "knowledge": input_data.knowledge,
            "previous_failures": input_data.previous_failures,
            "evaluation_criteria": evaluation_criteria,
            "hot_sectors": evaluation_criteria.get("market_insights", {}).get("hot_sectors_2024", []),
            "saturated_markets": evaluation_criteria.get("market_insights", {}).get("saturated_markets", []),
        }
    
    def _call_llm(self, context: dict[str, Any]) -> dict[str, Any]:
        """Call LLM to generate search plan using learned criteria."""

        prompt = self._build_prompt(context)
        system = "You are a strategic search planner for discovering innovative AI application ideas. Use learned startup success criteria to find high-potential opportunities."

        result = llm_complete_json(
            prompt=prompt,
            system=system,
            max_tokens=2000,
            temperature=0.7,
        )

        return self._validate_plan(self._coerce_plan_to_dict(result))
    
    def _build_prompt(self, context: dict[str, Any]) -> str:
        """Build the LLM prompt incorporating learned criteria."""
        goal = context["goal"]
        iteration = context["iteration"]
        knowledge = context.get("knowledge", {})
        failures = context.get("previous_failures", [])
        hot_sectors = context.get("hot_sectors", [])
        saturated = context.get("saturated_markets", [])
        
        prompt = f"""You are planning a search strategy for discovering innovative mobile app ideas.

Goal: {goal}
Iteration: {iteration}

=== LEARNED STARTUP SUCCESS CRITERIA ===

Focus on finding mobile app ideas that meet these success factors (in priority order):

1. Problem Clarity - Clear, painful problem being solved for mobile users
2. Mobile-Native Advantage - Leverages mobile-specific features (camera, GPS, sensors, offline)
3. Technical Feasibility - Can be built with today's mobile tech (React Native, Flutter, Swift, Kotlin)
4. Solo Founder Feasible - One person can build MVP and launch on app stores
5. Market Timing - Right time, not too early/late
6. Distribution Path - Clear way to reach mobile users (App Store, Play Store, social, influencers)
7. Monetization Clarity - Clear mobile monetization model (freemium, subscriptions, in-app purchases)
8. Defensibility - Sustainable competitive advantage or network effects

=== CURRENT MARKET INSIGHTS ===

Hot sectors with mobile app opportunities:
"""

        for sector in hot_sectors[:5]:
            prompt += f"- {sector}\n"

        prompt += "\nSaturated markets to avoid:\n"
        for market in saturated[:4]:
            prompt += f"- {market}\n"

        if knowledge:
            prompt += f"\n=== PREVIOUS LEARNINGS ===\n{json.dumps(knowledge, indent=2)}\n"

        if failures:
            prompt += "\n=== FAILURES TO AVOID ===\n"
            for failure in failures:
                prompt += f"- {failure}\n"

        prompt += """
=== YOUR TASK ===

THINK OUT LOUD FIRST: Before generating queries, analyze specific user pains and friction points that could be solved by a mobile app.

Step 1: Think about WHO is suffering and WHAT they struggle with daily ON THEIR PHONES
Step 2: Identify annoying mobile experiences, tedious tasks, or gaps in existing apps
Step 3: Find friction points in people's daily lives that a mobile app could solve
Step 4: Consider what users complain about in app reviews, forums, Reddit, and discussions

PAIN-DRIVEN QUERY EXAMPLES:
- BAD: "mobile app ideas for healthcare"
- GOOD: "what daily tasks do people wish they could do on their phone but can't"

- BAD: "mobile apps for productivity"
- GOOD: "frustrating moments where people reach for their phone but no good app exists"

- BAD: "app ideas for students"
- GOOD: "what problems do college students face daily that an app could solve"

- BAD: "mobile business ideas"
- GOOD: "reddit threads about apps people wish existed"

- BAD: "best mobile startups"
- GOOD: "painful daily routines that could be simplified with a smartphone app"

Generate a search plan targeting mobile app ideas that:
- Solve clear problems for mobile users
- Are feasible for solo founders to build and launch on app stores
- Have clear monetization paths (subscriptions, freemium, in-app purchases)
- Avoid saturated markets and red flags

Structure:
{
  "thinking": "Your chain-of-thought analysis of user pains, friction points, and daily problems that a mobile app could solve. Think out loud about WHO is suffering and WHAT they struggle with on their phones.",
  "search_queries": [
    "pain-driven query focusing on specific user frustrations on mobile",
    "query about annoying daily tasks that could be app-ified",
    "query for mobile app gaps and underserved niches",
    "query about what users complain about in existing apps",
    "query for validated pain points from mobile users"
  ],
  "target_sources": [
    "reddit.com/r/apps",
    "reddit.com/r/androidapps",
    "reddit.com/r/ios",
    "producthunt.com",
    "indiehackers.com",
    "news.ycombinator.com"
  ],
  "scraping_depth": 1,
  "filters": {
    "exclude_patterns": ["sponsored", "advertisement", "generic"],
    "min_relevance": 0.7,
    "focus_areas": ["problem validation", "mobile-native solution", "market timing"]
  },
  "rationale": "Explain how these queries target mobile app opportunities and the learned success criteria"
}

Requirements:
- Return a single JSON object as the root value (not an array wrapping the object)
- 4-5 diverse search queries targeting different aspects of mobile user pain
- Focus on finding MOBILE APP IDEAS (not web SaaS or desktop software)
- Avoid generic queries like "app startup ideas"
- Target sources where REAL mobile users discuss REAL problems
- Consider what worked/failed in previous iterations
- THINK FIRST about user pains before generating queries

Output ONLY valid JSON, no markdown formatting."""
        
        return prompt

    def _coerce_plan_to_dict(self, result: Any) -> dict[str, Any]:
        """LLMs sometimes return a JSON array (e.g. one plan in a list, or only queries). Normalize to a dict."""
        if isinstance(result, dict):
            return result
        if isinstance(result, list):
            if not result:
                raise ValueError("LLM returned an empty JSON array instead of a plan object")
            for item in result:
                if isinstance(item, dict) and (
                    item.get("search_queries")
                    or "thinking" in item
                    or "target_sources" in item
                ):
                    return item
            for item in result:
                if isinstance(item, dict):
                    return item
            if all(isinstance(x, str) for x in result):
                self.logger.warning(
                    "LLM returned a JSON array of strings; treating as search_queries only"
                )
                return {
                    "thinking": "",
                    "search_queries": list(result),
                    "target_sources": [
                        "reddit.com",
                        "news.ycombinator.com",
                        "producthunt.com",
                    ],
                    "scraping_depth": 1,
                    "filters": {},
                }
            raise ValueError(
                f"LLM returned a JSON array that is not a valid plan: {repr(result)[:500]}"
            )
        raise ValueError(
            f"LLM returned {type(result).__name__}, expected a JSON object with search_queries"
        )

    def _validate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize the generated plan."""
        # Extract thinking field (required for pain-driven CoT reasoning)
        thinking = plan.get("thinking", "")
        if not thinking:
            self.logger.warning("LLM returned empty thinking field - pain analysis may be incomplete")
        
        queries = plan.get("search_queries", [])[:5]
        if not queries:
            raise ValueError("LLM returned empty search_queries")
        
        sources = plan.get("target_sources", [])[:5]
        if not sources:
            raise ValueError("LLM returned empty target_sources")
        
        return {
            "thinking": thinking,
            "search_queries": queries,
            "target_sources": sources,
            "scraping_depth": max(1, min(plan.get("scraping_depth", 1), 3)),
            "filters": plan.get("filters", {}),
        }
