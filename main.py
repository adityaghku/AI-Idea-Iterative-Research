#!/usr/bin/env python3
"""Main entry point for the 6-agent idea pipeline."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv

    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

from agents.analyser import AnalyserAgent
from agents.critic import CriticAgent
from agents.deep_dive import DeepDiveAgent
from agents.librarian import LibrarianAgent
from agents.portfolio import PortfolioAgent
from agents.scout import ScoutAgent
from agents.synthesizer import SynthesizerAgent
from db import AgentRun, Idea, PipelineRun, PortfolioMemory, close_db, get_session, init_db
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.logger import get_logger

logger = get_logger(__name__)


def _analysis_value(idea: Idea, field: str) -> int:
    analysis = getattr(idea, "analysis", None)
    value = getattr(analysis, field, None) if analysis else None
    return int(value) if isinstance(value, (int, float)) else 0


def select_deep_dive_candidates(
    ideas: list[Idea], max_candidates: int = 3
) -> list[Idea]:
    """Prioritize ideas with monetization gaps first, then strongest business scores."""
    ranked = sorted(
        ideas,
        key=lambda idea: (
            1
            if getattr(getattr(idea, "analysis", None), "monetization_potential", None)
            == "unknown"
            else 0,
            (
                3 * _analysis_value(idea, "monetization_score")
                + 2 * _analysis_value(idea, "validation_score")
                + 2 * _analysis_value(idea, "demand_score")
                + _analysis_value(idea, "gtm_score")
                + _analysis_value(idea, "score")
            ),
            _analysis_value(idea, "score"),
            -int(getattr(idea, "id", 0) or 0),
        ),
        reverse=True,
    )
    return ranked[:max_candidates]


async def _load_portfolio_guidance(session) -> str:
    latest = await session.scalar(
        select(PortfolioMemory).order_by(PortfolioMemory.id.desc())
    )
    if not latest:
        return ""
    return (
        latest.synthesizer_guidance
        or latest.scout_guidance
        or latest.analyser_guidance
        or latest.summary
        or ""
    )


def _summarize_result(result) -> str:
    if isinstance(result, list):
        return f"{len(result)} item(s)"
    if isinstance(result, dict):
        return ", ".join(f"{k}={v}" for k, v in list(result.items())[:6])
    return str(result)


async def _start_pipeline_run(session, iteration: int) -> PipelineRun:
    run = PipelineRun(iteration=iteration, status="running", config_json={"iteration": iteration})
    session.add(run)
    await session.flush()
    return run


async def _run_agent_step(
    session,
    pipeline_run: PipelineRun,
    agent_name: str,
    prompt_name: str,
    input_summary: str,
    runner,
):
    agent_run = AgentRun(
        pipeline_run_id=pipeline_run.id,
        agent_name=agent_name,
        prompt_name=prompt_name,
        status="running",
        input_summary=input_summary,
    )
    session.add(agent_run)
    await session.flush()
    try:
        result = await runner()
        agent_run.status = "completed"
        agent_run.output_summary = _summarize_result(result)
        agent_run.completed_at = datetime.utcnow()
        await session.commit()
        return result
    except Exception as exc:
        agent_run.status = "failed"
        agent_run.error_text = str(exc)
        agent_run.completed_at = datetime.utcnow()
        await session.commit()
        raise


async def run_pipeline(iteration: int):
    """Run the full 6-agent pipeline."""
    logger.info("=== Starting Idea Pipeline (iteration %d) ===", iteration)

    await init_db()
    session = await get_session()

    try:
        pipeline_run = await _start_pipeline_run(session, iteration)
        portfolio_guidance = await _load_portfolio_guidance(session)

        logger.info("Step 1: Scout - Discovering signals...")
        scout = ScoutAgent(batch_size=5, portfolio_guidance=portfolio_guidance)
        signals = await _run_agent_step(
            session,
            pipeline_run,
            "scout",
            "scout.md",
            "discover fresh monetizable problem signals",
            lambda: scout.run(session),
        )
        logger.info("Scout complete: %d signals", len(signals))

        if not signals:
            logger.warning("No signals found. Exiting.")
            pipeline_run.status = "completed"
            pipeline_run.completed_at = datetime.utcnow()
            await session.commit()
            return

        logger.info("Step 2: Synthesizer - Converting signals to ideas...")
        synthesizer = SynthesizerAgent(portfolio_guidance=portfolio_guidance)
        ideas = await _run_agent_step(
            session,
            pipeline_run,
            "synthesizer",
            "synthesizer.md",
            f"{len(signals)} signals",
            lambda: synthesizer.run(session, signals),
        )
        logger.info("Synthesizer complete: %d ideas", len(ideas))

        if not ideas:
            logger.error("No ideas generated. Pipeline failed.")
            raise RuntimeError("Synthesizer produced no ideas")

        logger.info("Step 3: Analyser - Scoring ideas...")
        analyser = AnalyserAgent(portfolio_guidance=portfolio_guidance)
        analyses = await _run_agent_step(
            session,
            pipeline_run,
            "analyser",
            "analyser.md",
            f"{len(ideas)} ideas",
            lambda: analyser.run(session, ideas),
        )
        logger.info("Analyser complete: %d analyses", len(analyses))

        idea_ids = [i.id for i in ideas]
        current_ideas_stmt = (
            select(Idea)
            .where(Idea.id.in_(idea_ids))
            .options(selectinload(Idea.analysis))
        )
        current_ideas = (await session.execute(current_ideas_stmt)).scalars().all()

        top_ideas = select_deep_dive_candidates(current_ideas, max_candidates=3)
        logger.info(
            "Deep Dive candidate selection: selected=%d (%s)",
            len(top_ideas),
            ", ".join(f"{i.id}:{i.title}" for i in top_ideas),
        )

        logger.info("Step 4: Deep Dive - Enriching top ideas...")
        deep_dive = DeepDiveAgent()
        try:
            enrichments = await _run_agent_step(
                session,
                pipeline_run,
                "deep_dive",
                "deep_dive.md",
                f"{len(top_ideas)} ideas",
                lambda: asyncio.wait_for(deep_dive.run(session, top_ideas), timeout=900),
            )
        except asyncio.TimeoutError:
            logger.error("Deep Dive timed out after 900s - this step involves web searches which can take time")
            raise
        logger.info("Deep Dive complete: %d enrichments", len(enrichments))

        logger.info("Step 5: Critic - Critiquing enriched ideas...")
        critic = CriticAgent()
        top_idea_ids = [i.id for i in top_ideas]
        stmt = select(Idea).where(Idea.id.in_(top_idea_ids)).options(
            selectinload(Idea.analysis),
            selectinload(Idea.enrichment)
        )
        critic_ideas = (await session.execute(stmt)).scalars().all()
        logger.info("Critic input ideas prepared: %d", len(critic_ideas))
        critiques = await _run_agent_step(
            session,
            pipeline_run,
            "critic",
            "critic.md",
            f"{len(critic_ideas)} enriched ideas",
            lambda: critic.run(session, critic_ideas),
        )
        logger.info("Critic complete: %d critiques", len(critiques))

        logger.info("Step 6: Librarian - Deduplicating...")
        librarian = LibrarianAgent(threshold=0.7)
        result = await _run_agent_step(
            session,
            pipeline_run,
            "librarian",
            "librarian.md",
            "deduplicate active ideas",
            lambda: librarian.run(session),
        )
        logger.info("Librarian complete: %s", result)

        logger.info("Step 7: Portfolio - Learning from feedback...")
        portfolio = PortfolioAgent()
        memory = await _run_agent_step(
            session,
            pipeline_run,
            "portfolio",
            "portfolio:heuristic-feedback-summary",
            "feedback events and recent outcomes",
            lambda: portfolio.run(session, pipeline_run.id),
        )
        logger.info("Portfolio complete: %s", _summarize_result(memory))

        logger.info("=== Pipeline complete (iteration %d) ===", iteration)
        pipeline_run.status = "completed"
        pipeline_run.completed_at = datetime.utcnow()
        await session.commit()

        final_stmt = select(Idea).where(Idea.is_active == True).order_by(Idea.id.desc()).limit(10)
        final_ideas = (await session.execute(final_stmt)).scalars().all()
        
        final_ids = [i.id for i in final_ideas]
        final_stmt = select(Idea).where(Idea.id.in_(final_ids)).options(selectinload(Idea.analysis))
        final_ideas = (await session.execute(final_stmt)).scalars().all()
        
        logger.info("Top Ideas:")
        for idea in final_ideas:
            score = idea.analysis.score if idea.analysis else 0
            logger.info("  - %s (score: %d)", idea.title, score)

    finally:
        await session.close()


def main():
    parser = argparse.ArgumentParser(description="Run the 6-agent idea pipeline")
    parser.add_argument(
        "-n",
        "--max-iterations",
        type=int,
        default=1,
        help="Maximum number of pipeline iterations to run (default: 1)",
    )
    args = parser.parse_args()

    logger.info("Running pipeline with max_iterations=%d", args.max_iterations)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        for i in range(1, args.max_iterations + 1):
            loop.run_until_complete(run_pipeline(i))
            if i < args.max_iterations:
                logger.info("Sleeping before next iteration...")
                loop.run_until_complete(asyncio.sleep(2))
    finally:
        loop.run_until_complete(close_db())
        loop.close()

    logger.info("All %d iteration(s) complete!", args.max_iterations)


if __name__ == "__main__":
    main()
