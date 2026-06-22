# EchoMe — Your Digital Twin

> **Working title — rename freely.**
> An open-source digital twin. A person supplies a profile + a short voice clip, and others can have a spoken (or text) conversation with an AI version of them — on a portfolio page, a shareable link, or locally. Clearly labeled as an AI, in the person's own voice.

---

## 1. What we're building

**One line:** *"Add your profile and your voice, and people can talk to a digital version of you — embedded on your site or shared as a link."*

The whole project is **config-driven**: nothing about any specific person is hardcoded. Swap two inputs (a profile + a voice clip) and the same code becomes a different person's twin. That's what makes it reusable by anyone who clones the repo.

### The product shape (decided)

The flagship is a **"talk to my digital twin" widget** — an embeddable `<script>` snippet for a portfolio plus a shareable link — not a standalone webapp. The webapp is just the demo/host page. This integrates where recruiters and visitors already look and is the version where "everyone uses it" is realistic.

**Two modes:**

| Mode | Who it's for | How it runs |
| --- | --- | --- |
| **Twin (flagship)** | Visitors on your site/link | Spoken or text conversation; answers about you, in your voice |
| **Prep (secondary)** | You | Quizzes you with common screening questions, or drafts your best STAR answers |

### Origin & the honesty line

The idea came from repetitive AI-recruiter screening calls. **The twin is a transparent, labeled representation of you that answers questions on your terms** — it is *not* a tool for secretly impersonating you on a live screening call, which would misrepresent you to an employer and can carry real consequences. The honest framing (a labeled portfolio twin + an interview-prep coach) is more useful and more shareable anyway.

---

## 2. The two technical tracks

We settled a key distinction during design:

- **Operator track (CLI, $0):** setup, profile-building, customization, and a *text* "ask about me" can run as a **career-ops-style skill** inside the operator's own coding CLI (Claude Code / Gemini CLI), using that CLI's own auth. No API key. Great for onboarding and Phase 1.
- **Visitor track (API):** the live spoken conversation for outside visitors needs a real **LLM API** (Claude) — because it's a real-time audio loop (sub-~800ms, streaming, interruptions) and because visitors won't be in your terminal. This is the one genuinely paid piece.

---

## 3. Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  LAYER 0 — ONBOARDING / CONFIG  (per user, runs once)          │
│  profile.yaml  ·  documents/ folder  ·  voice clip             │
│  Fill via: CLI onboarding (free)  OR  webapp form              │
│  → builds: voice_ref.wav, profile, vector index                │
└───────────────────────────┬──────────────────────────────────┘
                            │ loaded at runtime by user_id
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  LAYER 3 — ORCHESTRATION  (Pipecat: VAD · turns · streaming)   │
└───┬────────────────────┬───────────────────────┬─────────────┘
    ▼                    ▼                       ▼
┌─────────┐    ┌────────────────────┐    ┌──────────────────────┐
│ STT     │    │  BRAIN (Layer 2)   │    │  TTS / VOICE CLONE   │
│ Whisper │───▶│  LLM (API) + RAG   │───▶│  speaks in your voice│
│         │    │  + persona/guards  │    │  + watermark         │
└─────────┘    └────────────────────┘    └──────────────────────┘
```

A single turn: visitor speaks → VAD detects end of speech → Whisper transcribes → RAG pulls relevant profile facts → LLM answers in first person as you (no inventing) → Chatterbox speaks it in your voice → streamed back, interruptible.

---

## 4. Final tech stack (with cost)

🟢 Free · 🟡 Free tier → paid · 🔴 Paid

### Build (all runs locally at ~$0)

| Layer | Tool | Cost | Notes |
| --- | --- | --- | --- |
| Orchestration | **Pipecat** (+ Silero VAD, SmallWebRTC) | 🟢 | BSD-2 backbone |
| STT | **faster-whisper** (local) | 🟢 | Groq/Deepgram optional cloud swap (🟡) |
| LLM brain | **Anthropic Claude API** | 🔴 | Bring-your-own-key; the core paid piece |
| LLM (dev) | **Ollama** (local) | 🟢 | Use during build to stay at $0 |
| Embeddings | **sentence-transformers** | 🟢 | Tiny local model |
| Vector store | **Chroma** (or LanceDB) | 🟢 | Embedded, no server |
| TTS clone | **Chatterbox** (default) / XTTS-v2 (fallback) | 🟢 | MIT, clones from a short clip |
| TTS (hosted) | **Cartesia / Fish Audio** | 🔴 (free tier) | Only if voice is offloaded to cloud |
| Watermark | **AudioSeal** | 🟢 | Marks output as AI |
| Profile | profile.yaml + `documents/` + CLI onboarding | 🟢 | Your template + files |
| Frontend/widget | **React + Vite** | 🟢 | Page + embeddable script |
| Backend | **FastAPI** | 🟢 | Hosts the pipeline |
| Tooling | Git / GitHub / Docker | 🟢 | — |

### Deploy (later)

| Purpose | Tool | Cost |
| --- | --- | --- |
| Frontend host | Vercel | 🟢 free tier |
| Backend host | Render | 🟡 free → paid at scale |
| Voice GPU (self-host TTS) | Modal / Replicate / RunPod | 🟡 free credits → paid |
| Voice (cloud API instead) | Cartesia / Fish Audio | 🔴 free tier |

### Cost summary
- **Building locally:** effectively **$0** (use Ollama as the dev brain).
- **Your live public twin:** exactly two costs — **(1) the LLM API** and **(2) 24/7 voice synthesis** (cloud TTS API or a GPU host). Everything else sits on free tiers.
- **Other users:** design **bring-your-own-key** so each person funds their own usage — you never pay for theirs.

---

## 5. Inputs: how a user configures their twin

### Profile (Layer 0)
- **Storage:** `profile.yaml` (structured facts + style + boundaries) **plus** a `documents/` folder for `resume.pdf`, cover letters, writing samples → ingested into the vector index.
- **Filling it:** **CLI onboarding** (open in Claude Code / Gemini CLI, it reads your resume and fills the template by chatting — free) is the nicest path; a webapp form is the fallback for non-technical users.
- **LinkedIn:** do **not** scrape it (against ToS, actively blocked). Use LinkedIn's own *"Download your data"* export or a saved profile PDF dropped into `documents/`.

### Voice clip
- **Baseline:** drop `voice_sample.wav`/`.mp3` into a `voice/` folder (universal, no UI).
- **Upgrade:** in-browser guided recording in the widget ("read this for ~15s") — added later.
- **Quality:** 10–20s, clean, single speaker, no music. Clean-and-short beats long-and-noisy.

---

## 6. The Brain (Layer 2) — quality lives here

- **RAG:** embed the question → search the user's index → pass only retrieved chunks as "what you know about yourself."
- **Persona:** system prompt frames the LLM to speak **first person as the user**, in the profile's style.
- **Guardrails (critical):** if retrieval finds nothing relevant, the twin says *"I don't actually know that about myself"* instead of inventing — the single rule that separates a useful tool from a liability. Plus public/private fact scoping and the profile's `refuse_topics`.

---

## 7. Build roadmap

| Phase | Goal | Build | Cost |
| --- | --- | --- | --- |
| **1. Text brain** ← start here | It knows you | profile + documents + RAG + LLM, **text only**, runnable in terminal | 🟢 $0 (Ollama) |
| 2. Ears | It listens | faster-whisper STT | 🟢 |
| 3. Voice | It sounds like you | voice enrollment + Chatterbox + watermark | 🟢 local |
| 4. Real-time | It converses | wire through Pipecat (VAD, streaming, interruption) | 🟢 local |
| 5. Widget | Others use it | embeddable widget + shareable link + onboarding UI | 🟡 deploy |
| 6. Prep mode | Second use case | screening-question simulator / STAR drafting | 🟢 |

**Rule:** get Phase 1 perfect (especially the no-hallucination guardrail) in text before adding any audio. Debugging "why did it invent a fact" is ten times easier without a voice pipeline in the way.

---

## 8. Responsibility (required for a public voice-cloning repo)

- **Consent gate** at enrollment ("this is my voice / I have permission"), logged.
- **Watermark** every output (AudioSeal) as AI-generated.
- **Always labeled** as an AI twin, never presented as the real person live.
- **Local-first / privacy:** profile data stays on the user's machine; `store/`, `data/`, `documents/`, `voice/` are gitignored.
- **No covert-impersonation** use case (e.g., secretly taking real screening calls).
- **License:** MIT (max adoption). Verify bundled model licenses separately.

---

## 9. Next step
Phase 1 — the local, $0 text twin: load profile + documents, build the RAG index, and chat in first person via a pluggable provider (Ollama free by default, Claude optional). Code scaffolded alongside this doc.
