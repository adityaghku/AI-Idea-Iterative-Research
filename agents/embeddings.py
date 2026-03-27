"""
Embedding generation for semantic similarity detection.

Uses sentence-transformers for local embedding (no API cost).
Default model: 'all-MiniLM-L6-v2' (384 dimensions).
"""

from __future__ import annotations

import numpy as np
from typing import Any

# Lazy-loaded model to avoid loading at import time
_model = None
_model_version = "all-MiniLM-L6-v2"


def _get_model():
    """Get or create the sentence transformer model (lazy loading)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def get_model_version() -> str:
    """Return the current embedding model version."""
    return _model_version


def generate_idea_embedding(idea: dict[str, Any]) -> list[float]:
    """
    Generate embedding for an idea using title and summary.
    
    Args:
        idea: Dict with 'idea_title' and/or 'idea_summary' keys
        
    Returns:
        List of floats (384 dimensions for all-MiniLM-L6-v2)
    """
    model = _get_model()
    title = str(idea.get('idea_title') or idea.get('title') or '').strip()
    summary = str(idea.get('idea_summary') or idea.get('summary') or '').strip()
    text = f"{title} {summary}".strip()
    
    if not text:
        # Return zero vector for empty ideas
        return [0.0] * 384
    
    embedding = model.encode(text)
    return embedding.tolist()


def compute_similarity(emb1: list[float], emb2: list[float]) -> float:
    """
    Compute cosine similarity between two embeddings.
    
    Args:
        emb1: First embedding vector
        emb2: Second embedding vector
        
    Returns:
        Cosine similarity score between -1 and 1
    """
    a = np.array(emb1)
    b = np.array(emb2)
    
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(np.dot(a, b) / (norm_a * norm_b))


def embedding_to_bytes(embedding: list[float]) -> bytes:
    """
    Serialize embedding list to bytes for database storage.
    
    Args:
        embedding: List of floats
        
    Returns:
        Bytes representation
    """
    return np.array(embedding, dtype=np.float32).tobytes()


def bytes_to_embedding(data: bytes) -> list[float]:
    """
    Deserialize bytes to embedding list.
    
    Args:
        data: Bytes from database
        
    Returns:
        List of floats
    """
    arr = np.frombuffer(data, dtype=np.float32)
    return arr.tolist()


def find_similar_ideas(
    query_embedding: list[float],
    candidate_embeddings: list[tuple[int, list[float]]],
    threshold: float = 0.85,
) -> list[tuple[int, float]]:
    """
    Find ideas with embeddings above similarity threshold.
    
    Args:
        query_embedding: The embedding to compare against
        candidate_embeddings: List of (idea_id, embedding) tuples
        threshold: Minimum similarity score (default 0.85)
        
    Returns:
        List of (idea_id, similarity_score) tuples, sorted by similarity descending
    """
    results = []
    for idea_id, emb in candidate_embeddings:
        sim = compute_similarity(query_embedding, emb)
        if sim >= threshold:
            results.append((idea_id, sim))
    
    results.sort(key=lambda x: x[1], reverse=True)
    return results