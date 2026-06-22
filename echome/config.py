"""Central configuration for EchoMe, loaded from `.env` with sensible defaults.

Bring-your-own-key: nothing here is hardcoded to a person or a secret. The LLM
provider is pluggable — switch `PROVIDER` between "ollama" (free, local) and
"claude" (paid API) with no code change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Load .env once, on import. Real values stay in the gitignored .env file.
load_dotenv()


def _get(key: str, default: str) -> str:
    """Read an env var, falling back to a default and ignoring empty strings."""
    value = os.getenv(key, "").strip()
    return value if value else default


@dataclass(frozen=True)
class Config:
    """All runtime settings for the text brain (Phase 1)."""

    # Which LLM brain to use: "ollama", "openai", or "claude".
    provider: str

    # Ollama (free, local dev).
    ollama_model: str
    ollama_url: str

    # OpenAI (paid API).
    openai_api_key: str
    openai_model: str

    # Claude (paid API, production).
    claude_api_key: str
    claude_model: str

    # Embeddings + vector index (local, used for RAG).
    embed_model: str
    index_dir: str

    # Retrieval relevance floor: chunks below this cosine similarity are dropped,
    # so weak/irrelevant context never reaches the LLM (no-hallucination guardrail).
    min_similarity: float


def load_config() -> Config:
    """Build a Config from the current environment."""
    return Config(
        provider=_get("PROVIDER", "ollama").lower(),
        ollama_model=_get("OLLAMA_MODEL", "llama3.1"),
        ollama_url=_get("OLLAMA_URL", "http://localhost:11434"),
        openai_api_key=_get("OPENAI_API_KEY", ""),
        openai_model=_get("OPENAI_MODEL", "gpt-4o-mini"),
        claude_api_key=_get("CLAUDE_API_KEY", ""),
        claude_model=_get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        embed_model=_get("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        index_dir=_get("INDEX_DIR", "index"),
        min_similarity=float(_get("MIN_SIMILARITY", "0.25")),
    )
