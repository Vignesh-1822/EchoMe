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

### Hear it speak (Phase 3 — voice output)

`python -m echome.voice_chat` also speaks each reply in a **cloned voice** built from
`voice/voice_sample.wav` (set via `VOICE_REF`). TTS is pluggable via `TTS_ENGINE`.

> 🔒 **Spoken-consent gate.** Before EchoMe will clone a voice, the enrollment clip must
> contain the speaker saying, *in that same voice*: **"This is my voice, and I give
> permission to use it."** It's verified locally with Whisper and logged (timestamp +
> file hash) to `voice/consent.log`; without it, `voice_chat` runs text-only. Verify a
> clip up front with `python -m echome.consent`. This ties consent to the actual
> voiceprint — a checkbox anyone could tick over a stolen recording wouldn't.

> 🌊 **Watermark.** Every synthesized clip is stamped with an inaudible **AudioSeal**
> watermark (16 kHz output) marking it AI-generated, so a clip in your cloned voice can
> be *proven* synthetic — it survives MP3/resample/trim where metadata wouldn't. One
> watermark + one detector covers both engines (Chatterbox also keeps its native Perth
> mark). Check any file with `python -m echome.watermark <file.wav>`. Controlled by
> `TTS_WATERMARK` (default on) — keep it on for anything shared.

**Voice engines — pick with `TTS_ENGINE`.** Two backends ship behind the same interface,
and the right one depends on where you run:

| | Speed (M3 Air, MPS) | Licensing | Use it for |
|---|---|---|---|
| **`luxtts`** *(default)* | ~1–1.5s per 3s clip (load ~31s) | CC-BY-NC weights → **local / non-commercial only** | Running your own twin locally on Apple Silicon |
| **`chatterbox`** | **75–377s** per 3s clip (load ~66s) | MIT code + MIT weights, auto-watermarked → **shippable** | A public/commercial deploy on a **CUDA GPU host** |

The tradeoff is real: **LuxTTS is fast on Apple Silicon but can't be shipped** (its weights
are distilled from a non-commercial dataset), while **Chatterbox is cleanly licensed but
25–125× slower than real-time on Mac CPU/MPS** — usable only with a CUDA GPU. So LuxTTS is
the local default; switch to Chatterbox (and give it a GPU) when you deploy. Benchmark: 5
consecutive same-sentence gens, model kept loaded, on an M3 Air.

**Default engine — LuxTTS** (install separately; not in the pinned requirements).
LuxTTS pulls two git-only packages (`linacodec`, and a `piper-phonemize` that has no
macOS-arm64 wheel), so the one-line install fails — use this recipe instead:
```bash
# 1. git-only neural codec
pip install git+https://github.com/ysharma3501/LinaCodec.git
# 2. phonemizer with a macOS arm64 wheel (the base piper-phonemize has none)
pip install piper-phonemize-fix
# 3. LuxTTS itself, skipping its unresolvable name-pins...
pip install --no-deps git+https://github.com/ysharma3501/LuxTTS.git
# 4. ...then its real deps that ARE on PyPI
pip install cn2an inflect jieba lhotse librosa tensorboard pypinyin pydub
pip install "setuptools<81"        # keep both torch and zipvoice satisfied
```
> **Note:** pip will warn that zipvoice wants `transformers<=4.57.6` while the RAG stack
> uses `transformers 5.x`. This is a resolver warning only — LuxTTS runs fine at runtime
> on 5.x. **Do not downgrade transformers**; it would break the embedding model.

> ⚠️ **Licensing:** LuxTTS weights are distilled from ZipVoice, whose base model is
> trained on **Emilia (CC BY-NC 4.0 — non-commercial)**. The Apache-2.0 label covers the
> *code*, not the *training data*, so LuxTTS is fine for **local/personal use** but **not
> cleanly licensed for a public or commercial release**. Swap `TTS_ENGINE` to a
> cleanly-licensed engine (e.g. Chatterbox, MIT) before shipping — the pluggable
> interface makes this a one-line change.

**On first launch, expect:**
- **A one-time LuxTTS model download** from Hugging Face (model load + reference
  encoding took ~2.5 min on first run on an M3 Air, mostly download).
- **Per-reply latency:** ~1–1.5s steady-state for a short sentence on **MPS** (Apple
  Silicon GPU; falls back to CPU for the few unsupported vocoder ops, handled
  automatically). The first gen is ~2.6s; the reference encoding is cached across replies.
- If LuxTTS isn't installed or fails to load, `voice_chat` **degrades gracefully to
  text-only** (it prints a notice and keeps working) rather than crashing.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the phase-by-phase build.

## Contributing

Issues and PRs welcome. EchoMe is config-driven — you should be able to run it as *your*
twin without editing any logic. Please keep personal data out of commits.

## License

[MIT](./LICENSE). Note: bundled model weights carry their own licenses — verify before
commercial use.
