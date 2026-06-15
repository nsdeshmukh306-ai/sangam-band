"""Curated structural binding-affinity lookup for @StructuralBio's `lookup_docking` tool.

Reads the curated data/docking_lookup.json (no external API / no live docking run).
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "docking_lookup.json"


def _load_pairs() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["pairs"]


def lookup_docking(drug_compound: str, herb_compound: str, pairs: list[dict] | None = None) -> dict:
    """Look up a curated delta_g_kcal_mol / target / mechanism entry for a
    drug-active-compound + herb-active-compound pair (case-insensitive match).

    If the pair is curated with an explicit "status": "no_data" entry, that entry
    (including any "notes") is returned as-is. If the pair is not present at all,
    returns {"status": "no_data", "drug_compound": ..., "herb_compound": ...}.
    """
    pairs = pairs if pairs is not None else _load_pairs()
    needle_drug = drug_compound.strip().lower()
    needle_herb = herb_compound.strip().lower()

    for pair in pairs:
        if (
            pair["drug_compound"].strip().lower() == needle_drug
            and pair["herb_compound"].strip().lower() == needle_herb
        ):
            result = dict(pair)
            result.setdefault("status", "ok")
            return result

    return {
        "status": "no_data",
        "drug_compound": drug_compound,
        "herb_compound": herb_compound,
    }
