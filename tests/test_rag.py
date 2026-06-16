from agents.common.rag import query_evidence
from rag.build_index import EVIDENCE_DIR, build_index


def test_build_index_counts_all_findings(tmp_path):
    n = build_index(evidence_dir=EVIDENCE_DIR, db_dir=tmp_path)
    assert n == 15  # 5 corpus files x 3 findings each


def test_query_evidence_returns_matching_pair(tmp_path):
    build_index(evidence_dir=EVIDENCE_DIR, db_dir=tmp_path)

    results = query_evidence("Tacrolimus", "St. John's Wort", n_results=3, db_dir=tmp_path)

    assert len(results) == 3
    assert all(r["drug"] == "Tacrolimus" for r in results)
    assert any(r["severity"] == "high" for r in results)
    assert any("PXR" in r["summary"] or "CYP3A4" in r["summary"] for r in results)


def test_query_evidence_metformin_karela(tmp_path):
    build_index(evidence_dir=EVIDENCE_DIR, db_dir=tmp_path)

    results = query_evidence("Metformin", "Karela", n_results=3, db_dir=tmp_path)

    assert len(results) == 3
    assert all(r["drug"] == "Metformin" for r in results)


def test_query_evidence_missing_index_returns_empty(tmp_path):
    results = query_evidence("Warfarin", "Guggulu", n_results=3, db_dir=tmp_path / "does_not_exist")
    assert results == []
