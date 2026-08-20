"""Pluggable text-to-speech so the twin can speak replies in a cloned voice (Phase 3).

Mirrors the LLM-provider pattern: the pipeline talks to a `TTSBackend` interface and
never imports an engine SDK directly, so swapping engines (LuxTTS -> Chatterbox -> …)
is a one-line `TTS_ENGINE` change with no pipeline edits.

LICENSING NOTE: the default `luxtts` weights are distilled from ZipVoice, whose base
model is trained on the Emilia dataset (CC BY-NC 4.0, non-commercial). That makes
LuxTTS fine for LOCAL/personal use but NOT cleanly licensed for a public/commercial
release — swap to a cleanly-licensed backend (e.g. Chatterbox, MIT) before shipping.
The pluggable interface below exists precisely so that swap is trivial.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from echome.config import Config, load_config


class TTSBackend(ABC):
    """A swappable speech synthesizer."""

    @abstractmethod
    def synthesize(self, text: str, voice_ref_path: str) -> tuple[np.ndarray, int]:
        """Return (mono float32 waveform in [-1, 1], sample_rate) for `text`."""

    def prepare(self, voice_ref_path: str) -> None:
        """Optionally pre-load the model and encode the reference clip up front.

        Default is a no-op; backends with a slow first call should override it so the
        download/warm-up happens before the first reply instead of mid-conversation.
        """
        return None

    def close(self) -> None:
        """Release any resources (e.g. a worker subprocess). Default is a no-op."""
        return None


class LuxTTSBackend(TTSBackend):
    """LuxTTS (ZipVoice-distilled) zero-shot voice cloning.

    Loads on MPS (Apple Silicon) when available, else CPU. The reference clip is
    encoded once and the encoded prompt is cached, so only generation runs per reply.
    Model weights download from Hugging Face on first use.
    """

    def __init__(self, model_id: str = "YatharthS/LuxTTS", num_steps: int = 4):
        self.model_id = model_id
        self.num_steps = num_steps
        self._model = None
        self._device = None
        self._prompt_cache: dict[str, object] = {}

    def _ensure_model(self):
        if self._model is None:
            # Let unsupported ops (FFT/iSTFT in the vocoder) fall back to CPU on MPS,
            # instead of erroring. Must be set before torch initializes the MPS backend.
            import os

            os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            import torch

            try:
                from zipvoice.luxvoice import LuxTTS
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "LuxTTS is not installed (local/non-commercial use only). "
                    "See the README 'Hear it speak' section for the full install recipe."
                ) from exc

            self._device = "mps" if torch.backends.mps.is_available() else "cpu"
            self._model = LuxTTS(self.model_id, device=self._device)
        return self._model

    def _encoded_prompt(self, voice_ref_path: str):
        if voice_ref_path not in self._prompt_cache:
            model = self._ensure_model()
            # rms=0.01 per the LuxTTS README; encode the reference clip once.
            self._prompt_cache[voice_ref_path] = model.encode_prompt(voice_ref_path, rms=0.01)
        return self._prompt_cache[voice_ref_path]

    def prepare(self, voice_ref_path: str) -> None:
        self._encoded_prompt(voice_ref_path)  # loads model + caches the prompt

    def synthesize(
        self,
        text: str,
        voice_ref_path: str,
        *,
        smooth: bool | None = None,
        runway_text: str | None = None,
        end_trim_ms: int | None = None,
    ) -> tuple[np.ndarray, int]:
        """Synthesize speech, applying end-drift mitigations (config defaults, overridable).

        - smooth: use LuxTTS return_smooth (24 kHz vocoder path, fewer artifacts).
        - runway_text: appended to the text so end-drift lands on throwaway runway.
        - end_trim_ms: trim this many ms off the end of the audio.
        """
        config = load_config()
        smooth = config.tts_smooth if smooth is None else smooth
        runway_text = config.tts_runway_text if runway_text is None else runway_text
        end_trim_ms = config.tts_end_trim_ms if end_trim_ms is None else end_trim_ms

        model = self._ensure_model()
        prompt = self._encoded_prompt(voice_ref_path)

        wav = model.generate_speech(
            text + runway_text, prompt, num_steps=self.num_steps, return_smooth=smooth
        )
        audio = wav.detach().to("cpu").numpy().squeeze().astype(np.float32)
        # Output is 48 kHz regardless of return_smooth (it changes the vocoder smoothing,
        # not the sample rate — verified: smooth/non-smooth yield the same sample count).
        sample_rate = 48000

        if end_trim_ms > 0:
            trim = int(sample_rate * end_trim_ms / 1000)
            if trim < len(audio):
                audio = audio[:-trim]
        return audio, sample_rate


class ChatterboxBackend(TTSBackend):
    """Resemble AI Chatterbox (MIT code + MIT weights — cleanly shippable).

    Chatterbox pins an older torch/numpy/transformers than the rest of EchoMe, so it
    runs in an isolated `venv-chatterbox` and is driven here as a long-lived subprocess
    (echome/_chatterbox_worker.py). The model loads once in that process; we exchange
    one JSON line per synthesis. Output includes Resemble's Perth watermark.
    """

    SENTINEL = "##ECHOME##"

    def __init__(self, venv_python: str = "venv-chatterbox/bin/python"):
        self.venv_python = venv_python
        self._proc = None
        self._sr = None
        self._device = None

    def _read_protocol(self) -> dict:
        """Read worker stdout until a sentinel-prefixed protocol line appears."""
        for line in self._proc.stdout:
            if line.startswith(self.SENTINEL):
                import json

                return json.loads(line[len(self.SENTINEL):].strip())
        raise RuntimeError("Chatterbox worker exited before responding (see its stderr).")

    def prepare(self, voice_ref_path: str) -> None:
        if self._proc is not None:
            return
        import os
        import subprocess

        if not os.path.exists(self.venv_python):
            raise RuntimeError(
                f"Chatterbox venv not found at '{self.venv_python}'. Create it with:\n"
                "  python3 -m venv venv-chatterbox && "
                "venv-chatterbox/bin/pip install chatterbox-tts"
            )
        # Run the worker as a module so its `echome` imports resolve.
        self._proc = subprocess.Popen(
            [self.venv_python, "-m", "echome._chatterbox_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            cwd=os.getcwd(),
        )
        ready = self._read_protocol()  # blocks through first-run model download
        self._sr = ready["sr"]
        self._device = ready.get("device")

    def synthesize(self, text: str, voice_ref_path: str) -> tuple[np.ndarray, int]:
        import json
        import tempfile

        import soundfile as sf

        if self._proc is None:
            self.prepare(voice_ref_path)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            out_path = tmp.name
        try:
            request = {"text": text, "voice_ref": voice_ref_path, "out": out_path}
            self._proc.stdin.write(json.dumps(request) + "\n")
            self._proc.stdin.flush()
            result = self._read_protocol()
            if result.get("status") != "ok":
                raise RuntimeError(f"Chatterbox synthesis failed: {result.get('msg')}")
            audio, sample_rate = sf.read(out_path, dtype="float32")
        finally:
            import os

            os.path.exists(out_path) and os.remove(out_path)
        if audio.ndim > 1:  # mono
            audio = audio[:, 0]
        return audio, sample_rate

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.stdin.close()  # EOF -> worker exits its read loop
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
            self._proc = None


class WatermarkedTTS(TTSBackend):
    """Wraps any backend so every synthesized clip carries the AudioSeal watermark.

    This is the single choke point that enforces "all synthesized audio is marked as AI"
    (golden rule #6) regardless of engine. Output is 16 kHz (AudioSeal's rate); for
    speech that's an inaudible trade — see echome/watermark.py.
    """

    def __init__(self, inner: TTSBackend):
        self._inner = inner

    def prepare(self, voice_ref_path: str) -> None:
        self._inner.prepare(voice_ref_path)
        from echome.watermark import warm_up

        warm_up()  # download/load the watermarker now, not mid-conversation

    def synthesize(self, text: str, voice_ref_path: str) -> tuple[np.ndarray, int]:
        from echome.watermark import embed

        audio, sr = self._inner.synthesize(text, voice_ref_path)
        return embed(audio, sr)

    def close(self) -> None:
        self._inner.close()


def get_tts_backend(config: Config | None = None) -> TTSBackend:
    """Build the TTS backend selected by `TTS_ENGINE`, watermarked unless disabled."""
    config = config or load_config()
    engine = config.tts_engine
    if engine == "luxtts":
        backend: TTSBackend = LuxTTSBackend()
    elif engine == "chatterbox":
        backend = ChatterboxBackend()
    else:
        raise ValueError(
            f"Unknown TTS_ENGINE '{engine}'. Supported: luxtts, chatterbox."
        )
    if config.tts_watermark:
        backend = WatermarkedTTS(backend)
    return backend


def play(audio: np.ndarray, sample_rate: int, lead_ms: int = 250, tail_ms: int = 100) -> None:
    """Play a waveform through the default speakers (blocks until done).

    Prepends `lead_ms` of silence so the output device's startup latency clips silence
    instead of the first words (LuxTTS leaves only ~60ms of lead-in, not enough), and
    appends a short tail so the ending isn't cut. The saved WAVs are unaffected.
    """
    import sounddevice as sd

    lead = np.zeros(int(sample_rate * lead_ms / 1000), dtype=audio.dtype)
    tail = np.zeros(int(sample_rate * tail_ms / 1000), dtype=audio.dtype)
    padded = np.concatenate([lead, audio, tail])

    sd.play(padded, sample_rate)
    sd.wait()  # block until playback finishes


def save_wav(path: str, audio: np.ndarray, sample_rate: int) -> None:
    """Write a waveform to a WAV file."""
    import soundfile as sf

    sf.write(path, audio, sample_rate)
