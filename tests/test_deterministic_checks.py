# SPDX-License-Identifier: MIT
"""Deterministic path — each deterministic check returns a per-doc
signal; a missing-metadata corpus drives Metadata & Provenance low."""

from datetime import date

from cab import DIMENSIONS
from cab.analysis.deterministic import run_deterministic
from cab.ingestion.demo import load_demo_corpus
from cab.models import Corpus, Document

REF = date(2026, 6, 28)


def _doc(name, text, **meta):
    return Document(name=name, ext="md", text=text, raw_bytes_len=len(text), metadata=meta)


def test_signals_cover_all_seven_dimensions():
    signals = run_deterministic(load_demo_corpus(), reference_date=REF)
    dims = {s.dimension for s in signals}
    assert dims == set(DIMENSIONS)
    for s in signals:
        assert s.method == "deterministic"
        assert 0.0 <= s.score <= 1.0


def test_metadata_low_when_stripped():
    corpus = Corpus(
        documents=[
            _doc("a.md", "# A\n\nSome text about workspaces and connectors."),
            _doc("b.md", "# B\n\nMore text with no metadata at all."),
        ],
        source="test",
    )
    signals = {s.dimension: s for s in run_deterministic(corpus, reference_date=REF)}
    meta = signals["metadata_provenance"]
    assert meta.score < 0.4, f"expected low metadata score, got {meta.score}"
    assert any(f.severity in ("high", "medium") for f in meta.findings)


def test_metadata_high_on_well_described_corpus():
    signals = {s.dimension: s for s in run_deterministic(load_demo_corpus(), reference_date=REF)}
    assert signals["metadata_provenance"].score >= 0.75


def test_numeric_claim_conflict_detected():
    corpus = Corpus(
        documents=[
            _doc(
                "p1.md",
                "# Policy\n\nData is retained for 30 days.",
                title="P1",
                author="x",
                date="2026-05-01",
                source="s",
            ),
            _doc(
                "p2.md",
                "# Policy\n\nData is retained for 90 days.",
                title="P2",
                author="y",
                date="2026-05-02",
                source="s",
            ),
        ],
        source="test",
    )
    cdc = {s.dimension: s for s in run_deterministic(corpus, reference_date=REF)}[
        "cross_document_consistency"
    ]
    assert cdc.score < 1.0
    assert any(
        "retention" in f.message.lower() or "retain" in f.message.lower() for f in cdc.findings
    )


def test_staleness_flagged():
    corpus = Corpus(
        documents=[
            _doc(
                "old.md",
                "# Old\n\ntext",
                title="Old",
                author="a",
                date="2019-01-01",
                source="s",
                version="1",
            )
        ],
        source="test",
    )
    fresh = {s.dimension: s for s in run_deterministic(corpus, reference_date=REF)}[
        "freshness_versioning"
    ]
    assert any("stale" in f.message.lower() for f in fresh.findings)
