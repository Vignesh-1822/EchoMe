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


def _get_bool(key: str, default: bool) -> bool:
    """Read a boolean env var ('true'/'1'/'yes' are True)."""
    raw = os.getenv(key, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


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

    # Speech-to-text (Phase 2). Whisper runs locally on CPU (Apple Silicon has no
    # CUDA; ctranslate2 uses CPU + int8 for speed).
    whisper_model: str
    whisper_compute_type: str

    # Text-to-speech (Phase 3). Pluggable engine, like the LLM provider.
    tts_engine: str
    voice_ref: str

    # Watermark all synthesized audio as AI-generated (AudioSeal). Keep on for any
    # audio that leaves this machine — required by the voice guardrail (golden rule #6).
    tts_watermark: bool

    # LuxTTS end-of-generation drift mitigations (each independently toggleable):
    tts_smooth: bool        # return_smooth=True (24 kHz vocoder path, fewer artifacts)
    tts_runway_text: str    # appended to text so drift lands on throwaway runway ("" = off)
    tts_end_trim_ms: int    # trim this many ms off the end of the audio (0 = off)

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
        whisper_model=_get("WHISPER_MODEL", "base"),
        whisper_compute_type=_get("WHISPER_COMPUTE_TYPE", "int8"),
        tts_engine=_get("TTS_ENGINE", "luxtts").lower(),
        voice_ref=_get("VOICE_REF", "voice/voice_sample.wav"),
        tts_watermark=_get_bool("TTS_WATERMARK", True),
        tts_smooth=_get_bool("TTS_SMOOTH", True),
        # Default " ." runway (ab_3 winner): gives end-drift throwaway runway to land on.
        # Set TTS_RUNWAY_TEXT= (empty) to disable.
        tts_runway_text=os.getenv("TTS_RUNWAY_TEXT", " ."),
        tts_end_trim_ms=int(_get("TTS_END_TRIM_MS", "0")),
        min_similarity=float(_get("MIN_SIMILARITY", "0.25")),
    )
