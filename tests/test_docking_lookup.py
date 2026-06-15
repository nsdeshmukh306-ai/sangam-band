from agents.common.docking import lookup_docking


def test_case1_warfarin_guggulsterone_z_inhibition():
    result = lookup_docking("Warfarin", "Guggulsterone Z")

    assert result["status"] == "ok"
    assert result["target"] == "CYP2C9"
    assert result["mechanism"] == "inhibition"
    assert result["delta_g_kcal_mol"] == -8.4


def test_case3_metformin_charantin_is_curated_no_data():
    result = lookup_docking("Metformin", "Charantin")

    assert result["status"] == "no_data"
    assert "notes" in result


def test_case4_tacrolimus_hyperforin_is_induction():
    result = lookup_docking("Tacrolimus", "Hyperforin")

    assert result["status"] == "ok"
    assert result["target"] == "CYP3A4"
    assert result["mechanism"] == "induction"
    assert result["delta_g_kcal_mol"] == -9.1


def test_unknown_pair_returns_no_data():
    result = lookup_docking("Aspirin", "SomeRandomCompound")

    assert result == {
        "status": "no_data",
        "drug_compound": "Aspirin",
        "herb_compound": "SomeRandomCompound",
    }


def test_lookup_is_case_insensitive():
    result = lookup_docking("warfarin", "guggulsterone z")

    assert result["status"] == "ok"
    assert result["delta_g_kcal_mol"] == -8.4
