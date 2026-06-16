"""Analytical one-compartment oral PK model for @PKPD.

`lookup_pk_params` reads the curated `pk_params` for each demo case's drug from
data/case_studies.json (no external API). `simulate_pk` is the pure math model;
see docs/architecture.md for the induction/inhibition sign-convention design note.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "case_studies.json"


def _load_cases() -> list[dict]:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)["cases"]


def lookup_pk_params(drug_compound: str, cases: list[dict] | None = None) -> dict:
    """Look up curated one-compartment oral PK parameters for a drug.

    Matches `drug_compound` case-insensitively against each demo case's
    `drugs[].compound`. Returns {"status": "no_data", "drug_compound": ...} if no
    case in data/case_studies.json uses that compound.
    """
    cases = cases if cases is not None else _load_cases()
    needle = drug_compound.strip().lower()

    for case in cases:
        for drug in case["drugs"]:
            if drug["compound"].strip().lower() == needle:
                params = case["pk_params"]
                return {
                    "status": "ok",
                    "drug_compound": drug["compound"],
                    "dose_mg": params["dose_mg"],
                    "ka_per_hr": params["ka_per_hr"],
                    "ke_baseline_per_hr": params["ke_baseline_per_hr"],
                    "v_l": params["v_l"],
                }

    return {"status": "no_data", "drug_compound": drug_compound}


def _clearance_change_fraction(delta_g_kcal_mol: float | None, mechanism: str) -> float:
    """Signed fractional change in ke from a docking ΔG + mechanism.

    magnitude = clamp((-delta_g - 6) / 4, 0, 0.7).
    - "inhibition": -magnitude (ke decreases -> AUC increases -> toxicity risk)
    - "induction": +magnitude (ke increases -> AUC decreases -> subtherapeutic risk)
    - anything else (e.g. "negligible", or delta_g_kcal_mol is None): 0
    """
    if delta_g_kcal_mol is None or mechanism not in ("inhibition", "induction"):
        return 0.0

    magnitude = round(max(0.0, min(0.7, (-delta_g_kcal_mol - 6) / 4)), 3)

    return -magnitude if mechanism == "inhibition" else magnitude


def _concentration(dose_mg: float, ka: float, ke: float, v_l: float, t_hr: float) -> float:
    """One-compartment oral concentration C(t), with F=1 (Bateman function)."""
    if abs(ka - ke) < 1e-9:
        return (dose_mg / v_l) * ka * t_hr * math.exp(-ka * t_hr)
    return (dose_mg * ka) / (v_l * (ka - ke)) * (math.exp(-ke * t_hr) - math.exp(-ka * t_hr))


def simulate_pk(
    dose_mg: float,
    ka_per_hr: float,
    ke_baseline_per_hr: float,
    v_l: float,
    clearance_modifier: float,
    delta_g_kcal_mol: float | None = None,
    mechanism: str = "negligible",
    duration_hr: float = 48.0,
    n_points: int = 49,
) -> dict:
    """Simulate baseline-vs-combined one-compartment oral PK and % AUC change.

    `clearance_modifier` is @PatientProfile's pharmacogenomic baseline modifier
    (applied to ke regardless of the herb). `delta_g_kcal_mol`/`mechanism` (from
    @StructuralBio) determine the additional herb-interaction effect on ke via
    `_clearance_change_fraction`:

        ke_patient_baseline = ke_baseline_per_hr * clearance_modifier
        ke_combined = ke_patient_baseline * (1 + clearance_change_fraction)

    AUC (analytical, one-compartment, F=1): AUC = dose / (V * ke).

    This is a simplified illustrative model for the hackathon demo, not validated
    for clinical decisions.
    """
    clearance_change_fraction = _clearance_change_fraction(delta_g_kcal_mol, mechanism)

    ke_patient_baseline = ke_baseline_per_hr * clearance_modifier
    ke_combined = ke_patient_baseline * (1 + clearance_change_fraction)

    auc_baseline = dose_mg / (v_l * ke_patient_baseline)
    auc_combined = dose_mg / (v_l * ke_combined)
    auc_pct_change = (auc_combined - auc_baseline) / auc_baseline * 100

    times = [i * duration_hr / (n_points - 1) for i in range(n_points)]
    concentration_curve = [
        {
            "t_hr": round(t, 2),
            "c_baseline": round(_concentration(dose_mg, ka_per_hr, ke_patient_baseline, v_l, t), 4),
            "c_combined": round(_concentration(dose_mg, ka_per_hr, ke_combined, v_l, t), 4),
        }
        for t in times
    ]

    return {
        "status": "ok",
        "clearance_change_fraction": round(clearance_change_fraction, 3),
        "mechanism": mechanism,
        "ke_patient_baseline_per_hr": round(ke_patient_baseline, 5),
        "ke_combined_per_hr": round(ke_combined, 5),
        "auc_baseline": round(auc_baseline, 4),
        "auc_combined": round(auc_combined, 4),
        "auc_pct_change": round(auc_pct_change, 1),
        "concentration_curve": concentration_curve,
        "disclaimer": (
            "Simplified illustrative one-compartment PK model for decision-support "
            "demo purposes only -- not validated for clinical use."
        ),
    }
