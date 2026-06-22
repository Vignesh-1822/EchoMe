"""Inspect what retrieval returns for a question — no LLM, just the raw chunks.

Usage:
    python -m scripts.ask "what are your main skills?"
    python -m scripts.ask "what are your main skills?" --k 6 --private
"""

from __future__ import annotations

import argparse

from echome.config import load_config
from echome.rag import retrieve


def main() -> None:
    parser = argparse.ArgumentParser(description="Show retrieved chunks for a question.")
    parser.add_argument("question", help="the question to retrieve context for")
    parser.add_argument("--k", type=int, default=6, help="number of chunks (default 6)")
    parser.add_argument(
        "--private", action="store_true", help="include private-tagged chunks"
    )
    args = parser.parse_args()

    floor = load_config().min_similarity
    results = retrieve(args.question, k=args.k, include_private=args.private)

    print(f'Q: {args.question}')
    print(f"(floor={floor:.2f}, include_private={args.private})\n")
    if not results:
        print(">> no relevant context found — twin should say it doesn't know.")
        return

    print(f"{len(results)} chunk(s) cleared the floor:\n")
    for i, r in enumerate(results, 1):
        snippet = r["text"] if len(r["text"]) <= 280 else r["text"][:277] + "..."
        print(f"[{i}] sim={r['similarity']:.3f}  source={r['source']}  visibility={r['visibility']}")
        print(f"    {snippet}\n")


if __name__ == "__main__":
    main()
