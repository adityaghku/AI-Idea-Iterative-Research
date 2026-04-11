"""Librarian agent - embedding-based dedupe and graph edge management with LLM."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Idea, IdeaEmbedding, IdeaRelation
from utils.embeddings import (
    EMBEDDING_MODEL_NAME,
    EMBEDDING_MODEL_VERSION,
    cosine_similarity,
    idea_to_text,
    text_to_embedding,
)
from utils.llm_client import async_llm_complete_json
from utils.logger import get_logger
from utils.prompts_utils import load_prompt

logger = get_logger(__name__)


class LibrarianAgent:
    """Agent 6: Deduplicates ideas with embeddings + LLM decisions."""

    def __init__(self, threshold: float = 0.7):
        self.threshold = threshold

    async def run(self, session: AsyncSession) -> dict:
        """Run librarian to dedupe ideas and finalize statuses."""

        result = await session.execute(
            select(Idea).where(Idea.is_active == True).order_by(Idea.id)
        )
        ideas = result.scalars().all()
        await session.execute(delete(IdeaRelation))
        logger.info("Processing %d ideas with embedding threshold=%s", len(ideas), self.threshold)

        embeddings_by_idea: dict[int, list[float]] = {}
        for idea in ideas:
            embedding_row = await session.scalar(
                select(IdeaEmbedding).where(IdeaEmbedding.idea_id == idea.id)
            )
            if embedding_row:
                embeddings_by_idea[idea.id] = embedding_row.vector
                continue

            text = idea_to_text(
                idea.title, idea.problem, idea.target_user, idea.solution
            )
            vector = text_to_embedding(text)
            session.add(
                IdeaEmbedding(
                    idea_id=idea.id,
                    vector=vector,
                    model_name=EMBEDDING_MODEL_NAME,
                    model_version=EMBEDDING_MODEL_VERSION,
                )
            )
            embeddings_by_idea[idea.id] = vector

        await session.flush()

        potential_pairs = []
        for i, source in enumerate(ideas):
            if not source.is_active:
                continue
            for target in ideas[i + 1:]:
                if not target.is_active:
                    continue

                sim = cosine_similarity(
                    embeddings_by_idea[source.id], embeddings_by_idea[target.id]
                )

                relation_type = "similar_to"
                if sim >= self.threshold:
                    potential_pairs.append({
                        "pair_index": len(potential_pairs),
                        "source": source,
                        "target": target,
                        "similarity": sim,
                    })
                    relation_type = "potential_duplicate"

                session.add(
                    IdeaRelation(
                        from_idea_id=source.id,
                        to_idea_id=target.id,
                        relation_type=relation_type,
                        similarity=float(sim),
                        relation_metadata={"threshold": self.threshold},
                    )
                )

        logger.info("Found %d potential duplicate pairs for LLM review", len(potential_pairs))
        if potential_pairs:
            logger.info(
                "Librarian duplicate review will evaluate idea pairs: %s",
                ", ".join(
                    f"{p['source'].id}-{p['target'].id}" for p in potential_pairs[:10]
                ),
            )

        merge_count = 0
        drop_count = 0

        if potential_pairs:
            decisions = await self._get_llm_decisions(potential_pairs)
            logger.info("Librarian received %d LLM dedupe decisions", len(decisions))
            merge_count, drop_count = await self._apply_decisions(
                session=session,
                decisions=decisions,
                potential_pairs=potential_pairs,
            )

        for idea in ideas:
            if idea.is_active:
                idea.status = "finalized"

        await session.commit()

        logger.info("Merged %d, dropped %d duplicates", merge_count, drop_count)
        return {
            "merged_count": merge_count,
            "dropped_count": drop_count,
            "total_ideas": len(ideas),
            "potential_pairs": len(potential_pairs),
            "threshold": self.threshold,
        }

    async def _get_llm_decisions(self, pairs: list[dict]) -> list[dict]:
        """Send potential duplicate pairs to LLM for merge decisions."""
        prompt_template = load_prompt("librarian.md")

        pair_texts = []
        for i, pair in enumerate(pairs):
            s = pair["source"]
            t = pair["target"]
            sim = pair["similarity"]
            pair_texts.append(f"""
Pair {i + 1} (pair_index: {i}, similarity: {sim:.2f}):

Idea A (ID: {s.id}):
- Title: {s.title}
- Problem: {s.problem}
- Target User: {s.target_user}
- Solution: {s.solution}

Idea B (ID: {t.id}):
- Title: {t.title}
- Problem: {t.problem}
- Target User: {t.target_user}
- Solution: {t.solution}
""")

        prompt = f"""{prompt_template}

Review the following {len(pairs)} potential duplicate pairs:

{''.join(pair_texts)}

Output your decisions as a JSON array with one entry per pair.
"""

        try:
            result = await async_llm_complete_json(prompt, max_tokens=4000, temperature=0.3)
            if isinstance(result, list):
                return result
            logger.warning("LLM returned non-list result: %s", type(result))
            return []
        except Exception as e:
            logger.error("Failed to get LLM decisions: %s", e)
            return []

    async def _refresh_embedding(self, session: AsyncSession, idea: Idea) -> None:
        """Refresh embedding when merged content changes."""
        text = idea_to_text(idea.title, idea.problem, idea.target_user, idea.solution)
        vector = text_to_embedding(text)
        embedding_row = await session.scalar(
            select(IdeaEmbedding).where(IdeaEmbedding.idea_id == idea.id)
        )
        if embedding_row:
            embedding_row.vector = vector
            embedding_row.model_name = EMBEDDING_MODEL_NAME
            embedding_row.model_version = EMBEDDING_MODEL_VERSION
            return
        session.add(
            IdeaEmbedding(
                idea_id=idea.id,
                vector=vector,
                model_name=EMBEDDING_MODEL_NAME,
                model_version=EMBEDDING_MODEL_VERSION,
            )
        )

    async def _apply_decisions(
        self,
        session: AsyncSession,
        decisions: list[dict],
        potential_pairs: list[dict],
    ) -> tuple[int, int]:
        """Apply LLM dedupe decisions to the concrete pair set."""
        merge_count = 0
        drop_count = 0
        used_pair_indices: set[int] = set()

        for decision in decisions:
            action = decision.get("action", "keep_separate")
            pair_index = decision.get("pair_index")
            if not isinstance(pair_index, int):
                logger.warning("Skipping decision without integer pair_index: %s", decision)
                continue
            if pair_index < 0 or pair_index >= len(potential_pairs):
                logger.warning("Skipping decision with out-of-range pair_index: %s", pair_index)
                continue
            if pair_index in used_pair_indices:
                logger.warning("Skipping duplicate decision for pair_index=%d", pair_index)
                continue

            pair = potential_pairs[pair_index]
            source_idea = pair["source"]
            target_idea = pair["target"]
            pair_idea_ids = {source_idea.id, target_idea.id}
            if not source_idea.is_active or not target_idea.is_active:
                logger.info(
                    "Skipping pair_index=%d because one or both ideas already inactive",
                    pair_index,
                )
                continue

            if action == "merge":
                keep_id = decision.get("keep_idea_id")
                if keep_id not in pair_idea_ids:
                    logger.warning(
                        "Skipping merge for pair_index=%d due to invalid keep_idea_id=%s",
                        pair_index,
                        keep_id,
                    )
                    continue
                keep_idea = source_idea if source_idea.id == keep_id else target_idea
                drop_idea = target_idea if keep_idea is source_idea else source_idea

                keep_idea.title = decision.get("merged_title", keep_idea.title)
                keep_idea.problem = decision.get("merged_problem", keep_idea.problem)
                keep_idea.target_user = decision.get("merged_target_user", keep_idea.target_user)
                keep_idea.solution = decision.get("merged_solution", keep_idea.solution)
                drop_idea.is_active = False
                drop_idea.is_duplicate = True
                drop_idea.merged_into_id = keep_idea.id
                await self._refresh_embedding(session, keep_idea)
                merge_count += 1
                used_pair_indices.add(pair_index)
                logger.info("Merged idea %d into %d: %s", drop_idea.id, keep_idea.id, keep_idea.title)

            elif action == "drop":
                keep_id = decision.get("keep_idea_id")
                drop_id = decision.get("drop_idea_id")
                if keep_id not in pair_idea_ids or drop_id not in pair_idea_ids or keep_id == drop_id:
                    logger.warning(
                        "Skipping drop for pair_index=%d due to invalid keep/drop ids: keep=%s drop=%s",
                        pair_index,
                        keep_id,
                        drop_id,
                    )
                    continue
                keep_idea = source_idea if source_idea.id == keep_id else target_idea
                drop_idea = source_idea if source_idea.id == drop_id else target_idea
                if not keep_idea.is_active or not drop_idea.is_active:
                    logger.info("Skipping drop for pair_index=%d because ideas changed state", pair_index)
                    continue
                drop_idea.is_active = False
                drop_idea.is_duplicate = True
                drop_idea.merged_into_id = keep_idea.id
                drop_count += 1
                used_pair_indices.add(pair_index)
                logger.info("Dropped idea %d, keeping %d", drop_idea.id, keep_idea.id)
            else:
                used_pair_indices.add(pair_index)

        return merge_count, drop_count