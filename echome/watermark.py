"""AudioSeal watermarking — mark every synthesized clip as AI-generated (Phase 3).

Golden rule #6 / §8: a public voice-cloning tool must watermark all synthesized audio,
so a clip in someone's cloned voice can be *proven* synthetic rather than passed off as
a real recording. AudioSeal (Meta, MIT) weaves an inaudible signal across the whole
waveform plus a small payload; a matching detector reads it back later. Unlike file
metadata or a spoken "I'm an AI" disclaimer, it survives MP3 re-encoding, resampling,
and trimming. It's a deterrent + provenance tool, not DRM — a determined adversary can
degrade it, but it defeats casual misuse and gives verifiable provenance.

AudioSeal operates at 16 kHz, so we watermark (and therefore deliver) voice at 16 kHz.
For speech that's an essentially inaudible trade: voice identity and intelligibility
live below 8 kHz; only the top "air" band is lost (see README "Voice engines"). Both TTS
engines route their output through `embed()`, so there is ONE watermark scheme and ONE
detector for everything — Chatterbox additionally carries its native Perth mark, which
is harmless to double up.
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

# AudioSeal's bundled moshi SEANet wraps its forward in torch.compile; TorchInductor can
# deadlock compiling those kernels on CPU (observed hanging indefinitely at 0% CPU on an
# M-series Mac). moshi honors this env var to stay in plain eager mode — set it before
# AudioSeal is imported. Eager is plenty fast here (embed ~0.1s for a short clip).
os.environ.setdefault("NO_TORCH_COMPILE", "1")

WATERMARK_SR = 16000  # AudioSeal's operating sample rate

# 16-bit signature embedded in every EchoMe clip (arbitrary but fixed = 0xAC36). The
# detector compares recovered bits against this to distinguish our marks from other
# AudioSeal watermarks. A small Hamming tolerance absorbs imperfect bit recovery.
ECHOME_PAYLOAD = [1, 0, 1, 0, 1, 1, 0, 0, 0, 0, 1, 1, 0, 1, 1, 0]
_MATCH_TOLERANCE = 2  # allow up to this many wrong bits and still call it ours


@lru_cache(maxsize=1)
def _generator():
    from audioseal import AudioSeal

    return AudioSeal.load_generator("audioseal_wm_16bits")


@lru_cache(maxsize=1)
def _detector():
    from audioseal import AudioSeal

    return AudioSeal.load_detector("audioseal_detector_16bits")


def warm_up() -> None:
    """Download/load the AudioSeal generator now (so the first reply isn't slow)."""
    _generator()


def _to_16k_mono_tensor(audio: np.ndarray, sr: int):
    """Return a (1, 1, samples) float32 torch tensor at 16 kHz mono."""
    import torch
    import torchaudio.functional as AF

    if audio.ndim > 1:  # mix down to mono
        audio = audio.mean(axis=1)
    x = torch.from_numpy(np.ascontiguousarray(audio, dtype=np.float32))
    if sr != WATERMARK_SR:  # filtered (anti-aliased) resample, unlike naive decimation
        x = AF.resample(x, sr, WATERMARK_SR)
    return x.unsqueeze(0).unsqueeze(0)


def embed(
    audio: np.ndarray, sr: int, *, payload: list[int] = ECHOME_PAYLOAD
) -> tuple[np.ndarray, int]:
    """Return (watermarked mono float32 audio at 16 kHz, 16000).

    The output carries an inaudible AudioSeal watermark plus the EchoMe payload. Input
    at any sample rate is resampled to 16 kHz first.
    """
    import torch

    x = _to_16k_mono_tensor(audio, sr)
    msg = torch.tensor([payload], dtype=torch.int32)
    watermarked = _generator()(x, sample_rate=WATERMARK_SR, message=msg, alpha=1.0)
    out = watermarked.squeeze().detach().cpu().numpy().astype(np.float32)
    return out, WATERMARK_SR


def detect(audio: np.ndarray, sr: int) -> dict:
    """Check for an AudioSeal watermark. Returns probability, decoded bits, and whether
    the payload matches EchoMe's signature (within a small bit tolerance)."""
    x = _to_16k_mono_tensor(audio, sr)
    prob, message = _detector().detect_watermark(x, sample_rate=WATERMARK_SR)
    bits = [1 if b > 0.5 else 0 for b in message.squeeze().tolist()]
    hamming = sum(a != b for a, b in zip(bits, ECHOME_PAYLOAD))
    return {
        "probability": float(prob),
        "bits": bits,
        "is_watermarked": float(prob) > 0.5,
        "is_echome": float(prob) > 0.5 and hamming <= _MATCH_TOLERANCE,
    }


def _main() -> None:
    """CLI: detect a watermark in a WAV. Usage: python -m echome.watermark <file.wav>"""
    import sys

    import soundfile as sf

    if len(sys.argv) < 2:
        print("usage: python -m echome.watermark <file.wav>")
        raise SystemExit(2)
    path = sys.argv[1]
    audio, sr = sf.read(path, dtype="float32")
    print(f"Analyzing '{path}' ({sr} Hz)…")
    result = detect(audio, sr)
    verdict = (
        "EchoMe AI-generated ✓" if result["is_echome"]
        else "watermarked (not EchoMe's payload)" if result["is_watermarked"]
        else "no watermark detected"
    )
    print(f"  detection probability: {result['probability']:.3f}")
    print(f"  payload bits:          {''.join(map(str, result['bits']))}")
    print(f"  verdict:               {verdict}")


if __name__ == "__main__":
    _main()
