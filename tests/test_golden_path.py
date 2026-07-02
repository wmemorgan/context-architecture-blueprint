# SPDX-License-Identifier: MIT
"""B (golden path) — fixture corpus library with known properties, each asserting
an acceptance criterion from evidence (not from BUILD_STATUS).

B1 planted-contradiction · B2 missing-metadata · B3 clean-L5 false-positive guard
B4 report render · B5 manifest · B6 PDF + email gate · B7 demo no-secrets
B8 hybrid both paths fire.
"""

import os
from datetime import date

from cab.ingestion.demo import load_demo_corpus
from cab.ingestion.loader import ingest_directory
from cab.pipeline import run_on_corpus

REF = date(2026, 6, 28)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _cal(name):
    return ingest_directory(os.path.join(ROOT, "corpora", "calibration", name))


def test_b1_planted_contradiction_flagged_with_both_doc_refs():
    rep = run_on_corpus(_cal("bad_contradiction"), reference_date=REF)
    cdc = rep["dimensions"]["cross_document_consistency"]
    assert cdc["score"] <= 40.0, "contradiction did not drive CDC low"
    docs = {d for f in cdc["findings"] for d in f["documents"]}
    assert len(docs) >= 2, f"contradiction must name >=2 conflicting docs, got {docs}"


def test_b2_missing_metadata_scores_low():
    rep = run_on_corpus(_cal("bad_missing_metadata"), reference_date=REF)
    assert rep["dimensions"]["metadata_provenance"]["score"] <= 40.0


def test_b3_clean_corpus_high_band_no_hallucinated_contradictions():
    rep = run_on_corpus(_cal("good_strong"), reference_date=REF)
    assert rep["band"] in ("L4", "L5")
    # False-positive guard: a clean corpus must not invent contradictions.
    assert rep["dimensions"]["cross_document_consistency"]["findings"] == []


def test_b4_report_renders_7_dims_and_band():
    rep = run_on_corpus(_cal("good_strong"), reference_date=REF)
    assert len(rep["dimension_scores"]) == 7
    assert rep["band"] in ("L1", "L2", "L3", "L4", "L5")
    rc = rep["render_contract"]
    assert rc is not None


def test_b5_manifest_emitted_and_corpus_specific():
    corpus = _cal("good_strong")
    rep = run_on_corpus(corpus, reference_date=REF)
    manifest = rep["manifest"]
    assert manifest is not None
    blob = str(manifest).lower()
    # Corpus-specific: references a term actually present in the corpus.
    corpus_text = " ".join(d.text.lower() for d in corpus.documents)
    assert any(term in blob for term in ("glossary", "lifecycle", "governance", "metadata"))
    assert any(w in corpus_text for w in ("glossary", "lifecycle", "governance"))


def test_b6_pdf_and_email_gate():
    from cab.report.email_gate import fetch_gated, get_pdf, register_report

    rep = run_on_corpus(_cal("good_strong"), reference_date=REF)
    url = rep["report_url"]
    register_report(url, rep, email=None)
    # No email -> 403 teaser, PDF blocked.
    payload, status = fetch_gated(url, email=None)
    assert status == 403 and payload.get("gated") is True
    assert get_pdf(url, email=None) == (None, 403)
    # Valid email -> 200 full report + branded PDF.
    full, status = fetch_gated(url, email="a@b.com")
    assert status == 200 and full.get("gated") is False
    pdf, pstatus = get_pdf(url, email="a@b.com")
    assert pstatus == 200 and pdf[:4] == b"%PDF"


def test_b7_demo_mode_no_upload_no_secrets():
    assert not os.environ.get("ANTHROPIC_API_KEY"), "B7 asserts the no-secret path"
    rep = run_on_corpus(load_demo_corpus(), reference_date=REF)
    assert rep["band"] in ("L1", "L2", "L3", "L4", "L5")
    assert len(rep["dimension_scores"]) == 7


def test_b8_hybrid_both_paths_fire():
    from cab.analysis.engine import run_analysis

    analysis = run_analysis(_cal("good_strong"), reference_date=REF)
    methods = {s.method for s in analysis.signals}
    assert "deterministic" in methods and "judge" in methods
