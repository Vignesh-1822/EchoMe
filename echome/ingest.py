"""Build the local vector index from a user's profile + documents.

This is the *ingestion* half of RAG (Phase 1, Step 3). It gathers content from
two sources, chunks/embeds it locally, and writes it to a persistent Chroma
collection. Retrieval and chat come in later steps — nothing here searches.

Sources:
  (a) profile facts (from profile.py) — public AND private, since the index lives
      locally on the user's machine. Each fact is its own unit, tagged with its
      visibility so retrieval can filter public vs. private later.
  (b) every readable file in documents/ — chunked with overlap.

Run with:  python -m echome.ingest
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from echome.config import load_config
from echome.profile import load_profile

COLLECTION_NAME = "echome"
DOCUMENTS_DIR = "documents"

CHUNK_SIZE = 800
CHUNK_OVERLAP = 120

# Plain-text extensions handled directly; .pdf/.docx are handled specially below.
TEXT_EXTENSIONS = {".md", ".txt"}


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace to single spaces and trim."""
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split normalized text into ~`size`-char chunks with ~`overlap`-char overlap."""
    text = normalize_whitespace(text)
    if not text:
        return []
    if len(text) <= size:
        return [text]

    step = size - overlap
    chunks = []
    for start in range(0, len(text), step):
        chunk = text[start : start + size]
        if chunk.strip():
            chunks.append(chunk)
        if start + size >= len(text):
            break
    return chunks


# --- File readers -----------------------------------------------------------


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _read_docx(path: Path) -> str | None:
    try:
        import docx  # python-docx, optional
    except ImportError:
        print(f"  ! skipping {path.name}: python-docx not installed")
        return None
    document = docx.Document(str(path))
    return "\n".join(p.text for p in document.paragraphs)


def read_document(path: Path) -> str | None:
    """Return the raw text of a supported document, or None if unsupported/empty."""
    ext = path.suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8", errors="ignore")
    if ext == ".pdf":
        return _read_pdf(path)
    if ext == ".docx":
        return _read_docx(path)
    return None


# --- Content gathering ------------------------------------------------------


def _fact_to_text(key: str, value: Any) -> str:
    """Render a single profile fact as a readable, searchable sentence."""
    label = key.replace("_", " ")
    if isinstance(value, (list, tuple)):
        return f"{label}: " + ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        inner = "; ".join(f"{k}: {v}" for k, v in value.items())
        return f"{label}: {inner}"
    return f"{label}: {value}"


def gather_profile_units() -> list[dict[str, Any]]:
    """One unit per profile fact (plus identity), tagged with visibility."""
    profile = load_profile()
    public_keys = set(profile.public_keys)
    units: list[dict[str, Any]] = []

    # Identity fields are inherently public context for the twin.
    identity = {
        "name": profile.name,
        "headline": profile.headline,
        "location": profile.location,
        "pronouns": profile.pronouns,
    }
    for key, value in identity.items():
        if value:
            units.append(
                {
                    "id": f"profile-{key}",
                    "text": _fact_to_text(key, value),
                    "metadata": {"source": "profile", "type": "profile_fact", "visibility": "public"},
                }
            )

    # Structured facts: public if listed in visibility.public, else private.
    for key, value in profile.facts.items():
        visibility = "public" if key in public_keys else "private"
        units.append(
            {
                "id": f"profile-fact-{key}",
                "text": _fact_to_text(key, value),
                "metadata": {"source": "profile", "type": "profile_fact", "visibility": visibility},
            }
        )
    return units


def gather_document_units(documents_dir: str | Path = DOCUMENTS_DIR) -> list[dict[str, Any]]:
    """Chunk every readable file in documents/ (skipping dotfiles/unknown types)."""
    docs_path = Path(documents_dir)
    units: list[dict[str, Any]] = []
    if not docs_path.exists():
        return units

    for path in sorted(docs_path.iterdir()):
        if not path.is_file() or path.name.startswith("."):
            continue  # skip dirs, dotfiles, and .gitkeep
        text = read_document(path)
        if text is None:
            if path.suffix.lower() not in {".docx"}:  # docx already warned
                print(f"  ! skipping {path.name}: unsupported type")
            continue
        chunks = chunk_text(text)
        if not chunks:
            print(f"  ! skipping {path.name}: no extractable text")
            continue
        for i, chunk in enumerate(chunks):
            units.append(
                {
                    "id": f"{path.name}-{i}",
                    "text": chunk,
                    "metadata": {"source": path.name, "type": "document", "visibility": "public"},
                }
            )
    return units


# --- Index build ------------------------------------------------------------


def build_index() -> dict[str, int]:
    """Gather, embed, and (re)build the persistent Chroma collection from scratch."""
    config = load_config()

    print("Gathering content...")
    units = gather_profile_units() + gather_document_units()
    if not units:
        print("No content found. Add a profile.yaml and/or files in documents/.")
        return {}

    print(f"Embedding {len(units)} chunks with '{config.embed_model}'...")
    model = SentenceTransformer(config.embed_model)
    embeddings = model.encode(
        [u["text"] for u in units], show_progress_bar=False, normalize_embeddings=True
    ).tolist()

    print(f"Writing collection '{COLLECTION_NAME}' to '{config.index_dir}'...")
    client = chromadb.PersistentClient(path=config.index_dir)
    # Rebuild fresh each run so the index always matches the current inputs.
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )
    collection.add(
        ids=[u["id"] for u in units],
        documents=[u["text"] for u in units],
        embeddings=embeddings,
        metadatas=[u["metadata"] for u in units],
    )

    return Counter(u["metadata"]["source"] for u in units)


def main() -> None:
    breakdown = build_index()
    if not breakdown:
        return
    total = sum(breakdown.values())
    print(f"\nIndexed {total} chunks into '{COLLECTION_NAME}'.")
    print("By source:")
    for source, count in sorted(breakdown.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {count:>4}  {source}")


if __name__ == "__main__":
    main()
