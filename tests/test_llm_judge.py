# SPDX-License-Identifier: MIT
"""Judge path — the dual-run judge flags a planted cross-document
contradiction with document references, and dual-run divergence is reported."""

from cab.analysis.engine import run_analysis
from cab.analysis.judge import MockJudge, dual_run
from cab.ingestion.demo import load_demo_corpus
from cab.models import Corpus, Document


def _doc(name, text):
    return Document(
        name=name,
        ext="md",
        text=text,
        raw_bytes_len=len(text),
        metadata={"title": name, "author": "a", "source": "s", "date": "2026-05-01"},
    )


def _contradictory_corpus():
    return Corpus(
        documents=[
            _doc(
                "security_a.md",
                "# Security\n\nAll customer data is encrypted at rest in every region.",
            ),
            _doc(
                "security_b.md",
                "# Security\n\nCustomer data is not encrypted at rest in any region.",
            ),
        ],
        source="test",
    )


def test_contradiction_flagged_with_document_references():
    result = dual_run(_contradictory_corpus(), judge=MockJudge())
    cdc = [s for s in result.signals if s.dimension == "cross_document_consistency"][0]
    assert cdc.score < 1.0
    contra = [f for f in cdc.findings if "contradiction" in f.message.lower()]
    assert contra, "no contradiction finding produced"
    # Both conflicting documents are named.
    assert set(contra[0].documents) == {"security_a.md", "security_b.md"}


def test_dual_run_reports_divergence_and_is_deterministic():
    result = dual_run(_contradictory_corpus(), judge=MockJudge())
    assert result.runs == 2
    assert set(result.divergence) >= {"cross_document_consistency", "attributability"}
    # The mock judge is deterministic at temp-0.0 ideal: zero divergence.
    assert all(v == 0.0 for v in result.divergence.values())


def test_clean_corpus_has_no_contradiction():
    result = dual_run(load_demo_corpus(), judge=MockJudge())
    cdc = [s for s in result.signals if s.dimension == "cross_document_consistency"][0]
    assert cdc.score == 1.0


def test_hybrid_run_exercises_both_paths():
    result = run_analysis(_contradictory_corpus(), judge=MockJudge())
    methods = {s.method for s in result.signals}
    assert "deterministic" in methods and "judge" in methods
    assert "narrative" in result.judge_divergence
