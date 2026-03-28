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

        return self._validate_plan(result)
    
    def _build_prompt(self, context: dict[str, Any]) -> str:
        """Build the LLM prompt incorporating learned criteria."""
        goal = context["goal"]
        iteration = context["iteration"]
        knowledge = context.get("knowledge", {})
        failures = context.get("previous_failures", [])
        hot_sectors = context.get("hot_sectors", [])
        saturated = context.get("saturated_markets", [])
        
        prompt = f"""You are planning a search strategy for discovering innovative AI application ideas.

Goal: {goal}
Iteration: {iteration}

=== LEARNED STARTUP SUCCESS CRITERIA ===

Focus on finding ideas that meet these success factors (in priority order):

1. Problem Clarity - Clear, painful problem being solved
2. AI Advantage - Genuinely requires AI (not AI for AI's sake)
3. Technical Feasibility - Can be built with today's technology
4. Solo Founder Feasible - One person can build and launch
5. Market Timing - Right time, not too early/late
6. Distribution Path - Clear way to reach customers
7. Monetization Clarity - Willingness to pay exists
8. Defensibility - Sustainable competitive advantage

=== CURRENT MARKET INSIGHTS ===

Hot sectors with opportunities:
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

THINK OUT LOUD FIRST: Before generating queries, analyze specific user pains and friction points.

Step 1: Think about WHO is suffering and WHAT they struggle with daily
Step 2: Identify tedious manual tasks that waste time
Step 3: Find friction points in workflows that could be automated
Step 4: Consider what users complain about in forums, reviews, and discussions

PAIN-DRIVEN QUERY EXAMPLES:
- BAD: "AI startup ideas in healthcare"
- GOOD: "what tasks do doctors hate doing manually that could be automated"

- BAD: "AI applications for finance"
- GOOD: "frustrating manual workflows in accounting that waste time"

- BAD: "AI tools for education"
- GOOD: "pain points teachers face with grading and lesson planning"

- BAD: "AI solutions for small business"
- GOOD: "repetitive administrative tasks small business owners dread"

- BAD: "AI productivity tools"
- GOOD: "time-consuming tasks knowledge workers want to automate"

Generate a search plan targeting ideas that:
- Solve clear problems in the hot sectors listed above
- Leverage current AI capabilities (LLMs, vision, agents)
- Are feasible for solo founders to build
- Have clear paths to market and monetization
- Avoid saturated markets and red flags

Structure:
{
  "thinking": "Your chain-of-thought analysis of user pains, friction points, and tedious tasks that could be automated. Think out loud about WHO is suffering and WHAT they struggle with.",
  "search_queries": [
    "pain-driven query focusing on specific user frustrations",
    "query about tedious manual tasks in a domain",
    "query for workflow friction points",
    "query about what users complain about",
    "query for validated pain points"
  ],
  "target_sources": [
    "specific high-quality sources",
    "communities where target users gather",
    "platforms showing early adoption signals"
  ],
  "scraping_depth": 1,
  "filters": {
    "exclude_patterns": ["sponsored", "advertisement", "generic"],
    "min_relevance": 0.7,
    "focus_areas": ["problem validation", "AI necessity", "market timing"]
  },
  "rationale": "Explain how these queries target the learned success criteria"
}

Requirements:
- 4-5 diverse search queries targeting different aspects
- Focus on finding IDEAS that meet success criteria (not just any AI product)
- Avoid generic queries like "AI startup ideas"
- Target sources where REAL users discuss REAL problems
- Consider what worked/failed in previous iterations
- THINK FIRST about user pains before generating queries

Output ONLY valid JSON, no markdown formatting."""
        
        return prompt
    
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
