"""Fast deterministic interaction screening for multi-substance input.

This module is intentionally local and synchronous: it expands the curated
case/evidence corpus into pairwise cards, then uses conservative mechanism
rules for drug-drug and herb-herb pairs not present in the demo corpus.
"""
from __future__ import annotations

import itertools
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "data" / "case_studies.json"
EVIDENCE_DIR = ROOT / "data" / "evidence_corpus"

TIER_RANK = {"GREEN": 0, "YELLOW": 1, "RED": 2}

PROFILES: dict[str, dict[str, Any]] = {
    "warfarin": {
        "name": "Warfarin", "kind": "drug", "aliases": ["coumadin", "blood thinner", "anticoagulant"],
        "effects": ["bleeding"], "enzymes": ["CYP2C9"], "transporters": [], "risk": "narrow_therapeutic_index",
    },
    "aspirin": {
        "name": "Aspirin", "kind": "drug", "aliases": ["ecosprin", "antiplatelet"],
        "effects": ["bleeding", "platelet_inhibition"], "enzymes": ["CYP2C9"], "transporters": [],
    },
    "clopidogrel": {
        "name": "Clopidogrel", "kind": "drug", "aliases": ["plavix", "antiplatelet"],
        "effects": ["bleeding", "platelet_inhibition"], "enzymes": ["CYP2C19"], "transporters": [],
    },
    "atorvastatin": {
        "name": "Atorvastatin", "kind": "drug", "aliases": ["statin", "lipitor", "cholesterol"],
        "effects": ["myopathy"], "enzymes": ["CYP3A4"], "transporters": ["P-gp"],
    },
    "simvastatin": {
        "name": "Simvastatin", "kind": "drug", "aliases": ["statin"],
        "effects": ["myopathy"], "enzymes": ["CYP3A4"], "transporters": ["P-gp"],
    },
    "amlodipine": {
        "name": "Amlodipine", "kind": "drug", "aliases": ["bp med", "blood pressure", "antihypertensive"],
        "effects": ["hypotension"], "enzymes": ["CYP3A4"], "transporters": [],
    },
    "tacrolimus": {
        "name": "Tacrolimus", "kind": "drug", "aliases": ["transplant", "immunosuppressant"],
        "effects": ["immunosuppression", "nephrotoxicity"], "enzymes": ["CYP3A4"], "transporters": ["P-gp"], "risk": "narrow_therapeutic_index",
    },
    "cyclosporine": {
        "name": "Cyclosporine", "kind": "drug", "aliases": ["transplant", "immunosuppressant"],
        "effects": ["immunosuppression", "nephrotoxicity"], "enzymes": ["CYP3A4"], "transporters": ["P-gp"], "risk": "narrow_therapeutic_index",
    },
    "digoxin": {
        "name": "Digoxin", "kind": "drug", "aliases": ["cardiac glycoside"],
        "effects": ["arrhythmia"], "enzymes": [], "transporters": ["P-gp"], "risk": "narrow_therapeutic_index",
    },
    "metformin": {
        "name": "Metformin", "kind": "drug", "aliases": ["diabetes", "sugar"],
        "effects": ["glucose_lowering"], "enzymes": [], "transporters": ["OCT"],
    },
    "insulin glargine": {
        "name": "Insulin Glargine", "kind": "drug", "aliases": ["insulin"],
        "effects": ["glucose_lowering"], "enzymes": [], "transporters": [],
    },
    "ciprofloxacin": {
        "name": "Ciprofloxacin", "kind": "drug", "aliases": ["antibiotic", "fluoroquinolone"],
        "effects": ["qt_prolongation"], "enzymes": ["CYP1A2"], "transporters": [],
    },
    "amoxicillin": {
        "name": "Amoxicillin", "kind": "drug", "aliases": ["antibiotic"],
        "effects": [], "enzymes": [], "transporters": [],
    },
    "omeprazole": {
        "name": "Omeprazole", "kind": "drug", "aliases": ["ppi", "gerd"],
        "effects": [], "enzymes": ["CYP2C19"], "transporters": [],
    },
    "phenytoin": {
        "name": "Phenytoin", "kind": "drug", "aliases": ["antiepileptic"],
        "effects": ["seizure_control"], "enzymes": ["CYP2C9", "CYP2C19"], "transporters": [], "risk": "narrow_therapeutic_index",
    },
    "methotrexate": {
        "name": "Methotrexate", "kind": "drug", "aliases": ["rheumatoid", "arthritis"],
        "effects": ["hepatotoxicity", "myelosuppression"], "enzymes": [], "transporters": ["P-gp"], "risk": "narrow_therapeutic_index",
    },
    "paracetamol": {
        "name": "Paracetamol", "kind": "drug", "aliases": ["acetaminophen", "crocin"],
        "effects": ["hepatotoxicity"], "enzymes": ["CYP2E1"], "transporters": [],
    },
    "guggulu": {
        "name": "Guggulu", "kind": "herb", "aliases": ["guggul", "gugulipid"],
        "effects": ["bleeding"], "enzymes": ["CYP2C9", "CYP3A4"], "transporters": [],
        "actions": ["CYP2C9 inhibition", "CYP3A4 modulation"],
    },
    "brahmi": {
        "name": "Brahmi", "kind": "herb", "aliases": ["bacopa", "bacopa monnieri"],
        "effects": ["sedation"], "enzymes": ["CYP3A4"], "transporters": [],
        "actions": ["CYP3A4 inhibition"],
    },
    "arjuna": {
        "name": "Arjuna", "kind": "herb", "aliases": ["terminalia arjuna"],
        "effects": ["hypotension"], "enzymes": ["CYP3A4"], "transporters": [],
        "actions": ["vasodilation", "CYP3A4 inhibition"],
    },
    "st. john's wort": {
        "name": "St. John's Wort", "kind": "herb", "aliases": ["st johns wort", "sjw", "hypericum"],
        "effects": [], "enzymes": ["CYP3A4", "CYP2C9"], "transporters": ["P-gp"],
        "actions": ["CYP3A4 induction", "P-gp induction"],
    },
    "garlic": {
        "name": "Garlic", "kind": "herb", "aliases": ["lasun"],
        "effects": ["bleeding", "platelet_inhibition"], "enzymes": [], "transporters": ["P-gp"],
        "actions": ["mild antiplatelet effect"],
    },
    "ginger": {
        "name": "Ginger", "kind": "herb", "aliases": ["adrak"],
        "effects": ["bleeding", "platelet_inhibition"], "enzymes": [], "transporters": [],
        "actions": ["antiplatelet effect"],
    },
    "ashwagandha": {
        "name": "Ashwagandha", "kind": "herb", "aliases": ["withania"],
        "effects": ["sedation", "bleeding"], "enzymes": ["CYP2C9"], "transporters": [],
        "actions": ["CNS depressant additivity", "platelet modulation"],
    },
    "karela": {
        "name": "Karela", "kind": "herb", "aliases": ["bitter gourd", "bitter melon"],
        "effects": ["glucose_lowering"], "enzymes": [], "transporters": [],
        "actions": ["glucose lowering"],
    },
    "fenugreek": {
        "name": "Fenugreek", "kind": "herb", "aliases": ["methi"],
        "effects": ["glucose_lowering"], "enzymes": [], "transporters": [],
        "actions": ["glucose lowering"],
    },
    "licorice": {
        "name": "Yashtimadhu (Licorice)", "kind": "herb", "aliases": ["yashtimadhu", "mulethi"],
        "effects": ["hypokalemia", "hypertension", "qt_prolongation"], "enzymes": ["CYP1A2"], "transporters": ["P-gp"],
        "actions": ["hypokalemia", "P-gp inhibition"],
    },
    "dandelion": {
        "name": "Dandelion", "kind": "herb", "aliases": ["taraxacum"],
        "effects": ["diuresis"], "enzymes": [], "transporters": [],
        "actions": ["diuretic effect"],
    },
    "tulsi": {
        "name": "Tulsi", "kind": "herb", "aliases": ["holy basil"],
        "effects": [], "enzymes": [], "transporters": [], "actions": ["low interaction signal at dietary exposure"],
    },
    "neem": {
        "name": "Neem", "kind": "herb", "aliases": ["azadirachta"],
        "effects": ["hepatotoxicity"], "enzymes": [], "transporters": ["P-gp"],
        "actions": ["P-gp inhibition", "hepatotoxicity signal"],
    },
    "black pepper": {
        "name": "Black Pepper", "kind": "herb", "aliases": ["piperine", "bioperine"],
        "effects": [], "enzymes": ["CYP2C19", "CYP3A4"], "transporters": ["P-gp"],
        "actions": ["CYP/P-gp inhibition"],
    },
}


def _load_cases() -> list[dict[str, Any]]:
    return json.loads(CASE_PATH.read_text())["cases"]


def _load_evidence() -> dict[tuple[str, str], list[dict[str, Any]]]:
    evidence: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for path in EVIDENCE_DIR.glob("*.json"):
        data = json.loads(path.read_text())
        drug = _canonical_key(data.get("drug", ""))
        herb = _canonical_key(data.get("herb", ""))
        if drug and herb:
            evidence[(drug, herb)] = data.get("findings", [])
    return evidence


def _canonical_key(value: str) -> str:
    needle = re.sub(r"\s+", " ", value.lower().strip())
    if needle in PROFILES:
        return needle
    for key, profile in PROFILES.items():
        names = [profile["name"], *profile.get("aliases", [])]
        if any(needle == alias.lower() for alias in names):
            return key
    return needle


def _known_substances() -> dict[str, dict[str, Any]]:
    substances = {key: profile.copy() for key, profile in PROFILES.items()}
    for case in _load_cases():
        for kind, field in (("drug", "drugs"), ("herb", "herbs")):
            for item in case.get(field, []):
                key = _canonical_key(item["name"])
                substances.setdefault(key, {
                    "name": item["name"], "kind": kind, "aliases": [],
                    "effects": [], "enzymes": [], "transporters": [], "actions": [],
                })
    return substances


def extract_substances(text: str) -> list[dict[str, str]]:
    substances = _known_substances()
    normalized = f" {re.sub(r'[^a-z0-9]+', ' ', text.lower())} "
    found: dict[str, dict[str, str]] = {}
    for key, profile in substances.items():
        candidates = [profile["name"], key, *profile.get("aliases", [])]
        for candidate in candidates:
            token = f" {re.sub(r'[^a-z0-9]+', ' ', candidate.lower()).strip()} "
            if token.strip() and token in normalized:
                found[key] = {"key": key, "name": profile["name"], "kind": profile["kind"]}
                break
    return sorted(found.values(), key=lambda item: (item["kind"], item["name"]))


def screen_interactions(text: str) -> dict[str, Any]:
    substances = extract_substances(text)
    profiles = _known_substances()
    cases = {_case_key(c): c for c in _load_cases()}
    evidence = _load_evidence()

    combinations = []
    for left, right in itertools.combinations(substances, 2):
        combinations.append(_screen_pair(left, right, profiles, cases, evidence))

    combinations.sort(key=lambda c: (-TIER_RANK[c["tier"]], c["left"]["name"], c["right"]["name"]))
    return {
        "substances": substances,
        "combination_count": len(combinations),
        "combinations": combinations,
        "disclaimer": "Fast screening only. Confirm high-risk results against prescribing information and clinician judgement.",
    }


def _case_key(case: dict[str, Any]) -> tuple[str, str]:
    drug = _canonical_key(case["drugs"][0]["name"]) if case.get("drugs") else ""
    herb = _canonical_key(case["herbs"][0]["name"]) if case.get("herbs") else ""
    return drug, herb


def _pair_type(left: dict[str, str], right: dict[str, str]) -> str:
    kinds = sorted([left["kind"], right["kind"]])
    if kinds == ["drug", "drug"]:
        return "drug-drug"
    if kinds == ["herb", "herb"]:
        return "herb-herb"
    return "drug-herb"


def _screen_pair(
    left: dict[str, str],
    right: dict[str, str],
    profiles: dict[str, dict[str, Any]],
    cases: dict[tuple[str, str], dict[str, Any]],
    evidence: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    lkey, rkey = left["key"], right["key"]
    p1, p2 = profiles[lkey], profiles[rkey]
    pair_type = _pair_type(left, right)

    exact_key = (lkey, rkey) if (lkey, rkey) in cases else (rkey, lkey)
    if exact_key in cases:
        case = cases[exact_key]
        findings = evidence.get(exact_key, [])
        return {
            "id": f"{lkey}__{rkey}",
            "type": pair_type,
            "left": left,
            "right": right,
            "tier": case.get("expected_tier", "YELLOW"),
            "confidence": "high",
            "source": "curated_case",
            "mechanism": case.get("mechanism", "Curated interaction case."),
            "clinical_action": _clinical_action(case.get("expected_tier", "YELLOW")),
            "evidence": findings[:3],
        }

    tier, reasons = _rule_reasons(p1, p2)
    return {
        "id": f"{lkey}__{rkey}",
        "type": pair_type,
        "left": left,
        "right": right,
        "tier": tier,
        "confidence": "moderate" if tier != "GREEN" else "low",
        "source": "mechanism_screen",
        "mechanism": " ".join(reasons) if reasons else "No strong overlapping pharmacokinetic or pharmacodynamic signal found in the local profile set.",
        "clinical_action": _clinical_action(tier),
        "evidence": _rule_evidence(p1, p2, reasons),
    }


def _rule_reasons(p1: dict[str, Any], p2: dict[str, Any]) -> tuple[str, list[str]]:
    effects = set(p1.get("effects", [])) & set(p2.get("effects", []))
    enzymes = set(p1.get("enzymes", [])) & set(p2.get("enzymes", []))
    transporters = set(p1.get("transporters", [])) & set(p2.get("transporters", []))
    risks = {p1.get("risk"), p2.get("risk")}
    reasons: list[str] = []
    tier = "GREEN"

    if "bleeding" in effects:
        reasons.append("Both agents carry anticoagulant or antiplatelet bleeding signals; combined use can raise bleeding risk.")
        tier = "RED" if "narrow_therapeutic_index" in risks else "YELLOW"
    if "glucose_lowering" in effects:
        reasons.append("Both agents lower glucose; combined exposure can increase hypoglycaemia risk.")
        tier = max_tier(tier, "YELLOW")
    if "hypotension" in effects:
        reasons.append("Both agents can lower blood pressure; combined use can cause dizziness, syncope, or falls.")
        tier = max_tier(tier, "YELLOW")
    if "sedation" in effects:
        reasons.append("Both agents have CNS-depressant or sedating signals; monitor for impairment.")
        tier = max_tier(tier, "YELLOW")
    if "hepatotoxicity" in effects:
        reasons.append("Both agents have hepatic safety signals; avoid stacking hepatotoxic exposures without monitoring.")
        tier = max_tier(tier, "YELLOW")
    if "hypokalemia" in effects and "qt_prolongation" in (set(p1.get("effects", [])) | set(p2.get("effects", []))):
        reasons.append("Hypokalaemia can amplify QT-prolongation risk.")
        tier = max_tier(tier, "YELLOW")
    if enzymes:
        reasons.append(f"Shared metabolism signal through {', '.join(sorted(enzymes))}; inhibitors or inducers may shift exposure.")
        tier = max_tier(tier, "YELLOW" if "narrow_therapeutic_index" in risks else "GREEN")
    if transporters:
        reasons.append(f"Shared transporter signal through {', '.join(sorted(transporters))}; exposure changes are plausible.")
        tier = max_tier(tier, "YELLOW" if "narrow_therapeutic_index" in risks else "GREEN")
    return tier, reasons


def max_tier(left: str, right: str) -> str:
    return left if TIER_RANK[left] >= TIER_RANK[right] else right


def _clinical_action(tier: str) -> str:
    if tier == "RED":
        return "Avoid or obtain clinician/pharmacist review before co-use; consider INR/drug-level/lab monitoring where applicable."
    if tier == "YELLOW":
        return "Use caution, counsel the patient, and monitor symptoms or labs relevant to the mechanism."
    return "No major signal in the local screen; continue routine counselling and medication reconciliation."


def _rule_evidence(p1: dict[str, Any], p2: dict[str, Any], reasons: list[str]) -> list[dict[str, str]]:
    if not reasons:
        return [{
            "severity": "low",
            "summary": "No curated pair-specific evidence exists in the local Sangam corpus for this combination.",
            "citation": "Sangam local mechanism screen",
        }]
    return [{
        "severity": "moderate",
        "summary": reason,
        "citation": "Sangam local mechanism screen; verify with product labeling and clinical references",
    } for reason in reasons[:3]]
