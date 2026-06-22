# CLAUDE.md — build instructions for EchoMe

You (Claude Code) are the developer on this repo. This file is your standing brief.
**`ARCHITECTURE.md` is the source of truth** — read it fully before scaffolding or
changing structure. This file tells you *how to work*; that file tells you *what to build*.

---

## What EchoMe is (one paragraph)

An open-source **digital twin**. A person adds a profile + a short voice clip, and
visitors can have a spoken or text conversation with a clearly-labeled AI version of
them — embedded on a portfolio or shared as a link. It is **config-driven**: nothing
about any specific person is hardcoded; swapping the profile + voice clip changes whose
twin it is.

## Current status

- **Phase: 1 (text brain).** Build the text-only twin first; no audio yet.
- Build order is fixed (see ARCHITECTURE.md §7). Do **not** jump ahead to voice or the
  widget until the current phase's definition of done is met.

---

## Golden rules — enforce these in every change

These are non-negotiable invariants. If a request conflicts with one, flag it.

1. **No-hallucination guardrail is the heart of the product.** The twin answers ONLY
   from retrieved profile/document context. When retrieval finds nothing relevant, it
   must say so in first person ("I don't have that in here") — never invent jobs,
   skills, dates, numbers, or opinions. A twin that fabricates facts about a real person
   is worse than no twin. Treat this as the primary thing every phase must preserve.
2. **Bring-your-own-key. Never hardcode or commit secrets.** Keys live in `.env`
   (gitignored). The LLM provider is pluggable: `ollama` (free, local) for dev,
   `claude` (API) for production. Code must run on both via config alone.
3. **Config-driven, never person-specific.** No real names, facts, or voices baked into
   code. Everything personal comes from `profile.yaml`, `documents/`, and `voice/`.
4. **Protect personal data.** `.env`, `profile.yaml`, `documents/*`, `voice/*`, and the
   index dir are gitignored. Never commit a real person's data. Only `*.example.*`
   templates are tracked.
5. **Honesty by design.** The twin is always labeled as an AI. Do **not** build features
   aimed at covertly impersonating the person on live calls (e.g. auto-answering a real
   recruiter screening as if human). The supported use cases are the labeled portfolio
   twin and the interview-prep simulator.
6. **Voice consent + watermark (Phase 3+).** Voice enrollment requires a logged consent
   confirmation; all synthesized audio is watermarked (AudioSeal).
7. **Don't route real-time voice through a coding CLI.** The live conversation uses a
   streaming LLM **API**, not Claude Code / Gemini CLI. (The CLI is for building this
   repo and for the optional free *text* onboarding/setup skill — not the runtime voice
   loop.)
8. **Don't scrape LinkedIn.** Ingest the user's own "Download your data" export or a
   saved profile PDF placed in `documents/`.

---

## Tech stack (see ARCHITECTURE.md §4 for the full table)

🟢 free · 🔴 paid
- Orchestration: **Pipecat** 🟢 · STT: **faster-whisper** 🟢
- Brain: **Claude API** 🔴 (prod) / **Ollama** 🟢 (dev) — pluggable
- RAG: **sentence-transformers** + **Chroma** 🟢
- Voice clone: **Chatterbox** 🟢 (XTTS-v2 fallback) · watermark **AudioSeal** 🟢
- Backend: **FastAPI** 🟢 · Frontend/widget: **React + Vite** 🟢
- Deploy (later): Vercel (frontend) + Render (backend) + cloud TTS or GPU host

## Repo conventions

- **Language:** Python for the backend/pipeline; JS/React for the widget.
- **Structure:** follow the layout in ARCHITECTURE.md §4/§5. Keep layers separated
  (`onboarding/`, `brain/`, `voice/`, `pipeline/`). The LLM provider and the TTS engine
  are each behind a single swappable interface.
- **Secrets/config:** `.env` + an `.env.example` that's always kept in sync.
- **Commits:** small, focused, conventional-commit style (`feat:`, `fix:`, `docs:`).
- **Dependencies:** prefer the stack above; if you add a library, note why in the PR.

## Definition of done per phase

- **Phase 1:** `python -m <pkg>.chat` loads a profile + documents, retrieves context,
  and answers in first person. **Acceptance test: ask something NOT in the profile —
  the twin must admit it doesn't know rather than invent.** Provider switches between
  ollama and claude via `.env` with no code change.
- Later phases: see ARCHITECTURE.md §7. Each phase must keep all golden rules intact.

## When unsure

Ask, or default to the most private/honest/cheapest option. Re-read ARCHITECTURE.md
before structural changes. Keep this file and the README updated as the build evolves.
