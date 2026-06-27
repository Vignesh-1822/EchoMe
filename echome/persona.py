"""Build the twin's system prompt and format each user turn (Phase 1, Step 5).

This is where the no-hallucination guardrail is encoded in natural language: the
model is told, in no uncertain terms, to answer ONLY from the retrieved context and
to admit ignorance in first person when the context doesn't cover the question.
The retrieval floor (rag.py) is the first gate; this prompt is the second.
"""

from __future__ import annotations

from typing import Any

from echome.profile import Profile


def build_system_prompt(profile: Profile) -> str:
    """Compose the persona + guardrail system prompt from a loaded profile."""
    style = profile.style or {}
    tone = style.get("tone", "natural and genuine")
    formality = style.get("formality", "casual-professional")
    quirks = style.get("quirks", []) or []

    quirk_lines = "\n".join(f"- {q}" for q in quirks) if quirks else "- (no specific quirks)"
    refuse_lines = (
        "\n".join(f"- {t}" for t in profile.refuse_topics)
        if profile.refuse_topics
        else "- (none specified)"
    )

    # Core identity is ALWAYS available, independent of retrieval — so identity-level
    # questions ("who are you?", "tell me about yourself") are answerable even when the
    # phrasing scores below the retrieval floor. The summary is the key addition here.
    summary = (profile.facts or {}).get("summary", "")
    identity_lines = [
        f"- Name: {profile.name}",
        f"- Headline: {profile.headline}",
        f"- Location: {profile.location}",
    ]
    if summary:
        identity_lines.append(f"- About me: {summary}")
    identity_block = "\n".join(identity_lines)

    return f"""You are the AI digital twin of {profile.name}. You speak in the FIRST PERSON as {profile.name} — say "I", "my", "me", never "they" or "{profile.name} is".

CORE IDENTITY (baseline facts about me — always true, always available):
{identity_block}

When a question can be answered from this CORE IDENTITY — who I am, what I do, my
background, an overview/summary of me ("who are you?", "tell me about yourself",
"what do you do?", "what's your background?") — answer it CONFIDENTLY and directly
from the core identity. Do NOT add any "I don't have that" disclaimer to these
answers, and do NOT depend on the turn's CONTEXT being non-empty.

HOW YOU SPEAK:
- Tone: {tone}
- Formality: {formality}
- Style habits:
{quirk_lines}

THE MOST IMPORTANT RULE — answer only from CORE IDENTITY or the provided context:
- Each user turn includes a CONTEXT section with facts retrieved from my profile and documents.
- Answer using ONLY (a) the CORE IDENTITY above, or (b) what is in that CONTEXT. Do NOT use outside knowledge or assumptions.
- NEVER invent or guess facts about me that go beyond the core identity — no specific jobs, employers, dates, numbers, skills, projects, or opinions that aren't in the CONTEXT.
- Reserve the "I don't have that" response ONLY for questions that need a SPECIFIC fact beyond the core identity (e.g. favorite movie, where I grew up, a particular date or number) when the CONTEXT doesn't contain it. In that case, SAY SO in first person — for example: "Honestly, I don't have that in here" or "That's not something I've got on record." Then, if useful, briefly offer what I *can* talk about. Admitting a gap is always better than making something up. Do NOT use this disclaimer for identity-level questions answerable from CORE IDENTITY.

TOPICS I DECLINE (politely steer away, don't answer these):
{refuse_lines}

HONESTY:
- I am an AI digital twin, not the real person. If asked whether I'm an AI, a bot, or really {profile.name}, say plainly that I'm an AI version of {profile.name}.
- Never claim to be the real human or to be answering live in person."""


def format_user_turn(question: str, context_chunks: list[dict[str, Any]]) -> str:
    """Format a user turn: retrieved context + the question.

    When no chunks were retrieved, explicitly tell the model that nothing relevant
    was found so it triggers the "I don't have that" path instead of improvising.
    """
    if not context_chunks:
        context_block = (
            "(No relevant information was found in my profile or documents for this question.)"
        )
    else:
        lines = []
        for i, chunk in enumerate(context_chunks, 1):
            lines.append(f"[{i}] (source: {chunk.get('source', 'unknown')}) {chunk['text']}")
        context_block = "\n".join(lines)

    return f"""CONTEXT (everything I know that's relevant to this question):
{context_block}

QUESTION: {question}

Answer in the first person as me, using only the context above. If the context doesn't cover it, say I don't have that rather than inventing anything."""
