"""Configuration and type definitions for Idea Harvester agents."""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional
from dataclasses import dataclass, field


class Stage(str, Enum):
    """Agent stages in the workflow."""
    PLANNER = "planner"
    RESEARCHER = "researcher"
    SCRAPER = "scraper"
    EVALUATOR = "evaluator"
    TAGGER = "tagger"
    LEARNER = "learner"
    FINALIZE = "finalize"


class SourceStatus(str, Enum):
    """Status values for sources table."""
    QUEUED = "queued"
    SCRAPED = "scraped"
    FAILED = "failed"


class MessageStatus(str, Enum):
    """Status values for queue_messages table."""
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


# Constants
DEFAULT_SCRAPER_COOLDOWN_SECONDS = 300  # 5 minutes
DEFAULT_MAX_ITERATIONS = 5
DEFAULT_PLATEAU_WINDOW = 2
DEFAULT_MIN_IMPROVEMENT = 0.0
DEFAULT_RETRY_LIMIT = 2
DEFAULT_DB_PATH = "idea_harvester.sqlite"
DEFAULT_VERBOSE = True


@dataclass
class PlannerInput:
    """Input for Planner agent."""
    run_task_id: str
    iteration_number: int
    goal: str
    knowledge: dict[str, Any] = field(default_factory=dict)
    previous_failures: list[str] = field(default_factory=list)
    accumulated_ideas: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PlannerOutput:
    """Output from Planner agent."""
    search_queries: list[str]
    target_sources: list[str]
    scraping_depth: int
    filters: dict[str, Any]
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "search_queries": self.search_queries,
            "target_sources": self.target_sources,
            "scraping_depth": self.scraping_depth,
            "filters": self.filters,
        }


@dataclass
class ResearcherInput:
    """Input for Researcher agent."""
    run_task_id: str
    iteration_number: int
    search_plan: PlannerOutput


@dataclass
class ResearcherOutput:
    """Output from Researcher agent."""
    candidate_urls: list[str]
    coverage_notes: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_urls": self.candidate_urls,
            "coverage_notes": self.coverage_notes,
        }


@dataclass
class ScraperInput:
    """Input for Scraper agent."""
    run_task_id: str
    iteration_number: int
    urls: list[str]
    throttle_seconds: int = DEFAULT_SCRAPER_COOLDOWN_SECONDS


@dataclass
class ScraperOutput:
    """Output from Scraper agent."""
    extracted: list[dict[str, Any]]
    scrape_quality: float
    scrape_failures: list[str]
    dedup_removed_count: int
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "extracted": self.extracted,
            "scrape_quality": self.scrape_quality,
            "scrape_failures": self.scrape_failures,
            "dedup_removed_count": self.dedup_removed_count,
        }


@dataclass
class EvaluatorInput:
    """Input for Evaluator agent."""
    run_task_id: str
    iteration_number: int
    extracted_content: list[dict[str, Any]]


@dataclass  
class IdeaScore:
    """Score breakdown for an idea."""
    novelty: int
    feasibility: int
    market_potential: int
    
    def total(self) -> int:
        # Weighted: 30% novelty, 40% feasibility, 30% market
        return int(0.3 * self.novelty + 0.4 * self.feasibility + 0.3 * self.market_potential)


@dataclass
class Idea:
    """An evaluated idea."""
    idea_title: str
    idea_summary: str
    source_urls: list[str]
    score: int
    score_breakdown: IdeaScore
    evaluator_explain: str
    idea_payload: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "idea_title": self.idea_title,
            "idea_summary": self.idea_summary,
            "source_urls": self.source_urls,
            "score": self.score,
            "score_breakdown": {
                "novelty": self.score_breakdown.novelty,
                "feasibility": self.score_breakdown.feasibility,
                "market_potential": self.score_breakdown.market_potential,
            },
            "evaluator_explain": self.evaluator_explain,
            "idea_payload": self.idea_payload,
        }


@dataclass
class EvaluatorOutput:
    """Output from Evaluator agent."""
    ideas: list[Idea]
    iteration_summary: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "ideas": [idea.to_dict() for idea in self.ideas],
            "iteration_summary": self.iteration_summary,
        }


@dataclass
class TaggerInput:
    """Input for Tagger agent."""
    ideas: list[dict[str, Any]]
    categories: list[str]


@dataclass
class TaggerOutput:
    """Output from Tagger agent."""
    tagged_ideas: list[dict[str, Any]]
    tag_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tagged_ideas": self.tagged_ideas,
            "tag_counts": self.tag_counts,
        }


@dataclass
class LearnerInput:
    """Input for Learner agent."""
    run_task_id: str
    iteration_number: int
    ideas: list[Idea]
    avg_score: float


@dataclass
class LearnerOutput:
    """Output from Learner agent."""
    validation_score: float
    validation_explain: str
    did_improve: bool
    what_failed: list[str]
    next_highest_value_action: str  # "fix_scraper" | "refine_queries" | "improve_filters"
    knowledge_updates: dict[str, Any]
    iteration_report: str
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "validation": {
                "validation_score": self.validation_score,
                "validation_explain": self.validation_explain,
            },
            "did_improve": self.did_improve,
            "what_failed": self.what_failed,
            "next_highest_value_action": self.next_highest_value_action,
            "knowledge_updates": self.knowledge_updates,
            "iteration_report": self.iteration_report,
        }


@dataclass
class RunConfig:
    """Configuration for a run."""
    run_task_id: str
    goal: str
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    plateau_window: int = DEFAULT_PLATEAU_WINDOW
    min_improvement: float = DEFAULT_MIN_IMPROVEMENT
    db_path: str = DEFAULT_DB_PATH
    model: Optional[str] = None
    max_llm_concurrency: int = 5
    max_search_concurrency: int = 3
    max_fetch_concurrency: int = 3
