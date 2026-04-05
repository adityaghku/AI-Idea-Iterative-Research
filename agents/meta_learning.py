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
             "description": "Clear articulation of mobile user problem being solved",
             "indicators": ["Problem is well-defined for mobile context", "Users have real pain point"]},
            {"factor": "Mobile-Native Advantage", "importance": "critical",
             "description": "App leverages mobile-specific features or context",
             "indicators": ["Uses camera, GPS, sensors, or offline", "On-the-go use case", "Mobile is the best form factor"]},
            {"factor": "Market Timing", "importance": "high",
             "description": "Right time for this mobile solution",
             "indicators": ["App store category growing", " underserved niche", "Platform features enable it"]},
            {"factor": "Solo Founder Feasible", "importance": "high",
             "description": "Can be built and launched by one person",
             "indicators": ["Manageable scope for solo dev", "Can launch MVP quickly", "No enterprise sales needed"]},
            {"factor": "Distribution Path", "importance": "high",
             "description": "Clear way to reach mobile users",
             "indicators": ["App Store/Play Store optimization", "Social viral potential", "Influencer marketing"]},
            {"factor": "Monetization", "importance": "medium",
             "description": "Clear mobile monetization model",
             "indicators": ["Freemium model viable", "Subscription potential", "In-app purchases make sense"]},
            {"factor": "Defensibility", "importance": "medium",
             "description": "Sustainable competitive advantage",
             "indicators": ["Network effects", "Data moat", "Community lock-in"]},
            {"factor": "Technical Feasible", "importance": "high",
             "description": "Can be built with current mobile tech",
             "indicators": ["React Native/Flutter/Swift capable", "No backend complexity", "Uses existing APIs/SDKs"]},
        ]

        for f in factors:
            f["weight"] = weights.get(f["importance"], 0.10)

        return factors

    def _get_failure_patterns(self) -> list[dict[str, Any]]:
        return [
            {"pattern": "Solution Looking for Problem", "red_flag_level": "critical",
             "description": "Building an app without clear user pain point",
             "warning_signs": ["App-first pitch without user need", "No clear user pain point"]},
            {"pattern": "Not Mobile-Native", "red_flag_level": "high",
             "description": "Could be a website instead of an app",
             "warning_signs": ["No mobile-specific features used", "Better as web app", "Desktop-first use case"]},
            {"pattern": "Over-Engineering", "red_flag_level": "medium",
             "description": "Complex architecture for simple problem",
             "warning_signs": ["Unnecessary backend complexity", "Too many features for MVP"]},
            {"pattern": "Underestimating Competition", "red_flag_level": "high",
             "description": "Not acknowledging established apps",
             "warning_signs": ["Big apps could add this feature", "No clear differentiation", "Red ocean market"]},
            {"pattern": "Unclear Mobile Monetization", "red_flag_level": "critical",
             "description": "No viable app store monetization strategy",
             "warning_signs": ["Unclear how to make money", "No freemium path", "No in-app purchase hooks"]},
        ]

    def _get_market_insights(self) -> dict[str, Any]:
        return {
            "hot_sectors_2024": [
                "Health & wellness apps",
                "Productivity & focus apps",
                "Creator tools & content apps",
                "Financial management apps",
                "Social & community apps",
                "Education & learning apps",
            ],
            "saturated_markets": [
                "Generic to-do list apps",
                "Simple calculator apps",
                "Basic note-taking apps",
                "Another fitness tracker",
                "Weather apps",
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

        success_factors = c.get("success_factors", [])
        for i, f in enumerate(success_factors[:5], 1):
            lines.append(f"{i}. {f.get('factor', 'Unknown')} (Weight: {f.get('weight', 0):.0%})")
            lines.append(f"   {f.get('description', '')}")
            lines.append("")

        lines.extend(["Red Flags:", ""])
        failure_patterns = c.get("failure_patterns", [])
        for p in failure_patterns[:3]:
            lines.append(f"- {p.get('pattern', 'Unknown')}: {p.get('description', '')}")

        market_insights = c.get("market_insights", {})
        hot_sectors = market_insights.get("hot_sectors_2024", [])
        lines.extend(["", "Hot Sectors:", f"  {', '.join(hot_sectors[:3])}"])

        return "\n".join(lines)

    def update_criteria_from_results(self, run_task_id: str, high: list, low: list) -> None:
        c = get_knowledge(self.db_path, run_task_id, "evaluation_criteria")
        if not c:
            return

        c["last_updated"] = get_current_epoch()
        set_knowledge(self.db_path, run_task_id, "evaluation_criteria", c)
