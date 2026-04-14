"""Scout agent - discovers signals from the web using LLM with built-in search."""

from __future__ import annotations

from collections import Counter
import hashlib
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Signal, SignalRelation
from utils.embeddings import cosine_similarity, text_to_embedding
from utils.llm_client import LLMError, async_llm_complete_json
from utils.logger import get_logger
from utils.prompts_utils import load_prompt

logger = get_logger(__name__)
_MAX_PER_DOMAIN = 2
_NOVELTY_SIM_THRESHOLD = 0.92
_DIVERSITY_SIM_THRESHOLD = 0.90

_QUERY_ROTATIONS = [
    [
        "recent app frustrations by niche profession",
        "i tried workaround but still painful app problem",
        "mobile app pain points for caregivers, parents, students",
        "watchOS iOS desktop app complaints last 30 days",
    ],
    [
        "underserved accessibility app frustrations",
        "regional/local service app pain points",
        "what app fails at daily routines 2026",
        "forum complaints app churn reason",
    ],
    [
        "post-update regressions in popular apps",
        "unmet needs in offline-first mobile workflows",
        "friction in notifications/reminders apps",
        "power-user complaints missing advanced controls",
    ],
]


def _signal_metadata_from_llm(signal_data: dict) -> dict:
    """Keep only structured metadata fields that help later monetization analysis."""
    allowed_keys = {
        "payment_context",
        "current_spend_or_workaround",
        "urgency",
        "score",
        "relevance",
        "strength",
    }
    out: dict = {}
    for key in allowed_keys:
        value = signal_data.get(key)
        if value in (None, "", []):
            continue
        out[key] = value
    return out


def _normalize_memory_key(text: str) -> str:
    """Create a compact, comparable key for scout memory lookups."""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    tokens = [t for t in cleaned.split() if len(t) > 2]
    return " ".join(tokens[:24])


def _build_memory_context(previous_signals: list[Signal], max_items: int = 12) -> str:
    """Summarize scout history so prompt context stays small."""
    if not previous_signals:
        return "No prior scout memory."

    type_counts = Counter(s.signal_type for s in previous_signals if s.signal_type)
    latest = list(reversed(previous_signals[-max_items:]))
    lines = [
        (
            "Existing scout memory (avoid repeating these unless you have materially "
            "new evidence):"
        ),
        "Signal counts by type: "
        + ", ".join(f"{k}={v}" for k, v in sorted(type_counts.items())),
    ]

    for signal in latest:
        source_suffix = f" ({signal.source_url})" if signal.source_url else ""
        lines.append(f"- [{signal.signal_type}] {signal.content[:120]}{source_suffix}")

    return "\n".join(lines)


def _infer_domain(text: str) -> str:
    lowered = text.lower()
    rules = [
        ("health_fitness", ["workout", "fitness", "health", "sleep", "nutrition"]),
        ("logistics", ["route", "delivery", "shipment", "customs", "dispatch"]),
        ("productivity", ["calendar", "notes", "email", "task", "reminder"]),
        ("social_communication", ["reddit", "twitter", "dm", "message", "social"]),
        ("wearables", ["watch", "wearable", "apple watch", "hrv"]),
        ("finance", ["subscription", "billing", "invoice", "payment", "budget"]),
    ]
    for domain, keywords in rules:
        if any(k in lowered for k in keywords):
            return domain
    return "general"


def _stable_hash(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


class ScoutAgent:
    """Agent 1: Discovers signals from web using LLM with built-in search."""

    def __init__(self, batch_size: int = 5, portfolio_guidance: str | None = None):
        self.batch_size = batch_size
        self.portfolio_guidance = (portfolio_guidance or "").strip()

    async def run(self, session: AsyncSession) -> list[Signal]:
        """Run scout to discover signals using LLM with web search."""
        prompt_template = load_prompt("scout.md")
        prior_rows = await session.execute(select(Signal).order_by(Signal.id))
        previous_signals = prior_rows.scalars().all()
        memory_context = _build_memory_context(previous_signals)
        rotation_index = len(previous_signals) % len(_QUERY_ROTATIONS)
        rotation_queries = "\n".join(
            f"- {q}" for q in _QUERY_ROTATIONS[rotation_index]
        )
        prompt = (
            f"{prompt_template}\n\n"
            "## Run-specific search focus\n"
            "Use these additional query angles this run to increase variability:\n"
            f"{rotation_queries}\n\n"
            "Diversity rule: avoid returning more than 2 signals from the same "
            "problem domain.\n\n"
            + (
                f"## Portfolio Guidance\n{self.portfolio_guidance}\n\n"
                if self.portfolio_guidance
                else ""
            )
            + f"## Memory\n{memory_context}"
        )

        try:
            result = await async_llm_complete_json(
                prompt,
                max_tokens=4000,
                temperature=0.7,
                agent_name="scout",
            )
        except LLMError as e:
            logger.warning(
                "Scout primary LLM call failed; retrying with reduced budget: %s",
                e,
            )
            try:
                result = await async_llm_complete_json(
                    prompt,
                    max_tokens=2500,
                    temperature=0.6,
                    agent_name="scout",
                )
            except LLMError as retry_error:
                logger.error(
                    "Scout failed after fallback retry; "
                    "continuing with zero signals: %s",
                    retry_error,
                )
                return []
        signals_data = result if isinstance(result, list) else result.get("signals", [])

        logger.info("Found %d signals", len(signals_data))

        existing_vectors = {
            s.id: text_to_embedding(s.content) for s in previous_signals
        }
        existing_keys = {_normalize_memory_key(s.content) for s in previous_signals}

        candidates: list[tuple[dict, list[float], str]] = []
        for sd in signals_data:
            content = sd.get("content", "")[:200]
            if not content:
                continue

            normalized = _normalize_memory_key(content)
            if normalized in existing_keys:
                logger.info("Skipping duplicate scout signal by key: %s", content[:80])
                continue

            candidate_vector = text_to_embedding(content)
            duplicate_found = False
            for existing_vector in existing_vectors.values():
                if (
                    cosine_similarity(candidate_vector, existing_vector)
                    >= _NOVELTY_SIM_THRESHOLD
                ):
                    duplicate_found = True
                    break

            if duplicate_found:
                logger.info(
                    "Skipping duplicate scout signal by embedding: %s",
                    content[:80],
                )
                continue
            candidates.append((sd, candidate_vector, normalized))

        all_signals = []
        selected_vectors: list[list[float]] = []
        domain_counts: Counter[str] = Counter()
        # Stable ordering with deterministic hash and content novelty tie-break.
        candidates.sort(
            key=lambda row: _stable_hash(row[0].get("content", "")),
        )
        for sd, candidate_vector, normalized in candidates:
            content = sd.get("content", "")[:200]
            domain = _infer_domain(content)
            if domain_counts[domain] >= _MAX_PER_DOMAIN:
                logger.info(
                    "Skipping due to domain quota (%s): %s",
                    domain,
                    content[:80],
                )
                continue
            too_close_to_selected = any(
                cosine_similarity(candidate_vector, v) >= _DIVERSITY_SIM_THRESHOLD
                for v in selected_vectors
            )
            if too_close_to_selected:
                logger.info("Skipping low-diversity candidate: %s", content[:80])
                continue
            signal = Signal(
                content=content,
                source_url=sd.get("source_context", ""),
                signal_type=sd.get("signal_type", "problem_statement"),
                signal_metadata=_signal_metadata_from_llm(sd),
            )
            session.add(signal)
            all_signals.append(signal)
            existing_keys.add(normalized)
            existing_vectors[-len(existing_vectors) - 1] = candidate_vector
            selected_vectors.append(candidate_vector)
            domain_counts[domain] += 1

        await session.flush()

        vectors = {s.id: text_to_embedding(s.content) for s in all_signals}
        for i, s1 in enumerate(all_signals):
            for s2 in all_signals[i + 1 :]:
                sim = cosine_similarity(vectors[s1.id], vectors[s2.id])
                if sim >= 0.95 or s1.signal_type == s2.signal_type:
                    relation_type = "similar_to" if sim >= 0.95 else "category_match"
                    session.add(
                        SignalRelation(
                            from_signal_id=s1.id,
                            to_signal_id=s2.id,
                            relation_type=relation_type,
                            similarity=float(sim),
                            relation_metadata={
                                "heuristic": "content_similarity_or_type",
                            },
                        ),
                    )

        await session.commit()
        return all_signals
