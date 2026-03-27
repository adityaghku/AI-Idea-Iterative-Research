from __future__ import annotations

from typing import Any

from .config import DEFAULT_DB_PATH
from .utils import get_knowledge, set_knowledge, get_current_epoch


class MetaLearningAgent:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    def _get_success_factors(self) -> list[dict[str, Any]]:
        weights = {"critical": 0.15, "high": 0.12, "medium": 0.10, "low": 0.08}

        factors = [
            {"factor": "Problem Clarity", "importance": "critical",
             "description": "Clear articulation of problem being solved",
             "indicators": ["Problem is well-defined", "Users have pain point"]},
            {"factor": "AI Advantage", "importance": "critical",
             "description": "Problem genuinely requires AI to solve",
             "indicators": ["Needs pattern recognition", "Scale requires automation"]},
            {"factor": "Market Timing", "importance": "high",
             "description": "Right time in market",
             "indicators": ["Infrastructure ready", "Growing awareness"]},
            {"factor": "Solo Founder Feasible", "importance": "high",
             "description": "Can be built by one person",
             "indicators": ["Manageable scope", "Uses existing APIs"]},
            {"factor": "Distribution Path", "importance": "high",
             "description": "Clear way to reach customers",
             "indicators": ["Clear channels", "Platform leverage"]},
            {"factor": "Monetization", "importance": "medium",
             "description": "Clear path to revenue",
             "indicators": ["Users will pay", "Clear pricing model"]},
            {"factor": "Defensibility", "importance": "medium",
             "description": "Sustainable competitive advantage",
             "indicators": ["Network effects", "Data moat"]},
            {"factor": "Technical Feasible", "importance": "high",
             "description": "Can be built with current tech",
             "indicators": ["Current AI capable", "No research needed"]},
        ]

        for f in factors:
            f["weight"] = weights.get(f["importance"], 0.10)

        return factors

    def _get_failure_patterns(self) -> list[dict[str, Any]]:
        return [
            {"pattern": "Solution Looking for Problem", "red_flag_level": "critical",
             "description": "Building AI without clear use case",
             "warning_signs": ["Tech-first pitch", "No user pain point"]},
            {"pattern": "Ignoring Data Needs", "red_flag_level": "high",
             "description": "Underestimating data requirements",
             "warning_signs": ["No training data plan", "Underestimating costs"]},
            {"pattern": "Over-Engineering", "red_flag_level": "medium",
             "description": "Complex AI when simple works",
             "warning_signs": ["LLM for simple rules", "Complex architecture"]},
            {"pattern": "Underestimating Competition", "red_flag_level": "high",
             "description": "Not acknowledging big tech",
             "warning_signs": ["Big tech could add this", "No differentiation"]},
            {"pattern": "Unclear Unit Economics", "red_flag_level": "critical",
             "description": "AI costs exceed revenue",
             "warning_signs": ["High AI costs", "No cost optimization"]},
        ]

    def _get_market_insights(self) -> dict[str, Any]:
        return {
            "hot_sectors_2024": [
                "AI developer tools",
                "Vertical AI agents",
                "AI content creation",
                "AI automation for SMBs",
            ],
            "saturated_markets": [
                "Generic chatbots",
                "Simple writing assistants",
                "Basic AI image generators",
            ],
        }

    def research_startup_criteria(self, run_task_id: str) -> dict[str, Any]:
        cached = get_knowledge(self.db_path, run_task_id, "evaluation_criteria")
        if cached:
            return cached

        criteria = {
            "version": 1,
            "last_researched": get_current_epoch(),
            "success_factors": self._get_success_factors(),
            "failure_patterns": self._get_failure_patterns(),
            "market_insights": self._get_market_insights(),
        }

        set_knowledge(self.db_path, run_task_id, "evaluation_criteria", criteria)
        return criteria

    def get_evaluation_context(self, run_task_id: str) -> str:
        c = self.research_startup_criteria(run_task_id)
        lines = ["=== EVALUATION CRITERIA ===", ""]

        for i, f in enumerate(c["success_factors"][:5], 1):
            lines.append(f"{i}. {f['factor']} (Weight: {f['weight']:.0%})")
            lines.append(f"   {f['description']}")
            lines.append("")

        lines.extend(["Red Flags:", ""])
        for p in c["failure_patterns"][:3]:
            lines.append(f"- {p['pattern']}: {p['description']}")

        lines.extend(["", "Hot Sectors:", f"  {', '.join(c['market_insights']['hot_sectors_2024'][:3])}"])

        return "\n".join(lines)

    def update_criteria_from_results(self, run_task_id: str, high: list, low: list) -> None:
        c = get_knowledge(self.db_path, run_task_id, "evaluation_criteria")
        if not c:
            return

        c["last_updated"] = get_current_epoch()
        set_knowledge(self.db_path, run_task_id, "evaluation_criteria", c)
