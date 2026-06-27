"""Microphone capture with voice-activity detection (Phase 2, Step 1).

Records a single spoken utterance and stops automatically when you pause — no
key-press needed. Uses WebRTC VAD on 30 ms frames: it waits until you start
speaking, then keeps recording until it hears a sustained silence.

Audio is captured as 16 kHz mono int16, which is exactly what Whisper wants.
"""

from __future__ import annotations

import collections

import numpy as np
import sounddevice as sd
import webrtcvad

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 480 samples per frame


def record_utterance(
    aggressiveness: int = 2,
    silence_ms: int = 800,
    start_timeout_s: float = 10.0,
    max_utterance_s: float = 30.0,
) -> np.ndarray:
    """Capture one utterance from the default mic.

    Waits up to `start_timeout_s` for speech to begin, then records until it hears
    `silence_ms` of trailing silence (or `max_utterance_s` is reached). Returns the
    spoken audio as int16 PCM, or an empty array if no speech was detected.
    """
    vad = webrtcvad.Vad(aggressiveness)
    silence_frames = silence_ms // FRAME_MS
    start_timeout_frames = int(start_timeout_s * 1000 // FRAME_MS)
    max_frames = int(max_utterance_s * 1000 // FRAME_MS)

    # ~300 ms of pre-roll so we don't clip the first word once speech triggers.
    preroll = collections.deque(maxlen=10)
    voiced: list[bytes] = []
    triggered = False
    trailing_silence = 0
    waited = 0

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE, blocksize=FRAME_SAMPLES, dtype="int16", channels=1
    ) as stream:
        while True:
            block, _overflowed = stream.read(FRAME_SAMPLES)
            frame = bytes(block)
            is_speech = vad.is_speech(frame, SAMPLE_RATE)

            if not triggered:
                preroll.append(frame)
                if is_speech:
                    triggered = True
                    voiced.extend(preroll)
                    preroll.clear()
                else:
                    waited += 1
                    if waited > start_timeout_frames:
                        return np.array([], dtype=np.int16)  # nobody spoke
                continue

            voiced.append(frame)
            trailing_silence = trailing_silence + 1 if not is_speech else 0
            if trailing_silence >= silence_frames or len(voiced) >= max_frames:
                break

    pcm = b"".join(voiced)
    return np.frombuffer(pcm, dtype=np.int16)
