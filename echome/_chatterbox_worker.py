"""Chatterbox TTS worker — runs INSIDE the isolated `venv-chatterbox`.

Chatterbox pins an older torch/numpy/transformers that conflicts with the main
EchoMe env, so it lives in its own virtualenv and is driven as a subprocess by
echome.tts.ChatterboxBackend. The model is loaded once, then this process serves
synthesis requests over a tiny line protocol so each reply doesn't reload ~1 GB.

Protocol (one JSON object per line, on stdout, prefixed so it's separable from the
libraries' own logging which we keep on stderr):
  ready:   ##ECHOME## {"status": "ready", "sr": 24000, "device": "mps"}
  request (stdin): {"text": "...", "voice_ref": "path.wav", "out": "path.wav"}
  result:  ##ECHOME## {"status": "ok"}  |  {"status": "error", "msg": "..."}
"""

from __future__ import annotations

import json
import os
import sys

SENTINEL = "##ECHOME##"


def _emit(obj: dict) -> None:
    """Write a protocol message to stdout (kept clean via the sentinel prefix)."""
    sys.stdout.write(f"{SENTINEL} {json.dumps(obj)}\n")
    sys.stdout.flush()


def main() -> None:
    # Let unsupported MPS ops fall back to CPU instead of erroring.
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

    import torch
    import torchaudio as ta
    from chatterbox.tts import ChatterboxTTS

    # Prefer Apple-Silicon GPU; fall back to CPU if MPS load fails.
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    try:
        model = ChatterboxTTS.from_pretrained(device=device)
    except Exception as exc:  # pragma: no cover - device-specific
        sys.stderr.write(f"[worker] {device} load failed ({exc}); falling back to cpu\n")
        device = "cpu"
        model = ChatterboxTTS.from_pretrained(device="cpu")

    _emit({"status": "ready", "sr": int(model.sr), "device": device})

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            if req.get("cmd") == "quit":
                break
            wav = model.generate(req["text"], audio_prompt_path=req["voice_ref"])
            ta.save(req["out"], wav.detach().cpu(), model.sr)
            _emit({"status": "ok"})
        except Exception as exc:  # report, keep serving
            _emit({"status": "error", "msg": str(exc)})


if __name__ == "__main__":
    main()
