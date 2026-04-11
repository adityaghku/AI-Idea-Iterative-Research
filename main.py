#!/usr/bin/env python3
"""Main entry point for the 6-agent idea pipeline."""
from __future__ import annotations

import argparse
import asyncio
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
from agents.scout import ScoutAgent
from agents.synthesizer import SynthesizerAgent
from db import Idea, get_session, init_db, close_db
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from utils.logger import get_logger

logger = get_logger(__name__)


async def run_pipeline(iteration: int):
    """Run the full 6-agent pipeline."""
    logger.info("=== Starting Idea Pipeline (iteration %d) ===", iteration)

    await init_db()
    session = await get_session()

    try:
        logger.info("Step 1: Scout - Discovering signals...")
        scout = ScoutAgent(batch_size=5)
        signals = await scout.run(session)
        logger.info("Scout complete: %d signals", len(signals))

        if not signals:
            logger.warning("No signals found. Exiting.")
            return

        logger.info("Step 2: Synthesizer - Converting signals to ideas...")
        synthesizer = SynthesizerAgent()
        ideas = await synthesizer.run(session, signals)
        logger.info("Synthesizer complete: %d ideas", len(ideas))

        if not ideas:
            logger.error("No ideas generated. Pipeline failed.")
            raise RuntimeError("Synthesizer produced no ideas")

        logger.info("Step 3: Analyser - Scoring ideas...")
        analyser = AnalyserAgent()
        analyses = await analyser.run(session, ideas)
        logger.info("Analyser complete: %d analyses", len(analyses))

        idea_ids = [i.id for i in ideas]
        current_ideas_stmt = (
            select(Idea)
            .where(Idea.id.in_(idea_ids))
            .options(selectinload(Idea.analysis))
        )
        current_ideas = (await session.execute(current_ideas_stmt)).scalars().all()

        fallback_stmt = (
            select(Idea)
            .where(Idea.is_active == True)
            .options(selectinload(Idea.analysis))
        )
        all_active_ideas = (await session.execute(fallback_stmt)).scalars().all()
        fallback_candidates = sorted(
            [
                i
                for i in all_active_ideas
                if i.analysis is None or i.analysis.monetization_potential == "unknown"
            ],
            key=lambda i: i.id,
        )

        score_sorted_current = sorted(
            current_ideas,
            key=lambda i: i.analysis.score if i.analysis else 0,
            reverse=True,
        )

        top_ideas: list[Idea] = []
        seen_ids: set[int] = set()
        for candidate in fallback_candidates + score_sorted_current:
            if candidate.id in seen_ids:
                continue
            top_ideas.append(candidate)
            seen_ids.add(candidate.id)
            if len(top_ideas) >= 3:
                break
        logger.info(
            "Deep Dive candidate selection: fallback=%d scored=%d selected=%d (%s)",
            len(fallback_candidates),
            len(score_sorted_current),
            len(top_ideas),
            ", ".join(f"{i.id}:{i.title}" for i in top_ideas),
        )

        logger.info("Step 4: Deep Dive - Enriching top ideas...")
        deep_dive = DeepDiveAgent()
        try:
            enrichments = await asyncio.wait_for(deep_dive.run(session, top_ideas), timeout=900)
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
        critiques = await critic.run(session, critic_ideas)
        logger.info("Critic complete: %d critiques", len(critiques))

        logger.info("Step 6: Librarian - Deduplicating...")
        librarian = LibrarianAgent(threshold=0.7)
        result = await librarian.run(session)
        logger.info("Librarian complete: %s", result)

        logger.info("=== Pipeline complete (iteration %d) ===", iteration)

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
