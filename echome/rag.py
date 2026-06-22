"""Retrieval over the local Chroma index (Phase 1, Step 4).

This is the *search* half of RAG — no LLM yet. Given a question, embed it with the
same model used at ingest time, pull the nearest chunks, and (by default) withhold
anything tagged private. Public-only is the safe default so the twin can't leak
private facts just because a caller forgot a flag.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from echome.config import load_config
from echome.ingest import COLLECTION_NAME


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load (and cache) the embedding model named in config."""
    return SentenceTransformer(load_config().embed_model)


@lru_cache(maxsize=1)
def _get_collection():
    """Open (and cache) the persistent Chroma collection."""
    client = chromadb.PersistentClient(path=load_config().index_dir)
    return client.get_collection(COLLECTION_NAME)


def retrieve(
    question: str,
    k: int = 6,
    include_private: bool = False,
    min_similarity: float | None = None,
) -> list[dict[str, Any]]:
    """Return chunks relevant to `question`, or an empty list if none clear the floor.

    Each result: {text, source, visibility, distance, similarity}. With
    include_private=False (default), private chunks are filtered out *in the query*
    so the caller still gets up to k public candidates.

    Chunks scoring below `min_similarity` (defaults to config.min_similarity) are
    dropped. If nothing clears the floor, returns [] — that empty result is how the
    LLM knows to say "I don't have that" rather than inventing an answer.
    """
    floor = load_config().min_similarity if min_similarity is None else min_similarity
    model = _get_model()
    collection = _get_collection()

    embedding = model.encode([question], normalize_embeddings=True).tolist()
    where = None if include_private else {"visibility": {"$ne": "private"}}

    response = collection.query(
        query_embeddings=embedding,
        n_results=k,
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    # Chroma returns a list-per-query; we only sent one query.
    documents = response["documents"][0]
    metadatas = response["metadatas"][0]
    distances = response["distances"][0]

    results = []
    for text, meta, distance in zip(documents, metadatas, distances):
        similarity = 1.0 - distance  # cosine space: similarity = 1 - distance
        if similarity < floor:
            continue  # below the relevance floor — drop it
        results.append(
            {
                "text": text,
                "source": meta.get("source", "unknown"),
                "visibility": meta.get("visibility", "unknown"),
                "distance": distance,
                "similarity": similarity,
            }
        )
    return results
