"""Idea Harvester agents package."""

from .config import (
    Stage,
    SourceStatus,
    MessageStatus,
    PlannerInput,
    PlannerOutput,
    ResearcherInput,
    ResearcherOutput,
    ScraperInput,
    ScraperOutput,
    EvaluatorInput,
    EvaluatorOutput,
    LearnerInput,
    LearnerOutput,
    Idea,
    IdeaScore,
    RunConfig,
    DEFAULT_SCRAPER_COOLDOWN_SECONDS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PLATEAU_WINDOW,
    DEFAULT_MIN_IMPROVEMENT,
    DEFAULT_DB_PATH,
)

from .utils import (
    get_current_epoch,
    call_db,
    can_scrape,
    update_scraper_timestamp,
    get_knowledge,
    set_knowledge,
    create_run,
    ensure_iteration,
    enqueue_message,
    dequeue_message,
    mark_done,
    mark_failed,
    store_iteration_output,
    store_ideas,
    store_validation,
    get_iteration_scores,
    get_top_ideas,
    filter_new_urls,
    mark_sources_status,
    list_pending_messages,
)

from .planner import PlannerAgent
from .researcher import ResearcherAgent
from .scraper import ScraperAgent
from .evaluator import EvaluatorAgent
from .learner import LearnerAgent
from .orchestrator import Orchestrator
from .meta_learning import MetaLearningAgent
from .llm_client import OpenCodeLLMClient, llm_complete, llm_complete_json
from .logger import setup_logging, get_logger

__all__ = [
    # Config
    "Stage",
    "SourceStatus",
    "MessageStatus",
    "PlannerInput",
    "PlannerOutput",
    "ResearcherInput",
    "ResearcherOutput",
    "ScraperInput",
    "ScraperOutput",
    "EvaluatorInput",
    "EvaluatorOutput",
    "LearnerInput",
    "LearnerOutput",
    "Idea",
    "IdeaScore",
    "RunConfig",
    "get_current_epoch",
    "call_db",
    "can_scrape",
    "update_scraper_timestamp",
    "get_knowledge",
    "set_knowledge",
    "create_run",
    "ensure_iteration",
    "enqueue_message",
    "dequeue_message",
    "mark_done",
    "mark_failed",
    "store_iteration_output",
    "store_ideas",
    "store_validation",
    "get_iteration_scores",
    "get_top_ideas",
    "filter_new_urls",
    "mark_sources_status",
    "list_pending_messages",
    # Agents
    "PlannerAgent",
    "ResearcherAgent",
    "ScraperAgent",
    "EvaluatorAgent",
    "LearnerAgent",
    "Orchestrator",
    "MetaLearningAgent",
    "OpenCodeLLMClient",
    "llm_complete",
    "llm_complete_json",
    "setup_logging",
    "get_logger",
]
