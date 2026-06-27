# EchoMe 🗣️

**Your digital twin — add your profile and your voice, and people can talk to an AI version of you.**

EchoMe is an open-source, config-driven digital twin. Drop in a profile and a short
voice clip, and visitors can have a spoken or text conversation with a clearly-labeled
AI version of you — embedded on your portfolio or shared as a link. It runs free and
local for development; going live needs only an LLM API key and a voice path.

> **Status:** 🚧 Under active construction. Phase 1 (text brain) is done; currently on
> **Phase 2 (speech-to-text input)** — you can now *speak* questions; replies are still text.
> See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full design and roadmap.

---

## Why

AI recruiter screening calls ask everyone the same questions, with no real conversation —
tiring to sit through five times. EchoMe flips that: instead of answering the same
questions over and over, your twin answers them once, on your terms, wherever recruiters
already look.

**Two modes:**
- **Twin** — visitors ask your digital self questions and hear answers in your voice.
- **Prep** — it quizzes you with common screening questions, or drafts your best answers,
  so the *real* calls go better.

## Honest use only

EchoMe is **always labeled as an AI twin**. It is **not** a tool for secretly
impersonating you on a live screening call — that misrepresents you to employers. The
supported uses are the labeled portfolio twin and the interview-prep coach. Voice
enrollment requires consent, and all generated audio is watermarked.

## How it works

```
profile + documents + voice clip   →   index + voice reference
                │
visitor speaks  →  STT  →  retrieve your facts (RAG)  →  LLM answers as you
                                                              │
                                          speak it in your cloned voice
```

The twin answers **only** from your real profile and documents — if it doesn't know
something, it says so rather than making it up.

## Tech stack

| Part | Tool | Cost |
| --- | --- | --- |
| Conversation loop | Pipecat | free |
| Speech-to-text | faster-whisper | free |
| Brain (LLM) | Claude API (prod) / Ollama (dev) | API: paid · local: free |
| Knowledge (RAG) | sentence-transformers + Chroma | free |
| Voice cloning | Chatterbox (XTTS-v2 fallback) | free |
| Backend / widget | FastAPI · React + Vite | free |

Building locally is **~$0** (use Ollama). A live hosted twin has two costs only — the
LLM API and 24/7 voice synthesis. EchoMe is **bring-your-own-key**, so each person who
runs it funds their own usage.

## Quickstart

> Full setup lands with Phase 1. High level:

```bash
git clone https://github.com/<you>/echome.git
cd echome
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # PROVIDER=ollama is free
cp profile.example.yaml profile.yaml # add your info
# drop your resume / writing into documents/

python -m echome.ingest              # build the vector index
python -m echome.chat                # type to your twin
```

### Talk to it (Phase 2 — speech-to-text input)

Speak your questions; the twin still replies as text (voice output is Phase 3).

**System dependency — PortAudio** (for microphone capture):
```bash
# macOS
brew install portaudio        # usually optional: the sounddevice wheel bundles PortAudio,
                              # but install this if mic capture fails to initialize
# Debian/Ubuntu
sudo apt-get install portaudio19-dev
```

Then:
```bash
python -m echome.voice_chat
```

**On first launch, expect:**
- **A one-time Whisper model download** (~140 MB for `base`) to `~/.cache/huggingface`.
  Set the size with `WHISPER_MODEL` in `.env` (`tiny`/`base`/`small`/`medium`).
- **A microphone-permission prompt** from your OS the first time (macOS: System
  Settings → Privacy & Security → Microphone → allow your terminal). If denied, capture
  fails silently — re-enable and retry.
- After the prompt `🎤 listening…`, just speak and pause — it auto-stops on silence,
  prints `you said: …`, then the twin's reply. Say "quit" (or Ctrl-C) to leave.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the phase-by-phase build.

## Contributing

Issues and PRs welcome. EchoMe is config-driven — you should be able to run it as *your*
twin without editing any logic. Please keep personal data out of commits.

## License

[MIT](./LICENSE). Note: bundled model weights carry their own licenses — verify before
commercial use.
