"""Rule-based pharmacogenomic baseline computation for @PatientProfile.

Reads the curated data/pgx_rules.json (no external API).
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "pgx_rules.json"


def _load_rules() -> dict:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def _match_band(bands: list[dict], value: float) -> dict:
    for band in bands:
        lo, hi = band["min"], band["max"]
        if value >= lo and (hi is None or value <= hi):
            return band
    raise ValueError(f"No band matches value {value!r}")


def compute_pgx_baseline(
    age: int,
    egfr: float,
    cyp2c9_genotype: str,
    cyp3a4_status: str,
    rules: dict | None = None,
) -> dict:
    """Combine CYP2C9 genotype, CYP3A4 status, eGFR, and age into a single
    clearance_modifier (product of the matched band modifiers, rounded to 2
    decimals) plus the union of all non-null risk_flags.

    Returns {"status": "error", "error": "..."} for an unrecognized genotype or
    CYP3A4 status.
    """
    rules = rules if rules is not None else _load_rules()

    cyp2c9 = rules["cyp2c9_genotypes"].get(cyp2c9_genotype)
    if cyp2c9 is None:
        return {"status": "error", "error": f"Unknown CYP2C9 genotype: {cyp2c9_genotype!r}"}

    cyp3a4 = rules["cyp3a4_status"].get(cyp3a4_status)
    if cyp3a4 is None:
        return {"status": "error", "error": f"Unknown CYP3A4 status: {cyp3a4_status!r}"}

    egfr_band = _match_band(rules["egfr_bands"], egfr)
    age_band = _match_band(rules["age_bands"], age)

    modifier = (
        cyp2c9["clearance_modifier"]
        * cyp3a4["clearance_modifier"]
        * egfr_band["clearance_modifier"]
        * age_band["clearance_modifier"]
    )

    risk_flags = [
        flag
        for flag in (cyp2c9["flag"], cyp3a4["flag"], egfr_band["flag"], age_band["flag"])
        if flag
    ]

    return {
        "status": "ok",
        "clearance_modifier": round(modifier, 2),
        "risk_flags": risk_flags,
        "details": {
            "cyp2c9": cyp2c9["label"],
            "cyp3a4": cyp3a4["label"],
            "renal_function": egfr_band["label"],
            "age_group": age_band["label"],
        },
    }
