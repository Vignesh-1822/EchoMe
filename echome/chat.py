"""Interactive text chat with the twin (Phase 1, Step 6 — the definition of done).

Run with:  python -m echome.chat

Loads the profile, builds the persona+guardrail system prompt once, then loops:
read a question -> retrieve public context (0.25 floor) -> format the turn ->
call the configured provider -> print the reply in first person. A short rolling
history gives follow-ups context without letting the prompt grow unbounded.
"""

from __future__ import annotations

from echome.config import load_config
from echome.conversation import generate_reply, is_exit, remember
from echome.persona import build_system_prompt
from echome.profile import load_profile
from echome.providers import ProviderError


def run() -> None:
    config = load_config()
    try:
        profile = load_profile()
    except FileNotFoundError as exc:
        print(exc)
        return

    system = build_system_prompt(profile)

    print(f"You're chatting with the AI digital twin of {profile.name}.")
    print(f"(provider: {config.provider}  ·  type 'quit' or 'exit' to leave)\n")

    # Lightweight history: raw questions + replies (no retrieved context stored,
    # so it stays small). Only the current turn carries fresh retrieved context.
    history: list[dict[str, str]] = []

    while True:
        try:
            question = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye 👋")
            return

        if not question:
            continue
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
