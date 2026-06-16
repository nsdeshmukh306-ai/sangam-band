"""Deterministic, dependency-light embedding function for @EvidenceRAG's index.

Avoids chromadb's default ONNX MiniLM embedding function, which requires
downloading a ~80MB model from S3 on first use -- unreliable in this dev
environment (8GB RAM, flaky network) and unnecessary for a ~15-document corpus.
Uses an MD5-hashed bag-of-words vector (the "hashing trick"), which is sufficient
to rank data/evidence_corpus/ findings by drug/herb term overlap.
"""
from __future__ import annotations

import hashlib
import re

import numpy as np
from chromadb import EmbeddingFunction

_WORD_RE = re.compile(r"[a-z0-9]+")


class HashingEmbeddingFunction(EmbeddingFunction):
    """Normalized hashed bag-of-words embedding (no model download required)."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vec = np.zeros(self.dim)
        for word in _WORD_RE.findall(text.lower()):
            idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % self.dim
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec.tolist()

    @staticmethod
    def name() -> str:
        return "sangam-hashing-v1"

    def get_config(self) -> dict:
        return {"dim": self.dim}

    @staticmethod
    def build_from_config(config: dict) -> "HashingEmbeddingFunction":
        return HashingEmbeddingFunction(dim=config["dim"])
