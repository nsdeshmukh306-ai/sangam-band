"""Local Ayurvedic/herbal name lookup, used by @Intake's `lookup_herb` tool.

Reads the curated data/herb_dictionary.json (no external API).
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "herb_dictionary.json"


def _load_herbs() -> dict:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def lookup_herb(name: str, herbs: dict | None = None) -> dict:
    """Resolve a common/Ayurvedic herb name to its Latin binomial + active compounds.

    Matches case-insensitively against each entry's common_name and aliases.
    Returns {"status": "not_found", "name": name} if nothing matches.
    """
    herbs = herbs if herbs is not None else _load_herbs()
    needle = name.strip().lower()

    for key, entry in herbs.items():
        if key.startswith("_"):
            continue
        candidates = [entry["common_name"], *entry.get("aliases", [])]
        if any(needle == candidate.strip().lower() for candidate in candidates):
            return {
                "status": "ok",
                "name": name,
                "common_name": entry["common_name"],
                "latin_binomial": entry["latin_binomial"],
                "active_compounds": entry["active_compounds"],
                "traditional_use": entry.get("traditional_use"),
            }

    return {"status": "not_found", "name": name}
