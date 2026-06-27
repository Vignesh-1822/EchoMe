"""Shared turn-handling for the text and voice chat loops.

Both `echome.chat` (typed) and `echome.voice_chat` (spoken input) run the exact same
brain: retrieve -> persona-formatted turn -> provider. Keeping it here means the voice
path is just a different *input* method over an unchanged pipeline.
"""

from __future__ import annotations

from echome.persona import format_user_turn
from echome.providers import chat
from echome.rag import retrieve

# Keep the last N exchanges (1 exchange = 1 user + 1 assistant message) so the
# prompt stays small and cheap. 6 exchanges = 12 messages.
MAX_EXCHANGES = 6


def generate_reply(
    system: str, history: list[dict[str, str]], question: str
) -> tuple[str, list[dict]]:
    """Retrieve context for `question` and get the twin's reply. Returns (reply, chunks)."""
    chunks = retrieve(question)  # public-only, config floor (defaults)
    user_turn = format_user_turn(question, chunks)
    reply = chat(system, [*history, {"role": "user", "content": user_turn}])
    return reply, chunks


def remember(history: list[dict[str, str]], question: str, reply: str) -> None:
    """Append the raw turn to history (no retrieved context stored) and trim it."""
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": reply})
    del history[: -2 * MAX_EXCHANGES]


def is_exit(text: str) -> bool:
    """True if the user asked to quit (tolerates transcription punctuation/case)."""
    return text.strip().strip(".!?,").lower() in {"quit", "exit"}
