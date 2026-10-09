<div align="center">

<img src="./echome-logo.svg" width="120" height="120" alt="EchoMe logo"/>

# EchoMe

**Your digital twin — add your profile and voice, let people talk to an AI version of you.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-Frontend-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![Claude](https://img.shields.io/badge/Claude-LLM-7C3AED?style=flat-square)](https://anthropic.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

</div>

---

EchoMe is an open-source, config-driven **AI digital twin**. Drop in a YAML profile, your documents, and a short voice clip — visitors can have a spoken or text conversation with a clearly-labelled AI version of you, embedded on your portfolio or shared as a link.

---

## Why

AI recruiter screening calls ask everyone the same questions over and over. EchoMe flips that: instead of answering the same questions five times, your twin answers them once — on your terms, wherever recruiters already look.

**Two modes:**
- **Twin** — visitors ask your digital self questions and hear answers in your voice
- **Prep** — it quizzes you with common screening questions, or drafts your best answers so live calls go better

---

## How It Works

```
profile + documents + voice clip   →   vector index + voice reference
                │
visitor speaks  →  STT  →  retrieve your facts (RAG)  →  LLM answers as you
                                                              │
                                          speak it in your cloned voice
```

The twin answers **only** from your real profile and documents — if it doesn't know something, it says so.

---

## Tech Stack

| Layer | Tool | Cost |
|---|---|---|
| Conversation loop | Pipecat | Free |
| Speech-to-text | faster-whisper | Free |
| Brain (LLM) | Claude API (prod) / Ollama (dev) | API: paid · Local: free |
| Knowledge (RAG) | sentence-transformers + Chroma | Free |
| Voice cloning | Chatterbox (XTTS-v2 fallback) | Free |
| Backend / widget | FastAPI · React + Vite | Free |

Building locally is **~$0** (use Ollama). A live hosted twin needs only an LLM API key.

---

## Quickstart

```bash
git clone https://github.com/Vignesh-1822/echome.git
cd echome
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                  # PROVIDER=ollama is free
cp profile.example.yaml profile.yaml  # add your info
# drop your resume / writing into documents/

python -m echome.ingest               # build the vector index
python -m echome.chat                 # type to your twin
```

**Talk to it (speech input):**
```bash
python -m echome.voice_chat
```

---

## Voice & Ethics

> 🔒 **Spoken-consent gate.** Before EchoMe clones a voice, the enrollment clip must contain the speaker saying: *"This is my voice, and I give permission to use it."* Verified locally with Whisper and logged to `voice/consent.log`.

> 🌊 **Watermark.** Every synthesized clip is stamped with an inaudible AudioSeal watermark marking it AI-generated — survives MP3/resample/trim where metadata wouldn't.

EchoMe is **always labelled as an AI twin**. It is not a tool for secretly impersonating anyone on a live call.

---

## License

[MIT](LICENSE) — Note: bundled model weights carry their own licenses; verify before commercial use.
