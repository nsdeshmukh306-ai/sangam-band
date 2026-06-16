"""ChromaDB-backed evidence retrieval for @EvidenceRAG's `query_evidence` tool.

Reads the index built by `rag/build_index.py` (run that once before starting
@EvidenceRAG, and again whenever data/evidence_corpus/ changes).
"""
from __future__ import annotations

from pathlib import Path

import chromadb

from rag.build_index import COLLECTION_NAME, DB_DIR
from rag.embeddings import HashingEmbeddingFunction


def query_evidence(drug: str, herb: str, n_results: int = 3, db_dir: Path | None = None) -> list[dict]:
    """Retrieve the most relevant curated evidence findings for a drug + herb pair.

    Returns a list of {"summary", "citation", "severity", "drug", "herb"} dicts,
    most relevant first. Returns [] if the index hasn't been built yet (run
    `uv run python -m rag.build_index` first).
    """
    db_dir = db_dir if db_dir is not None else DB_DIR
    client = chromadb.PersistentClient(path=str(db_dir))

    try:
        collection = client.get_collection(COLLECTION_NAME, embedding_function=HashingEmbeddingFunction())
    except Exception:
        return []

    results = collection.query(query_texts=[f"{drug} {herb} interaction"], n_results=n_results)

    return [
        {
            "summary": metadata["summary"],
            "citation": metadata["citation"],
            "severity": metadata["severity"],
            "drug": metadata["drug"],
            "herb": metadata["herb"],
        }
        for metadata in results["metadatas"][0]
    ]
