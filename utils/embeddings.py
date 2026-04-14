"""Deterministic local embeddings utilities for idea deduplication."""

from __future__ import annotations

import hashlib
import math
from typing import Iterable


EMBEDDING_DIM = 256
EMBEDDING_MODEL_NAME = "hashing"
EMBEDDING_MODEL_VERSION = "1"


def _tokenize(text: str) -> list[str]:
    return [t for t in text.lower().split() if t]


def text_to_embedding(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Generate deterministic normalized embedding with feature hashing."""
    vec = [0.0] * dim
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        idx = int(digest[:8], 16) % dim
        sign = -1.0 if int(digest[8:10], 16) % 2 else 1.0
        vec[idx] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def idea_to_text(
    title: str,
    problem: str,
    target_user: str,
    solution: str,
    monetization_hypothesis: str | None = None,
    payer: str | None = None,
    pricing_model: str | None = None,
    wedge: str | None = None,
    why_now: str | None = None,
) -> str:
    parts = [title.strip(), problem.strip(), target_user.strip(), solution.strip()]
    for value in (
        monetization_hypothesis,
        payer,
        pricing_model,
        wedge,
        why_now,
    ):
        if value:
            parts.append(value.strip())
    return "\n".join(parts)


def cosine_similarity(v1: Iterable[float], v2: Iterable[float]) -> float:
    a = list(v1)
    b = list(v2)
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    n1 = math.sqrt(sum(x * x for x in a))
    n2 = math.sqrt(sum(y * y for y in b))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)
