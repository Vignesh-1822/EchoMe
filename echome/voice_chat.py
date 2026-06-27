"""Speak to the twin; it answers in TEXT (Phase 2, Step 1).

Run with:  python -m echome.voice_chat

This is the typed chat loop with a *spoken* input method: capture an utterance from
the mic, transcribe it locally with Whisper, then feed that text into the unchanged
retrieve -> persona -> LLM pipeline. Voice OUTPUT (the twin speaking back) is Phase 3.
"""

from __future__ import annotations

from echome.config import load_config
from echome.conversation import generate_reply, is_exit, remember
from echome.mic import record_utterance
from echome.persona import build_system_prompt
from echome.profile import load_profile
from echome.providers import ProviderError
from echome.stt import transcribe, warm_up


def run() -> None:
    config = load_config()
    try:
        profile = load_profile()
    except FileNotFoundError as exc:
        print(exc)
        return

    system = build_system_prompt(profile)

    print(f"You're speaking with the AI digital twin of {profile.name}.")
    print(f"(provider: {config.provider}  ·  STT: faster-whisper '{config.whisper_model}')")
    print(f"Loading Whisper '{config.whisper_model}' (first run downloads it)...")
    warm_up()  # load/download the model now, so the first turn isn't slow
    print("Ready. Speak after the prompt; pause when done. Say 'quit' or Ctrl-C to leave.\n")

    history: list[dict[str, str]] = []

    while True:
        try:
            print("🎤 listening… (speak now)")
            pcm = record_utterance()
        except KeyboardInterrupt:
            print("\nbye 👋")
            return

        if pcm.size == 0:
            print("   (didn't hear anything — try again)\n")
            continue

        question = transcribe(pcm)
        if not question:
            print("   (couldn't make that out — try again)\n")
            continue

        print(f"you said: {question}")
        if is_exit(question):
            print("bye 👋")
            return

        try:
            reply, _chunks = generate_reply(system, history, question)
        except ProviderError as exc:
            print(f"\n[provider error] {exc}\n")
            continue

        print(f"\n{profile.name.split()[0].lower()} > {reply}\n")
        remember(history, question, reply)


if __name__ == "__main__":
    run()
