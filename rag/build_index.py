"""Build the local ChromaDB index for @EvidenceRAG from data/evidence_corpus/*.json.

Run once before starting @EvidenceRAG (and again whenever the corpus changes):

    uv run python -m rag.build_index
"""
from __future__ import annotations

import json
from pathlib import Path

import chromadb

from rag.embeddings import HashingEmbeddingFunction

EVIDENCE_DIR = Path(__file__).resolve().parents[1] / "data" / "evidence_corpus"
DB_DIR = Path(__file__).resolve().parents[1] / "data" / "chroma_db"
COLLECTION_NAME = "evidence_corpus"


def build_index(evidence_dir: Path = EVIDENCE_DIR, db_dir: Path = DB_DIR) -> int:
    """(Re)build the evidence_corpus collection. Returns the number of findings indexed."""
    client = chromadb.PersistentClient(path=str(db_dir))

    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = client.create_collection(
        COLLECTION_NAME, embedding_function=HashingEmbeddingFunction()
    )

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []

    for path in sorted(evidence_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        drug, herb = data["drug"], data["herb"]
        for i, finding in enumerate(data["findings"]):
            ids.append(f"{path.stem}_{i}")
            documents.append(f"{drug} + {herb}: {finding['summary']}")
            metadatas.append(
                {
                    "drug": drug,
                    "herb": herb,
                    "citation": finding["citation"],
                    "severity": finding["severity"],
                    "summary": finding["summary"],
                }
            )

    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


if __name__ == "__main__":
    n = build_index()
    print(f"Indexed {n} evidence findings into {DB_DIR}")
