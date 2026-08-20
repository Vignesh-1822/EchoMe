"""Voice-cloning consent gate — Model B: spoken, Whisper-verified, logged (Phase 3).

Before EchoMe will synthesize in a cloned voice, the enrollment clip it clones from
must itself contain the speaker granting permission, spoken *in that same voice*. We
transcribe the clip locally with our own Whisper (Phase 2) and require the consent
phrase to be present, then append a timestamped, file-hashed record to a log. No
spoken consent -> no synthesis.

Why spoken-in-voice rather than a yes/no prompt: a checkbox proves nothing about
*whose* voice the clip is — anyone could tick it over a stolen recording. Requiring the
consent sentence in the cloned voice ties "I agree" to the actual voiceprint, which is
what makes this defensible for a public voice-cloning repo (golden rule #6, §8).

The record is keyed on the clip's SHA-256, so consent is verified once per clip; swap
in a different clip and it must be re-consented (a new voice needs new permission).
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from datetime import datetime, timezone

import numpy as np

from echome.stt import SAMPLE_RATE, transcribe

# What the speaker must say in the enrollment clip. The first form is normalized for
# tolerant matching; the second is shown to the user to read aloud.
CONSENT_PHRASE = "this is my voice and i give permission to use it"
CONSENT_PHRASE_DISPLAY = "This is my voice, and I give permission to use it."

# Fraction of the phrase that must match (Whisper is not character-perfect).
MATCH_THRESHOLD = 0.8

CONSENT_LOG = "voice/consent.log"


class ConsentError(RuntimeError):
    """Raised when a voice clip has no verifiable spoken consent."""


def _tokens(text: str) -> list[str]:
    """Lowercase word tokens, punctuation stripped — for tolerant phrase matching."""
    return re.sub(r"[^a-z0-9 ]+", " ", text.lower()).split()


def _phrase_present(transcript: str, phrase: str, threshold: float = MATCH_THRESHOLD) -> bool:
    """True if `phrase` appears in `transcript`, allowing minor transcription slop.

    Slides a window the length of the phrase across the transcript and compares token
    sequences with difflib, so "give permission to use it" still matches even if Whisper
    drops or bends a word or two.
    """
    target = _tokens(phrase)
    if not target:
        return False
    words = _tokens(transcript)
    if len(words) < len(target):
        return difflib.SequenceMatcher(None, words, target).ratio() >= threshold
    for i in range(len(words) - len(target) + 1):
        window = words[i : i + len(target)]
        if difflib.SequenceMatcher(None, window, target).ratio() >= threshold:
            return True
    return False


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def _read_wav_16k_int16(path: str) -> np.ndarray:
    """Load a WAV as 16 kHz mono int16 PCM (what Whisper expects)."""
    import soundfile as sf

    audio, sr = sf.read(path, dtype="float32")
    if audio.ndim > 1:  # mix down to mono
        audio = audio.mean(axis=1)
    if sr != SAMPLE_RATE:  # linear resample — fine for speech recognition
        n = int(round(len(audio) * SAMPLE_RATE / sr))
        if n > 0:
            audio = np.interp(
                np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio
            ).astype(np.float32)
    return (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)


def _find_record(digest: str) -> dict | None:
    """Return a prior 'granted' consent record for this clip hash, if any."""
    if not os.path.exists(CONSENT_LOG):
        return None
    with open(CONSENT_LOG, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("sha256") == digest and rec.get("status") == "granted":
                return rec
    return None


def _record_consent(voice_ref: str, digest: str, transcript: str) -> dict:
    """Append a timestamped consent record and return it."""
    rec = {
        "status": "granted",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "voice_ref": voice_ref,
        "sha256": digest,
        "heard": transcript,
        "phrase": CONSENT_PHRASE,
    }
    os.makedirs(os.path.dirname(CONSENT_LOG) or ".", exist_ok=True)
    with open(CONSENT_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def ensure_consent(voice_ref: str) -> dict:
    """Gate synthesis on verified spoken consent for `voice_ref`.

    Returns the consent record on success (verifying anew only if this exact clip
    hasn't been consented before). Raises ConsentError if the clip is missing or the
    spoken consent phrase can't be found in it.
    """
    if not os.path.exists(voice_ref):
        raise ConsentError(
            f"Voice reference '{voice_ref}' not found — cannot verify consent."
        )

    digest = _file_sha256(voice_ref)
    prior = _find_record(digest)
    if prior is not None:
        return prior  # already consented for this exact clip

    transcript = transcribe(_read_wav_16k_int16(voice_ref))
    if not _phrase_present(transcript, CONSENT_PHRASE):
        raise ConsentError(
            "No spoken consent found in the voice clip — refusing to clone it.\n"
            f"  Heard: {transcript!r}\n"
            "  The enrollment clip must include you saying, in your own voice:\n"
            f'    "{CONSENT_PHRASE_DISPLAY}"\n'
            f"  Re-record '{voice_ref}' with that line included (anywhere in the clip),\n"
            "  then run again."
        )
    return _record_consent(voice_ref, digest, transcript)


def _main() -> None:
    """CLI: verify/enroll consent for a clip. Usage: python -m echome.consent [path]"""
    import sys

    from echome.config import load_config

    voice_ref = sys.argv[1] if len(sys.argv) > 1 else load_config().voice_ref
    print(f"Verifying spoken consent in '{voice_ref}' (transcribing locally)…")
    try:
        rec = ensure_consent(voice_ref)
    except ConsentError as exc:
        print(f"\n✗ {exc}")
        raise SystemExit(1)
    print(f"\n✓ Consent verified and logged to {CONSENT_LOG}")
    print(f"  heard: {rec['heard']!r}")
    print(f"  when:  {rec['timestamp']}")


if __name__ == "__main__":
    _main()
