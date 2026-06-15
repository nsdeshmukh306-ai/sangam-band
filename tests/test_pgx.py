import pytest

from agents.common.pgx import compute_pgx_baseline


def test_case1_warfarin_patient_intermediate_metabolizer_moderate_renal():
    # Case 1: 68F, eGFR 55, CYP2C9 *1/*3, CYP3A4 normal
    result = compute_pgx_baseline(age=68, egfr=55, cyp2c9_genotype="*1/*3", cyp3a4_status="normal")

    assert result["status"] == "ok"
    assert result["clearance_modifier"] == pytest.approx(0.41, abs=0.01)
    assert "intermediate_cyp2c9_metabolizer" in result["risk_flags"]
    assert "moderate_renal_impairment" in result["risk_flags"]
    assert "advanced_age" in result["risk_flags"]


def test_case4_tacrolimus_patient_reduced_cyp3a4():
    # Case 4: 45M, eGFR 85, CYP2C9 *1/*1, CYP3A4 reduced
    result = compute_pgx_baseline(age=45, egfr=85, cyp2c9_genotype="*1/*1", cyp3a4_status="reduced")

    assert result["status"] == "ok"
    assert result["clearance_modifier"] == pytest.approx(0.675, abs=0.01)
    assert "reduced_cyp3a4_activity" in result["risk_flags"]
    assert "mild_renal_impairment" in result["risk_flags"]
    assert "intermediate_cyp2c9_metabolizer" not in result["risk_flags"]


def test_normal_healthy_adult_has_no_risk_flags():
    # Case 5: 30F, eGFR 100, CYP2C9 *1/*1, CYP3A4 normal
    result = compute_pgx_baseline(age=30, egfr=100, cyp2c9_genotype="*1/*1", cyp3a4_status="normal")

    assert result["status"] == "ok"
    assert result["clearance_modifier"] == pytest.approx(1.0)
    assert result["risk_flags"] == []


def test_unknown_genotype_returns_error():
    result = compute_pgx_baseline(age=50, egfr=90, cyp2c9_genotype="*9/*9", cyp3a4_status="normal")

    assert result["status"] == "error"
    assert "*9/*9" in result["error"]


def test_unknown_cyp3a4_status_returns_error():
    result = compute_pgx_baseline(age=50, egfr=90, cyp2c9_genotype="*1/*1", cyp3a4_status="unknown")

    assert result["status"] == "error"
