"""Interactive text chat with the twin (Phase 1, Step 6 — the definition of done).

Run with:  python -m echome.chat

Loads the profile, builds the persona+guardrail system prompt once, then loops:
read a question -> retrieve public context (0.25 floor) -> format the turn ->
call the configured provider -> print the reply in first person. A short rolling
history gives follow-ups context without letting the prompt grow unbounded.
"""

from __future__ import annotations

from echome.config import load_config
from echome.persona import build_system_prompt, format_user_turn
from echome.providers import ProviderError, chat
from echome.profile import load_profile
from echome.rag import retrieve

# Keep the last N exchanges (1 exchange = 1 user + 1 assistant message) so the
# prompt stays small and cheap. 6 exchanges = 12 messages.
MAX_EXCHANGES = 6


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
        if question.lower() in {"quit", "exit"}:
            print("bye 👋")
            return

        chunks = retrieve(question)  # public-only, 0.25 floor (defaults)
        user_turn = format_user_turn(question, chunks)
        messages = [*history, {"role": "user", "content": user_turn}]

        try:
            reply = chat(system, messages)
        except ProviderError as exc:
            print(f"\n[provider error] {exc}\n")
            continue

        print(f"\n{profile.name.split()[0].lower()} > {reply}\n")

        # Store the RAW question (not the context-heavy turn) + reply, then trim.
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": reply})
        del history[: -2 * MAX_EXCHANGES]


if __name__ == "__main__":
    run()
