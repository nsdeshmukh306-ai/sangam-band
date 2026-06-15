from agents.common.herbs import lookup_herb


def test_lookup_herb_by_common_name():
    result = lookup_herb("Guggulu")

    assert result["status"] == "ok"
    assert result["latin_binomial"] == "Commiphora wightii"
    assert "Guggulsterone Z" in result["active_compounds"]
    assert "Guggulsterone E" in result["active_compounds"]


def test_lookup_herb_by_alias_case_insensitive():
    result = lookup_herb("st. john's wort")

    assert result["status"] == "ok"
    assert result["latin_binomial"] == "Hypericum perforatum"
    assert "Hyperforin" in result["active_compounds"]


def test_lookup_herb_by_latin_alias():
    result = lookup_herb("Bitter Gourd")

    assert result["status"] == "ok"
    assert result["latin_binomial"] == "Momordica charantia"


def test_lookup_herb_not_found():
    result = lookup_herb("NotAHerb")

    assert result == {"status": "not_found", "name": "NotAHerb"}
