"""PubChem PUG REST wrapper for resolving allopathic drug identifiers.

Used by @Intake's `lookup_pubchem` tool.
"""
from __future__ import annotations

from urllib.parse import quote

import requests

PUG_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPERTIES = "IUPACName,CanonicalSMILES,MolecularFormula"


def lookup_pubchem(name: str, timeout: float = 10.0) -> dict:
    """Resolve a drug name to PubChem identifiers.

    Returns a dict with "status" of "ok", "not_found", or "error". On "ok", also
    includes pubchem_cid, iupac_name, canonical_smiles, and molecular_formula.
    """
    url = f"{PUG_BASE}/compound/name/{quote(name)}/property/{PROPERTIES}/JSON"

    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        return {"status": "error", "name": name, "error": str(exc)}

    if response.status_code == 404:
        return {"status": "not_found", "name": name}
    if response.status_code != 200:
        return {"status": "error", "name": name, "error": f"HTTP {response.status_code}"}

    try:
        props = response.json()["PropertyTable"]["Properties"][0]
    except (KeyError, IndexError, ValueError):
        return {"status": "not_found", "name": name}

    return {
        "status": "ok",
        "name": name,
        "pubchem_cid": props.get("CID"),
        "iupac_name": props.get("IUPACName"),
        "canonical_smiles": props.get("CanonicalSMILES"),
        "molecular_formula": props.get("MolecularFormula"),
    }
