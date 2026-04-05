from __future__ import annotations

import asyncio
import json
import os
import sqlite3
from typing import Any, Optional

from .logger import get_logger
from .config import (
    RunConfig,
    Stage,
    PlannerInput,
    ResearcherInput,
    ScraperInput,
    EvaluatorInput,
    CriticInput,
    LearnerInput,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_PLATEAU_WINDOW,
    DEFAULT_MIN_IMPROVEMENT,
    DEFAULT_DB_PATH,
)
from .utils import (
    create_run,
    ensure_iteration,
    enqueue_message,
    mark_done,
    mark_failed,
    store_iteration_output,
    store_ideas,
    store_validation,
    get_iteration_scores,
    get_top_ideas,
    list_pending_messages,
    get_knowledge,
    set_knowledge,
    generate_embeddings_for_run,
    merge_duplicate_ideas,
    record_accumulated_knowledge,
    get_accumulated_stats,
    get_idea_stats,
)
from .planner import PlannerAgent
from .researcher import ResearcherAgent
from .scraper import ScraperAgent
from .evaluator import EvaluatorAgent
from .critic import CriticAgent
from .learner import LearnerAgent


class Orchestrator:
    """Coordinates the multi-agent workflow for idea harvesting."""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        run_task_id: Optional[str] = None,
        goal: Optional[str] = None,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        plateau_window: int = DEFAULT_PLATEAU_WINDOW,
        min_improvement: float = DEFAULT_MIN_IMPROVEMENT,
        model: Optional[str] = None,
    ):
        self.db_path = db_path
        self.config = RunConfig(
            run_task_id=run_task_id or self._generate_task_id(),
            goal=goal or "Find innovative AI app ideas",
            max_iterations=max_iterations,
            plateau_window=plateau_window,
            min_improvement=min_improvement,
            db_path=db_path,
            model=model,
        )
        self.agents = {
            Stage.PLANNER: PlannerAgent(db_path=db_path),
            Stage.RESEARCHER: ResearcherAgent(db_path=db_path),
            Stage.SCRAPER: ScraperAgent(db_path=db_path),
            Stage.EVALUATOR: EvaluatorAgent(db_path=db_path),
            Stage.CRITIC: CriticAgent(),
            Stage.LEARNER: LearnerAgent(db_path=db_path),
        }
        self._stop_sentinel = ".idea-harvester-off"
        self.logger = get_logger()
        self.logger.info(f"Orchestrator initialized: run={self.config.run_task_id}")
    
    def _generate_task_id(self) -> str:
        """Generate a unique task ID."""
        import uuid
        return f"run_{uuid.uuid4().hex[:12]}"
    
    def _check_stop_sentinel(self) -> bool:
        """Check if stop sentinel file exists."""
        return os.path.exists(self._stop_sentinel)
    
    def _remove_stop_sentinel(self) -> None:
        """Remove stop sentinel file if it exists."""
        if os.path.exists(self._stop_sentinel):
            os.remove(self._stop_sentinel)
    
    def initialize(self) -> None:
        """Initialize the run in the database."""
        self.logger.info("Initializing run", extra={"goal_preview": self.config.goal[:100]})
        try:
            create_run(
                db_path=self.db_path,
                task_id=self.config.run_task_id,
                goal=self.config.goal,
                max_iterations=self.config.max_iterations,
                plateau_window=self.config.plateau_window,
                min_improvement=self.config.min_improvement,
                model=self.config.model,
            )
            self.logger.info(f"Run initialized: {self.config.run_task_id}")
            print(f"Initialized run: {self.config.run_task_id}")
            print(f"Goal: {self.config.goal}")
        except Exception as e:
            self.logger.exception("Failed to initialize run", extra={"error": str(e)})
            raise
    
    def start(self) -> None:
        """Start the orchestration loop from iteration 1."""
        self.logger.info("Starting orchestration")
        self._remove_stop_sentinel()
        self.initialize()
        self._run_iterations()
    
    def resume(self) -> None:
        """Resume from existing state in database."""
        self.logger.info("Resuming run")
        self._remove_stop_sentinel()
        print(f"Resuming run: {self.config.run_task_id}")

        # Check for pending messages and resume from where we left off
        pending = list_pending_messages(self.db_path, self.config.run_task_id)
        if pending:
            self.logger.info(f"Found {len(pending)} pending messages", extra={"pending_count": len(pending)})
            print(f"Found {len(pending)} pending messages, resuming...")
            # Process pending messages first
            self._process_pending_messages()

        # Continue with next iterations
        self._run_iterations()
    
    def _process_pending_messages(self) -> None:
        """Process any pending messages from a previous run."""
        self.logger.info("Processing pending messages")
        max_attempts = 3
        for attempt in range(max_attempts):
            pending = list_pending_messages(self.db_path, self.config.run_task_id)
            if not pending:
                self.logger.debug("No more pending messages")
                break

            self.logger.info(f"Processing {len(pending)} pending messages (attempt {attempt + 1})")
            for msg in pending:
                if self._check_stop_sentinel():
                    self.logger.info("Stop sentinel detected during pending message processing")
                    print("Stop sentinel detected, halting...")
                    return

                stage = msg.get("stage")
                iteration = msg.get("iteration_number")

                if stage and iteration:
                    self.logger.info(f"Stage transition: pending_resume -> {stage} (iter {iteration})")
                    print(f"Processing pending {stage} for iteration {iteration}")
                    self._execute_stage(stage, iteration)
    
    def _run_iterations(self) -> None:
        """Run iterations until completion or stop condition."""
        # Determine which iteration to start from
        scores = get_iteration_scores(self.db_path, self.config.run_task_id)
        completed_iterations = len([s for s in scores if s.get("avg_score") is not None])
        self.logger.info(f"Starting iterations (completed: {completed_iterations}, max: {self.config.max_iterations})")

        for iteration_num in range(completed_iterations + 1, self.config.max_iterations + 1):
            if self._check_stop_sentinel():
                self.logger.info("Stop sentinel detected, halting iterations")
                print("Stop sentinel detected, halting...")
                break

            self.logger.info(f"Starting iteration {iteration_num}/{self.config.max_iterations}")
            print(f"\n{'='*60}")
            print(f"Starting iteration {iteration_num}/{self.config.max_iterations}")
            print(f"{'='*60}")

            # Run single iteration
            result = self._run_iteration(iteration_num)

            if result.get("stopped"):
                reason = result.get('reason', 'unknown')
                self.logger.info(f"Stopping: {reason}")
                print(f"Stopping: {reason}")
                break

            # Check plateau
            if self._check_plateau():
                self.logger.info(f"Plateau detected after {iteration_num} iterations")
                print(f"Plateau detected after {iteration_num} iterations")
                break

        # Finalize
        self._finalize()
    
    def _run_iteration(self, iteration_number: int) -> dict[str, Any]:
        """Run a single iteration through all stages."""
        self.logger.info(f"[iter {iteration_number}] Starting iteration")

        ensure_iteration(self.db_path, self.config.run_task_id, iteration_number)

        stages = [
            (Stage.PLANNER.value, "Generating search plan"),
            (Stage.RESEARCHER.value, "Finding candidate URLs"),
            (Stage.SCRAPER.value, "Extracting content (throttled)"),
            (Stage.EVALUATOR.value, "Scoring ideas"),
            (Stage.CRITIC.value, "Adversarial vetting"),
            (Stage.LEARNER.value, "Computing validation and learning"),
        ]
        n_stages = len(stages)

        for i, (stage, description) in enumerate(stages, 1):
            self.logger.info(f"[iter {iteration_number}] Stage {i}/{n_stages}: {stage}")
            print(f"\n[{i}/{n_stages}] {stage.capitalize()}: {description}...")

            result = self._execute_stage(stage, iteration_number)
            if not result:
                self.logger.error(f"[iter {iteration_number}] Stage {stage} failed")
                return {"stopped": True, "reason": f"{stage} failed"}
            self.logger.info(f"[iter {iteration_number}] Stage {stage} completed")

        self.logger.info(f"[iter {iteration_number}] Complete")
        print(f"\nIteration {iteration_number} complete!")
        return {"stopped": False}

    def _execute_stage(self, stage: str, iteration_number: int) -> Optional[dict[str, Any]]:
        """Execute a single stage by enqueuing and waiting for completion."""
        self.logger.debug(f"[iter {iteration_number}] Executing stage {stage}")

        # Check for existing pending message for this stage
        pending = list_pending_messages(
            self.db_path,
            self.config.run_task_id,
            to_agent=stage,
            stage=stage,
            iteration_number=iteration_number,
        )

        if pending:
            # Use existing message
            msg = pending[0]
            message_id = msg["message_id"]
            payload = msg["payload"]
            self.logger.debug(f"[iter {iteration_number}] Using existing message {message_id}")
        else:
            # Get previous stage output to build input
            payload = self._build_stage_input(stage, iteration_number)
            if payload is None:
                self.logger.error(f"[iter {iteration_number}] Failed to build stage input for {stage}")
                return None

            # Enqueue new message
            message_id = enqueue_message(
                db_path=self.db_path,
                run_task_id=self.config.run_task_id,
                from_agent="orchestrator",
                to_agent=stage,
                stage=stage,
                payload=payload,
                iteration_number=iteration_number,
            )
            self.logger.debug(f"[iter {iteration_number}] Enqueued message {message_id}")

        # Execute the agent
        try:
            result = self._execute_agent(stage, payload, iteration_number)

            if result:
                mark_done(self.db_path, message_id, result)
                store_iteration_output(
                    self.db_path,
                    self.config.run_task_id,
                    iteration_number,
                    stage,
                    result,
                )
                self.logger.info(f"[iter {iteration_number}] Stage {stage} completed")
                return result
            else:
                self.logger.error(f"[iter {iteration_number}] Stage {stage} returned no result")
                mark_failed(self.db_path, message_id, "Agent returned no result")
                return None

        except Exception as e:
            self.logger.exception(f"[iter {iteration_number}] Error in stage {stage}: {e}")
            print(f"Error in {stage}: {e}")
            mark_failed(self.db_path, message_id, str(e))
            return None
    
    def _build_stage_input(self, stage: str, iteration_number: int) -> Optional[dict[str, Any]]:
        """Build input payload for a stage based on previous stage output."""
        if stage == Stage.PLANNER:
            prev_failures = []
            if iteration_number > 1:
                prev_knowledge = get_knowledge(
                    self.db_path,
                    self.config.run_task_id,
                    f"learner_output_{iteration_number - 1}"
                )
                if prev_knowledge:
                    prev_failures = prev_knowledge.get("what_failed", [])
            
            return {
                "run_task_id": self.config.run_task_id,
                "iteration_number": iteration_number,
                "goal": self.config.goal,
                "knowledge": get_knowledge(self.db_path, self.config.run_task_id, "accumulated_knowledge") or {},
                "previous_failures": prev_failures,
                "accumulated_ideas": self._load_accumulated_ideas(),
            }
        
        elif stage == Stage.RESEARCHER:
            # Get planner output
            planner_data = get_knowledge(
                self.db_path,
                self.config.run_task_id,
                f"planner_output_{iteration_number}"
            )
            if not planner_data:
                print("No planner output found")
                return None
            
            return {
                "run_task_id": self.config.run_task_id,
                "iteration_number": iteration_number,
                "search_plan": planner_data,
            }
        
        elif stage == Stage.SCRAPER:
            # Get researcher output
            researcher_data = get_knowledge(
                self.db_path,
                self.config.run_task_id,
                f"researcher_output_{iteration_number}"
            )
            if not researcher_data:
                print("No researcher output found")
                return None
            
            return {
                "run_task_id": self.config.run_task_id,
                "iteration_number": iteration_number,
                "urls": researcher_data.get("candidate_urls", []),
            }
        
        elif stage == Stage.EVALUATOR:
            # Get scraper output
            scraper_data = get_knowledge(
                self.db_path,
                self.config.run_task_id,
                f"scraper_output_{iteration_number}"
            )
            if not scraper_data:
                print("No scraper output found")
                return None
            
            return {
                "run_task_id": self.config.run_task_id,
                "iteration_number": iteration_number,
                "extracted_content": scraper_data.get("extracted", []),
            }
        
        elif stage == Stage.CRITIC:
            # Get evaluator output
            evaluator_data = get_knowledge(
                self.db_path,
                self.config.run_task_id,
                f"evaluator_output_{iteration_number}"
            )
            if not evaluator_data:
                print("No evaluator output found")
                return None
            
            # Convert dict ideas back to Idea objects
            from .config import Idea, IdeaScore
            ideas = []
            for idea_dict in evaluator_data.get("ideas", []):
                sb = idea_dict.get("score_breakdown", {})
                idea = Idea(
                    idea_title=idea_dict.get("idea_title", ""),
                    idea_summary=idea_dict.get("idea_summary", ""),
                    source_urls=idea_dict.get("source_urls", []),
                    score=idea_dict.get("score", 0),
                    score_breakdown=IdeaScore(
                        novelty=sb.get("novelty", 0),
                        feasibility=sb.get("feasibility", 0),
                        market_potential=sb.get("market_potential", 0)
                    ),
                    evaluator_explain=idea_dict.get("evaluator_explain", ""),
                )
                ideas.append(idea)
            
            return {
                "run_task_id": self.config.run_task_id,
                "iteration_number": iteration_number,
                "ideas": [idea.to_dict() for idea in ideas],
            }

        elif stage == Stage.LEARNER:
            critic_data = get_knowledge(
                self.db_path,
                self.config.run_task_id,
                f"critic_output_{iteration_number}",
            )
            evaluator_data = get_knowledge(
                self.db_path,
                self.config.run_task_id,
                f"evaluator_output_{iteration_number}",
            )
            if not evaluator_data:
                print("No evaluator output found")
                return None

            if critic_data:
                ideas = critic_data.get("vetted_ideas", [])
            else:
                ideas = evaluator_data.get("ideas", [])
            
            scores = get_iteration_scores(self.db_path, self.config.run_task_id)
            avg_score = 0.0
            for s in scores:
                if s.get("iteration_number") == iteration_number:
                    avg_score = s.get("avg_score", 0.0) or 0.0
                    break
            
            return {
                "run_task_id": self.config.run_task_id,
                "iteration_number": iteration_number,
                "ideas": ideas,
                "avg_score": avg_score,
            }
        
        return None
    
    def _execute_agent(
        self,
        stage: str,
        payload: dict[str, Any],
        iteration_number: int,
    ) -> Optional[dict[str, Any]]:
        """Execute the appropriate agent for a stage."""
        stage_enum = Stage(stage) if stage in [s.value for s in Stage] else None
        if not stage_enum:
            print(f"Unknown stage: {stage}")
            return None
        agent = self.agents.get(stage_enum)
        if not agent:
            print(f"Unknown stage: {stage}")
            return None
        
        print(f"  Executing {stage} agent...")

        try:
            if stage_enum == Stage.PLANNER:
                result = agent.plan(PlannerInput(**payload))
                result_dict = result.to_dict()
                set_knowledge(
                    self.db_path,
                    self.config.run_task_id,
                    f"planner_output_{iteration_number}",
                    result_dict,
                )
                print(f"  Generated {len(result.search_queries)} search queries")
                return result_dict

            elif stage_enum == Stage.RESEARCHER:
                result = asyncio.run(agent.research(ResearcherInput(**payload)))
                result_dict = result.to_dict()
                set_knowledge(
                    self.db_path,
                    self.config.run_task_id,
                    f"researcher_output_{iteration_number}",
                    result_dict,
                )
                print(f"  Found {len(result.candidate_urls)} candidate URLs")
                return result_dict

            elif stage_enum == Stage.SCRAPER:
                result = asyncio.run(agent.scrape(ScraperInput(**payload)))
                result_dict = result.to_dict()
                set_knowledge(
                    self.db_path,
                    self.config.run_task_id,
                    f"scraper_output_{iteration_number}",
                    result_dict,
                )
                print(f"  Extracted {len(result.extracted)} items (quality: {result.scrape_quality:.2f})")
                return result_dict

            elif stage_enum == Stage.EVALUATOR:
                result = asyncio.run(agent.evaluate(EvaluatorInput(**payload)))
                result_dict = result.to_dict()

                store_ideas(
                    self.db_path,
                    self.config.run_task_id,
                    iteration_number,
                    result_dict.get("ideas", []),
                )

                set_knowledge(
                    self.db_path,
                    self.config.run_task_id,
                    f"evaluator_output_{iteration_number}",
                    result_dict,
                )
                print(f"  Evaluated {len(result.ideas)} ideas")
                return result_dict

            elif stage_enum == Stage.CRITIC:
                result = asyncio.run(agent.vet(CriticInput(**payload)))
                result_dict = result.to_dict()

                set_knowledge(
                    self.db_path,
                    self.config.run_task_id,
                    f"critic_output_{iteration_number}",
                    result_dict,
                )
                print(f"  Vetted {len(result.vetted_ideas)} ideas")
                return result_dict

            elif stage_enum == Stage.LEARNER:
                result = agent.learn(LearnerInput(**payload))
                result_dict = result.to_dict()
                
                # Store validation
                store_validation(
                    self.db_path,
                    self.config.run_task_id,
                    iteration_number,
                    result.validation_score,
                    result.validation_explain,
                )
                
                # Update knowledge
                set_knowledge(
                    self.db_path,
                    self.config.run_task_id,
                    f"learner_output_{iteration_number}",
                    result_dict,
                )
                
                # Update accumulated knowledge
                accumulated = get_knowledge(
                    self.db_path,
                    self.config.run_task_id,
                    "accumulated_knowledge"
                ) or {}
                accumulated.update(result.knowledge_updates)
                set_knowledge(
                    self.db_path,
                    self.config.run_task_id,
                    "accumulated_knowledge",
                    accumulated,
                )
                
                print(f"  Validation score: {result.validation_score:.2f}")
                print(f"  Did improve: {result.did_improve}")
                print(f"  Next action: {result.next_highest_value_action}")
                return result_dict
        
        except Exception as e:
            print(f"  Agent execution failed: {e}")
            raise
        
        return None
    
    def _check_plateau(self) -> bool:
        """Check if scores have plateaued."""
        scores = get_iteration_scores(self.db_path, self.config.run_task_id)
        
        if len(scores) < self.config.plateau_window + 1:
            return False
        
        # Get last N iterations with scores
        scored_iterations = [s for s in scores if s.get("avg_score") is not None]
        if len(scored_iterations) < self.config.plateau_window + 1:
            return False
        
        # Check improvement over the plateau window
        recent = scored_iterations[-self.config.plateau_window:]
        previous = scored_iterations[-(self.config.plateau_window + 1):-1]
        
        recent_avg = sum(s["avg_score"] for s in recent) / len(recent)
        previous_avg = sum(s["avg_score"] for s in previous) / len(previous)
        
        improvement = recent_avg - previous_avg
        
        print(f"  Plateau check: recent_avg={recent_avg:.2f}, previous_avg={previous_avg:.2f}, improvement={improvement:.2f}")
        
        return improvement <= self.config.min_improvement
    
    def _load_accumulated_ideas(self) -> list[dict[str, Any]]:
        """Load accumulated ideas from database (non-merged ideas sorted by score)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                """
                SELECT
                  idea_id,
                  iteration_number,
                  source_urls,
                  idea_title,
                  idea_summary,
                  idea_payload,
                  score,
                  score_breakdown,
                  evaluator_explain
                FROM ideas
                WHERE canonical_idea_id IS NULL
                ORDER BY score DESC, iteration_number ASC
                """
            ).fetchall()

            ideas: list[dict[str, Any]] = []
            for r in rows:
                idea = {
                    "idea_id": int(r["idea_id"]),
                    "iteration_number": int(r["iteration_number"]),
                    "source_urls": json.loads(r["source_urls"]),
                    "idea_title": r["idea_title"],
                    "idea_summary": r["idea_summary"],
                    "idea_payload": json.loads(r["idea_payload"]),
                    "score": float(r["score"]),
                    "score_breakdown": json.loads(r["score_breakdown"]) if r["score_breakdown"] else {},
                    "evaluator_explain": r["evaluator_explain"],
                }
                ideas.append(idea)
            return ideas
        except sqlite3.Error as e:
            self.logger.error(f"Database error in _load_accumulated_ideas: {e}")
            return []
        finally:
            conn.close()
    
    def _merge_ideas(
        self, existing: list[dict[str, Any]], new: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Merge new ideas with existing, deduplicating by title (keep highest score)."""
        ideas_by_title: dict[str, dict[str, Any]] = {}
        
        for idea in existing:
            title = idea.get("idea_title", "").lower()
            if title:
                if title not in ideas_by_title or idea.get("score", 0) > ideas_by_title[title].get("score", 0):
                    ideas_by_title[title] = idea
        
        for idea in new:
            title = idea.get("idea_title", "").lower()
            if title:
                if title not in ideas_by_title or idea.get("score", 0) > ideas_by_title[title].get("score", 0):
                    ideas_by_title[title] = idea
        
        merged = list(ideas_by_title.values())
        merged.sort(key=lambda x: x.get("score", 0), reverse=True)
        return merged
    
    def _finalize(self) -> None:
        """Finalize the run and generate outputs."""
        print(f"\n{'='*60}")
        print("Finalizing run...")
        print(f"{'='*60}")
        
        new_ideas = get_top_ideas(self.db_path, self.config.run_task_id, limit=20)
        
        existing_ideas = self._load_accumulated_ideas()
        if existing_ideas:
            print(f"  Loaded {len(existing_ideas)} accumulated ideas from database")
            all_ideas = self._merge_ideas(existing_ideas, new_ideas)
        else:
            all_ideas = new_ideas
        
        top_ideas = all_ideas[:20]
        print(f"  Merged total: {len(all_ideas)} ideas, keeping top {len(top_ideas)}")
        
        emb_count = generate_embeddings_for_run(self.db_path, self.config.run_task_id)
        print(f"  Generated embeddings for {emb_count} ideas")
        
        merge_count = merge_duplicate_ideas(self.db_path)
        if merge_count > 0:
            print(f"  Merged {merge_count} duplicate ideas")
        
        stats = get_idea_stats(self.db_path)
        record_accumulated_knowledge(
            db_path=self.db_path,
            total_ideas=stats["total_ideas"],
            unique_ideas=stats["unique_ideas"],
            merged_ideas=stats["merged_ideas"],
        )
        print(f"  Recorded accumulated knowledge: {stats['total_ideas']} total, {stats['unique_ideas']} unique, {stats['merged_ideas']} merged")
        
        print(f"\nRun complete! Found {len(top_ideas)} top ideas (stored in DB).")
