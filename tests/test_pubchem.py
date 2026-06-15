from unittest.mock import Mock, patch

import requests

from agents.common.pubchem import lookup_pubchem


def _mock_response(status_code: int, json_data: dict | None = None) -> Mock:
    response = Mock()
    response.status_code = status_code
    if json_data is not None:
        response.json.return_value = json_data
    return response


def test_lookup_pubchem_success():
    payload = {
        "PropertyTable": {
            "Properties": [
                {
                    "CID": 54678486,
                    "IUPACName": "[(2R,3R)-2-hydroxy...]",
                    "CanonicalSMILES": "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O",
                    "MolecularFormula": "C19H16O4",
                }
            ]
        }
    }
    with patch("agents.common.pubchem.requests.get", return_value=_mock_response(200, payload)):
        result = lookup_pubchem("Warfarin")

    assert result["status"] == "ok"
    assert result["pubchem_cid"] == 54678486
    assert result["molecular_formula"] == "C19H16O4"
    assert result["canonical_smiles"].startswith("CC(=O)")


def test_lookup_pubchem_not_found():
    with patch("agents.common.pubchem.requests.get", return_value=_mock_response(404)):
        result = lookup_pubchem("Notadrugxyz")

    assert result == {"status": "not_found", "name": "Notadrugxyz"}


def test_lookup_pubchem_request_error():
    with patch(
        "agents.common.pubchem.requests.get",
        side_effect=requests.exceptions.ConnectionError("boom"),
    ):
        result = lookup_pubchem("Warfarin")

    assert result["status"] == "error"
    assert result["name"] == "Warfarin"


def test_lookup_pubchem_unexpected_payload():
    with patch("agents.common.pubchem.requests.get", return_value=_mock_response(200, {})):
        result = lookup_pubchem("Warfarin")

    assert result == {"status": "not_found", "name": "Warfarin"}
