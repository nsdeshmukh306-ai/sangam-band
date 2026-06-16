"""
Data-integrity tests for all 25 drug-herb case studies.

These tests verify the static data files (case_studies.json, herb_dictionary.json,
docking_lookup.json, pgx_rules.json, evidence_corpus/) without requiring live
Band or DeepSeek credentials.  They act as a regression guard: if any data file
is edited the tests catch schema violations, missing coverage, and tier-logic
inconsistencies immediately.
"""

import json
from collections import Counter
from pathlib import Path

import pytest

DATA = Path(__file__).parent.parent / "data"
CORPUS = DATA / "evidence_corpus"


def _load(name: str) -> dict | list:
    return json.loads((DATA / name).read_text())


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def cases() -> list[dict]:
    return _load("case_studies.json")["cases"]


@pytest.fixture(scope="module")
def herb_dict() -> dict:
    return _load("herb_dictionary.json")


@pytest.fixture(scope="module")
def docking() -> dict:
    return _load("docking_lookup.json")


@pytest.fixture(scope="module")
def pgx() -> dict:
    return _load("pgx_rules.json")


# ── Count and structure ───────────────────────────────────────────────────────

def test_exactly_25_cases(cases):
    assert len(cases) == 25, f"Expected 25 cases, got {len(cases)}"


def test_tier_distribution(cases):
    counts = Counter(c["expected_tier"] for c in cases)
    assert counts["RED"] == 10,    f"Expected 10 RED, got {counts['RED']}"
    assert counts["YELLOW"] == 10, f"Expected 10 YELLOW, got {counts['YELLOW']}"
    assert counts["GREEN"] == 5,   f"Expected 5 GREEN, got {counts['GREEN']}"


def test_all_cases_have_required_fields(cases):
    required = {"id", "title", "drugs", "herbs", "patient", "expected_tier",
                "sample_message", "mechanism", "pk_params"}
    for c in cases:
        missing = required - set(c.keys())
        assert not missing, f"Case {c.get('id')} missing fields: {missing}"


def test_all_case_ids_unique(cases):
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids)), "Duplicate case IDs found"


def test_all_tiers_valid(cases):
    valid = {"RED", "YELLOW", "GREEN"}
    for c in cases:
        assert c["expected_tier"] in valid, (
            f"Case {c['id']} has invalid tier '{c['expected_tier']}'"
        )


# ── @mention coverage ─────────────────────────────────────────────────────────

def test_sample_messages_mention_intake_or_pp(cases):
    for c in cases:
        msg = c.get("sample_message", "")
        assert "@Intake" in msg or "@PatientProfile" in msg, (
            f"Case {c['id']} sample_message has no agent @mentions"
        )


def test_sample_messages_have_run_ready_content(cases):
    for c in cases:
        msg = c.get("sample_message", "")
        assert len(msg) >= 40, f"Case {c['id']} sample_message is suspiciously short"


# ── Drug and herb fields ──────────────────────────────────────────────────────

def test_every_case_has_at_least_one_drug_and_herb(cases):
    for c in cases:
        assert c.get("drugs"), f"Case {c['id']} has no drugs"
        assert c.get("herbs"), f"Case {c['id']} has no herbs"


def test_drug_entries_have_compound_field(cases):
    for c in cases:
        for d in c["drugs"]:
            assert "compound" in d, f"Case {c['id']} drug missing 'compound': {d}"


# ── PK params ─────────────────────────────────────────────────────────────────

def test_pk_params_have_required_keys(cases):
    required = {"dose_mg", "ka_per_hr", "ke_baseline_per_hr", "v_l"}
    for c in cases:
        pk = c.get("pk_params", {})
        missing = required - set(pk.keys())
        assert not missing, f"Case {c['id']} pk_params missing: {missing}"


def test_pk_params_are_positive(cases):
    for c in cases:
        pk = c["pk_params"]
        for key in ("dose_mg", "ka_per_hr", "ke_baseline_per_hr", "v_l"):
            val = pk.get(key, 0)
            assert val > 0, f"Case {c['id']} pk_params.{key}={val} must be >0"


# ── Patient fields ────────────────────────────────────────────────────────────

def test_patient_fields(cases):
    required = {"age", "sex", "egfr", "cyp2c9_genotype", "cyp3a4_status"}
    for c in cases:
        pt = c.get("patient", {})
        missing = required - set(pt.keys())
        assert not missing, f"Case {c['id']} patient missing: {missing}"


def test_patient_egfr_range(cases):
    for c in cases:
        egfr = c["patient"]["egfr"]
        assert 0 < egfr <= 130, f"Case {c['id']} suspicious eGFR={egfr}"


# ── Herb dictionary coverage ──────────────────────────────────────────────────

def test_herb_dictionary_has_19_entries(herb_dict):
    entries = {k: v for k, v in herb_dict.items() if not k.startswith("_")}
    assert len(entries) >= 19, f"Expected >=19 herb entries, got {len(entries)}"


def test_herb_entries_have_active_compounds(herb_dict):
    for key, val in herb_dict.items():
        if key.startswith("_"):
            continue
        assert val.get("active_compounds"), (
            f"Herb '{key}' has no active_compounds"
        )
        assert val.get("latin_binomial"), f"Herb '{key}' has no latin_binomial"


# ── Docking lookup ────────────────────────────────────────────────────────────

def test_docking_has_at_least_26_pairs(docking):
    assert len(docking["pairs"]) >= 26, (
        f"Expected >=26 docking pairs, got {len(docking['pairs'])}"
    )


def test_docking_contains_cyp1a2_target(docking):
    targets = {p.get("target") for p in docking["pairs"] if "target" in p}
    assert "CYP1A2" in targets


def test_docking_contains_p_gp_target(docking):
    targets = {p.get("target") for p in docking["pairs"] if "target" in p}
    assert "P-gp" in targets


def test_docking_contains_cyp2c19_target(docking):
    targets = {p.get("target") for p in docking["pairs"] if "target" in p}
    assert "CYP2C19" in targets


def test_docking_pairs_have_mechanism(docking):
    for p in docking["pairs"]:
        if "status" in p and p["status"] == "no_data":
            continue
        assert "mechanism" in p, f"Pair {p} missing mechanism"
        assert p["mechanism"] in {"inhibition", "induction", "negligible"}, (
            f"Unknown mechanism '{p['mechanism']}' in pair {p}"
        )


def test_docking_inhibition_has_negative_delta_g(docking):
    for p in docking["pairs"]:
        if p.get("mechanism") == "inhibition":
            dg = p.get("delta_g_kcal_mol", 0)
            assert dg < 0, (
                f"Inhibition pair {p.get('drug_compound')}+{p.get('herb_compound')} "
                f"has non-negative delta_g={dg}"
            )


# ── PGx rules ─────────────────────────────────────────────────────────────────

def test_pgx_has_cyp2c19_genotypes(pgx):
    assert "cyp2c19_genotypes" in pgx
    genos = pgx["cyp2c19_genotypes"]
    assert "*1/*1" in genos
    assert "*2/*2" in genos
    assert "*17/*17" in genos, "Ultrarapid metabolizer *17/*17 missing"


def test_pgx_has_cyp2c9_genotypes(pgx):
    assert "cyp2c9_genotypes" in pgx
    assert "*1/*1" in pgx["cyp2c9_genotypes"]
    assert "*3/*3" in pgx["cyp2c9_genotypes"]


def test_pgx_clearance_modifiers_range(pgx):
    for section in ("cyp2c9_genotypes", "cyp2c19_genotypes", "cyp3a4_status"):
        for key, rule in pgx.get(section, {}).items():
            cm = rule.get("clearance_modifier", 1.0)
            assert 0 < cm <= 2.0, (
                f"{section}[{key}].clearance_modifier={cm} out of expected range (0, 2]"
            )


# ── Evidence corpus ───────────────────────────────────────────────────────────

def test_evidence_corpus_has_25_files():
    files = list(CORPUS.glob("*.json"))
    assert len(files) >= 25, f"Expected >=25 corpus files, got {len(files)}"


def test_evidence_corpus_has_70_total_findings():
    total = 0
    for f in CORPUS.glob("*.json"):
        data = json.loads(f.read_text())
        total += len(data.get("findings", []))
    assert total >= 70, f"Expected >=70 total findings, got {total}"


def test_evidence_corpus_severity_values():
    valid = {"high", "moderate", "low"}
    for f in CORPUS.glob("*.json"):
        data = json.loads(f.read_text())
        for finding in data.get("findings", []):
            sev = finding.get("severity", "low")
            assert sev in valid, (
                f"{f.name} finding has invalid severity '{sev}'"
            )


def test_evidence_corpus_has_drug_field():
    for f in CORPUS.glob("*.json"):
        data = json.loads(f.read_text())
        assert "drug" in data, f"{f.name} missing top-level 'drug' field"
        assert "herb" in data, f"{f.name} missing top-level 'herb' field"


# ── Spot-check known tiers ────────────────────────────────────────────────────

@pytest.mark.parametrize("case_id,expected_tier", [
    ("case_1_warfarin_guggulu",     "RED"),
    ("case_2_digoxin_licorice",     "RED"),
    ("case_3_metformin_karela",     "YELLOW"),
    ("case_4_tacrolimus_sjw",       "RED"),
    ("case_5_paracetamol_tulsi",    "GREEN"),
    ("case_7_atorvastatin_brahmi",  "RED"),
    ("case_9_methotrexate_neem",    "RED"),
    ("case_13_phenytoin_shankhpushpi", "RED"),
    ("case_14_amoxicillin_garlic",  "GREEN"),
    ("case_15_levothyroxine_shatavari", "GREEN"),
    ("case_22_cyclosporine_sjw",    "RED"),
    ("case_23_furosemide_dandelion","GREEN"),
    ("case_24_amiodarone_fenugreek","RED"),
    ("case_25_cetirizine_ashwagandha", "GREEN"),
])
def test_tier_spot_check(case_id: str, expected_tier: str, cases: list[dict]):
    by_id = {c["id"]: c for c in cases}
    assert case_id in by_id, f"Case '{case_id}' not found in case_studies.json"
    actual = by_id[case_id]["expected_tier"]
    assert actual == expected_tier, (
        f"Case {case_id}: expected tier {expected_tier}, got {actual}"
    )
