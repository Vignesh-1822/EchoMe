"""Local speech-to-text via faster-whisper (Phase 2, Step 1).

Runs Whisper locally on CPU (Apple Silicon has no CUDA path; ctranslate2 uses int8
on CPU, which is plenty fast for short utterances). The model is downloaded on first
use and cached by faster-whisper under ~/.cache/huggingface.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from echome.config import load_config

SAMPLE_RATE = 16000  # Whisper expects 16 kHz mono audio


@lru_cache(maxsize=1)
def _get_model():
    """Load (and cache) the Whisper model named in config. Downloads on first run."""
    from faster_whisper import WhisperModel

    config = load_config()
    return WhisperModel(
        config.whisper_model, device="cpu", compute_type=config.whisper_compute_type
    )


def warm_up() -> None:
    """Force the model to load/download now (so the first utterance isn't slow)."""
    _get_model()


def transcribe(pcm_int16: np.ndarray, sample_rate: int = SAMPLE_RATE) -> str:
    """Transcribe 16-bit mono PCM to text. Returns "" if nothing intelligible."""
    if pcm_int16.size == 0:
        return ""
    # Whisper wants float32 in [-1, 1].
    audio = pcm_int16.astype(np.float32) / 32768.0
    segments, _info = _get_model().transcribe(audio, language="en", beam_size=5)
    return " ".join(segment.text for segment in segments).strip()
