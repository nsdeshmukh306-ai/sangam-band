from agents.common.pgx import compute_pgx_baseline
from agents.common.pkpd import (
    _clearance_change_fraction,
    lookup_pk_params,
    simulate_pk,
)


def test_clearance_change_fraction_inhibition():
    assert _clearance_change_fraction(-8.4, "inhibition") == -0.6


def test_clearance_change_fraction_induction_clamped():
    # magnitude = (9.1 - 6) / 4 = 0.775 -> clamped to 0.7
    assert _clearance_change_fraction(-9.1, "induction") == 0.7


def test_clearance_change_fraction_negligible():
    assert _clearance_change_fraction(-4.2, "negligible") == 0.0


def test_clearance_change_fraction_no_data():
    assert _clearance_change_fraction(None, "inhibition") == 0.0


def test_simulate_pk_no_change():
    result = simulate_pk(
        dose_mg=100, ka_per_hr=1.0, ke_baseline_per_hr=0.1, v_l=10,
        clearance_modifier=1.0, delta_g_kcal_mol=None, mechanism="negligible",
    )
    assert result["status"] == "ok"
    assert result["clearance_change_fraction"] == 0.0
    assert result["auc_baseline"] == 100.0
    assert result["auc_combined"] == 100.0
    assert result["auc_pct_change"] == 0.0
    assert len(result["concentration_curve"]) == 49
    assert result["concentration_curve"][0] == {"t_hr": 0.0, "c_baseline": 0.0, "c_combined": 0.0}


def test_simulate_pk_inhibition_increases_auc():
    result = simulate_pk(
        dose_mg=100, ka_per_hr=1.0, ke_baseline_per_hr=0.1, v_l=10,
        clearance_modifier=1.0, delta_g_kcal_mol=-8.4, mechanism="inhibition",
    )
    assert result["clearance_change_fraction"] == -0.6
    assert result["ke_combined_per_hr"] == 0.04
    assert result["auc_combined"] == 250.0
    assert result["auc_pct_change"] == 150.0


def test_simulate_pk_induction_decreases_auc():
    result = simulate_pk(
        dose_mg=100, ka_per_hr=1.0, ke_baseline_per_hr=0.1, v_l=10,
        clearance_modifier=1.0, delta_g_kcal_mol=-9.1, mechanism="induction",
    )
    assert result["clearance_change_fraction"] == 0.7
    assert result["ke_combined_per_hr"] == 0.17
    assert result["auc_pct_change"] == -41.2


def test_lookup_pk_params_warfarin():
    result = lookup_pk_params("Warfarin")
    assert result == {
        "status": "ok",
        "drug_compound": "Warfarin",
        "dose_mg": 5,
        "ka_per_hr": 1.0,
        "ke_baseline_per_hr": 0.0173,
        "v_l": 10,
    }


def test_lookup_pk_params_unknown():
    assert lookup_pk_params("NotADrug") == {"status": "no_data", "drug_compound": "NotADrug"}


def test_case1_warfarin_guggulu_toxicity_direction():
    pgx = compute_pgx_baseline(age=68, egfr=55, cyp2c9_genotype="*1/*3", cyp3a4_status="normal")
    pk_params = lookup_pk_params("Warfarin")

    result = simulate_pk(
        dose_mg=pk_params["dose_mg"],
        ka_per_hr=pk_params["ka_per_hr"],
        ke_baseline_per_hr=pk_params["ke_baseline_per_hr"],
        v_l=pk_params["v_l"],
        clearance_modifier=pgx["clearance_modifier"],
        delta_g_kcal_mol=-8.4,
        mechanism="inhibition",
    )

    assert result["clearance_change_fraction"] == -0.6
    # Inhibition -> ke decreases -> AUC increases -> toxicity risk.
    assert result["auc_pct_change"] > 0


def test_case4_tacrolimus_sjw_subtherapeutic_direction():
    pgx = compute_pgx_baseline(age=45, egfr=85, cyp2c9_genotype="*1/*1", cyp3a4_status="reduced")
    pk_params = lookup_pk_params("Tacrolimus")

    result = simulate_pk(
        dose_mg=pk_params["dose_mg"],
        ka_per_hr=pk_params["ka_per_hr"],
        ke_baseline_per_hr=pk_params["ke_baseline_per_hr"],
        v_l=pk_params["v_l"],
        clearance_modifier=pgx["clearance_modifier"],
        delta_g_kcal_mol=-9.1,
        mechanism="induction",
    )

    assert result["clearance_change_fraction"] == 0.7
    # Induction -> ke increases -> AUC decreases -> subtherapeutic/efficacy-loss risk.
    assert result["auc_pct_change"] < 0
