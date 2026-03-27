"""Learner agent - computes validation and produces iteration reports."""
from __future__ import annotations

from typing import Any

from .config import LearnerInput, LearnerOutput, DEFAULT_DB_PATH
from .utils import (
    get_iteration_scores,
    get_knowledge,
    set_knowledge,
)
from .meta_learning import MetaLearningAgent
from .logger import get_logger


class LearnerAgent:
    def __init__(self, db_path: str = "idea_harvester.sqlite"):
        self.db_path = db_path
        self.logger = get_logger()

    def _get_attr(self, idea: Any, attr: str, default: Any = None) -> Any:
        if isinstance(idea, dict):
            return idea.get(attr, default)
        return getattr(idea, attr, default)

    def _get_score(self, idea: Any) -> int:
        return self._get_attr(idea, "score", 0)

    def _get_title(self, idea: Any) -> str:
        return self._get_attr(idea, "idea_title", "Untitled")

    def _get_score_breakdown(self, idea: Any) -> Any:
        sb = self._get_attr(idea, "score_breakdown", {})
        if isinstance(sb, dict):
            return sb
        # Use 0 instead of silent 50 default to surface missing data issues
        return {
            "novelty": getattr(sb, "novelty", 0),
            "feasibility": getattr(sb, "feasibility", 0),
            "market_potential": getattr(sb, "market_potential", 0),
        }

    def learn(self, input_data: LearnerInput) -> LearnerOutput:
        self.logger.info(f"[iter {input_data.iteration_number}] Learner starting: {len(input_data.ideas)} ideas, avg_score={input_data.avg_score:.2f}")

        all_scores = get_iteration_scores(
            db_path=self.db_path,
            run_task_id=input_data.run_task_id,
        )
        
        # Compute validation score
        validation_score = self._compute_validation_score(
            input_data.avg_score,
            all_scores,
            input_data.iteration_number,
        )
        
        # Determine if we improved
        did_improve = self._check_improvement(
            input_data.avg_score,
            all_scores,
            input_data.iteration_number,
        )
        
        # Identify what failed
        what_failed = self._identify_failures(input_data)
        
        # Determine next action
        next_action = self._determine_next_action(
            what_failed,
            input_data,
        )
        
        # Build knowledge updates
        knowledge_updates = self._build_knowledge_updates(
            input_data,
            did_improve,
            what_failed,
        )
        
        # Generate report
        iteration_report = self._generate_report(
            input_data,
            did_improve,
            what_failed,
            next_action,
        )
        
        validation_explain = self._generate_validation_explain(
            validation_score,
            did_improve,
            input_data,
        )
        
        self.logger.info(f"[iter {input_data.iteration_number}] Learner complete: validation={validation_score:.2f}, improved={did_improve}")

        return LearnerOutput(
            validation_score=validation_score,
            validation_explain=validation_explain,
            did_improve=did_improve,
            what_failed=what_failed,
            next_highest_value_action=next_action,
            knowledge_updates=knowledge_updates,
            iteration_report=iteration_report,
        )
    
    def _compute_validation_score(
        self,
        current_avg: float,
        all_scores: list[dict[str, Any]],
        current_iteration: int,
    ) -> float:
        """Compute validation score based on improvement and quality."""
        
        # Base score from current average
        base_score = current_avg if current_avg else 0.0
        
        if len(all_scores) >= 2 and current_iteration is not None:
            prev_scores = [s for s in all_scores if s.get("iteration_number", 0) < current_iteration]
            if prev_scores:
                prev_avg = sum(s.get("avg_score", 0) or 0 for s in prev_scores) / len(prev_scores)
                if current_avg > prev_avg:
                    base_score += (current_avg - prev_avg) * 0.5
        
        # Normalize to 0-100
        return min(100.0, max(0.0, base_score))
    
    def _check_improvement(
        self,
        current_avg: float,
        all_scores: list[dict[str, Any]],
        current_iteration: int,
    ) -> bool:
        """Check if this iteration improved over previous."""
        
        if current_iteration <= 1:
            return True  # First iteration is always "improved"
        
        prev_iteration = current_iteration - 1
        prev_score = None
        
        for s in all_scores:
            if s.get("iteration_number") == prev_iteration:
                prev_score = s.get("avg_score")
                break
        
        if prev_score is None:
            return True
        
        return (current_avg or 0) > prev_score
    
    def _identify_failures(self, input_data: LearnerInput) -> list[str]:
        failures = []

        if len(input_data.ideas) < 3:
            failures.append(f"Low idea yield: only {len(input_data.ideas)} ideas extracted")

        if input_data.avg_score < 50:
            failures.append(f"Low average score: {input_data.avg_score:.1f} (threshold: 50)")

        high_scores = [i for i in input_data.ideas if self._get_score(i) >= 70]
        if len(high_scores) < 2:
            failures.append(f"Few high-quality ideas: only {len(high_scores)} scored >= 70")

        return failures
    
    def _determine_next_action(
        self,
        failures: list[str],
        input_data: LearnerInput,
    ) -> str:
        """Determine the next highest value action."""
        
        # Count failure types
        low_yield = any("yield" in f.lower() for f in failures)
        low_quality = any("score" in f.lower() for f in failures)
        
        if low_yield:
            return "fix_scraper"
        elif low_quality:
            return "improve_filters"
        else:
            return "refine_queries"
    
    def _build_knowledge_updates(
        self,
        input_data: LearnerInput,
        did_improve: bool,
        failures: list[str],
    ) -> dict[str, Any]:
        high_scoring_ideas = [i for i in input_data.ideas if self._get_score(i) >= 70]

        successful_patterns = []
        for i in high_scoring_ideas[:3]:
            sb = self._get_score_breakdown(i)
            novelty = sb.get("novelty")
            feasibility = sb.get("feasibility")
            market = sb.get("market_potential")
            if novelty is None or feasibility is None or market is None:
                missing = []
                if novelty is None:
                    missing.append("novelty")
                if feasibility is None:
                    missing.append("feasibility")
                if market is None:
                    missing.append("market_potential")
                self.logger.warning(f"Missing score breakdown fields: {missing}")
            successful_patterns.append({
                "title": self._get_title(i),
                "score": self._get_score(i),
                "aspects": {
                    "novelty": novelty if novelty is not None else 0,
                    "feasibility": feasibility if feasibility is not None else 0,
                    "market": market if market is not None else 0,
                },
            })

        return {
            "iteration": input_data.iteration_number,
            "did_improve": did_improve,
            "avg_score": input_data.avg_score,
            "idea_count": len(input_data.ideas),
            "high_scoring_count": len(high_scoring_ideas),
            "failures": failures,
            "successful_patterns": successful_patterns,
        }
    
    def _generate_report(
        self,
        input_data: LearnerInput,
        did_improve: bool,
        failures: list[str],
        next_action: str,
    ) -> str:
        lines = [
            f"Iteration {input_data.iteration_number} Report:",
            "",
            f"Average Score: {input_data.avg_score:.2f}",
            f"Ideas Generated: {len(input_data.ideas)}",
            f"Did Improve: {did_improve}",
            "",
        ]

        if failures:
            lines.append("Issues Identified:")
            for failure in failures:
                lines.append(f"  - {failure}")
            lines.append("")

        lines.append(f"Recommended Next Action: {next_action}")
        lines.append("")

        top_ideas = sorted(input_data.ideas, key=lambda x: self._get_score(x), reverse=True)[:3]
        if top_ideas:
            lines.append("Top Ideas:")
            for idea in top_ideas:
                lines.append(f"  - {self._get_title(idea)} (Score: {self._get_score(idea)})")

        return "\n".join(lines)
    
    def _generate_validation_explain(
        self,
        validation_score: float,
        did_improve: bool,
        input_data: LearnerInput,
    ) -> str:
        """Generate explanation for validation score."""
        
        if did_improve:
            return f"Iteration {input_data.iteration_number} showed improvement with validation score {validation_score:.2f}. Generated {len(input_data.ideas)} ideas with average score {input_data.avg_score:.2f}."
        else:
            return f"Iteration {input_data.iteration_number} did not improve over previous. Validation score {validation_score:.2f}. Consider adjusting strategy based on failure analysis."
