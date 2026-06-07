"""data/scripts/build_guidelines_index.py — index the UNHCR guidelines for RAG.

Extracts text from every PDF in specs/data/guidelines/, splits it into overlapping
chunks, embeds each chunk with a local Ollama embedding model, and writes a single
JSON index that the ``guideline_search`` tool queries at runtime (no network).

This grounds the assessment in the *actual* UNHCR Handbook + Guidelines so the
agent cites real guidance instead of inventing law.

Run:  python data/scripts/build_guidelines_index.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import ollama
from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))
from app.config import load_env  # noqa: E402

GUIDELINES_DIR = REPO_ROOT / "specs" / "data" / "guidelines"
OUTPUT = REPO_ROOT / "specs" / "data" / "guidelines_index.json"
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
CHUNK_CHARS = 1100
OVERLAP = 150
BATCH = 32


def _title(path: Path) -> str:
    name = path.stem
    if name.lower() == "handbook":
        return "UNHCR Handbook on Procedures and Criteria for Determining Refugee Status"
    return "UNHCR Guideline " + name


def _chunks(text: str) -> list[str]:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text).strip()
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + CHUNK_CHARS].strip())
        i += CHUNK_CHARS - OVERLAP
    return [c for c in out if len(c) > 120]


def main() -> int:
    load_env()
    client = ollama.Client(host=os.getenv("OLLAMA_HOST"))
    records: list[dict] = []

    pdfs = sorted(GUIDELINES_DIR.glob("*.pdf"))
    print(f"Indexing {len(pdfs)} PDFs with {EMBED_MODEL} …")
    for pdf in pdfs:
        title = _title(pdf)
        try:
            reader = PdfReader(str(pdf))
            text = "\n".join((pg.extract_text() or "") for pg in reader.pages)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {pdf.name}: {exc}")
            continue
        chunks = _chunks(text)
        print(f"  {pdf.name}: {len(chunks)} chunks")
        for start in range(0, len(chunks), BATCH):
            batch = chunks[start:start + BATCH]
            emb = client.embed(model=EMBED_MODEL, input=batch)["embeddings"]
            for chunk, vec in zip(batch, emb):
                records.append({"guideline": title, "source": pdf.name, "text": chunk, "embedding": vec})

    OUTPUT.write_text(json.dumps({"model": EMBED_MODEL, "dim": len(records[0]["embedding"]) if records else 0,
                                  "chunks": records}, ensure_ascii=False))
    print(f"Wrote {len(records)} chunks -> {OUTPUT} ({OUTPUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
