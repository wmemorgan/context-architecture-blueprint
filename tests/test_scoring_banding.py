# SPDX-License-Identifier: MIT
"""Locked, reproducible scoring contract: Cross-Doc Consistency +
Attributability are the heaviest; an identical corpus replays to an identical band;
a known-bad corpus bands below a known-good one."""

from datetime import date

from cab.analysis.engine import run_analysis
from cab.analysis.judge import MockJudge
from cab.ingestion.demo import load_demo_corpus
from cab.models import Corpus, Document
from cab.scoring.banding import score
from cab.scoring.contract import load_contract

REF = date(2026, 6, 28)


def _doc(name, text, **meta):
    return Document(name=name, ext="md", text=text, raw_bytes_len=len(text), metadata=meta)


def _score(corpus):
    analysis = run_analysis(corpus, judge=MockJudge(), reference_date=REF)
    return score(analysis, load_contract())


def test_contract_gives_top_weights_to_headline_dimensions():
    c = load_contract()
    others = [
        d
        for d, _ in c.weights.items()
        if d not in ("cross_document_consistency", "attributability")
    ]
    top = min(c.weights["cross_document_consistency"], c.weights["attributability"])
    assert all(top > c.weights[o] for o in others)


def test_contract_exposes_required_fields():
    c = load_contract()
    assert c.weights and c.cut_lines and c.method_weights
    assert isinstance(c.heaviest_min_delta, float)
    assert c.dual_run_arbitration in ("min", "mean", "max")
    assert isinstance(c.score_decimals, int)


def test_identical_corpus_replays_to_identical_band_and_scores():
    r1 = _score(load_demo_corpus())
    r2 = _score(load_demo_corpus())
    assert r1.band == r2.band
    assert r1.overall_score == r2.overall_score
    assert r1.to_dict()["dimension_scores"] == r2.to_dict()["dimension_scores"]


def test_known_bad_bands_below_known_good():
    good = load_demo_corpus()
    bad = Corpus(
        documents=[
            _doc("a.md", "All customer data is encrypted at rest."),  # no metadata
            _doc("b.md", "Customer data is not encrypted at rest."),  # contradiction
            _doc("c.md", "Stale notes.", date="2018-01-01"),  # stale
        ],
        source="test",
    )
    rg = _score(good)
    rb = _score(bad)
    assert rb.overall_score < rg.overall_score
    bands = ["L1", "L2", "L3", "L4", "L5"]
    assert bands.index(rb.band) <= bands.index(rg.band)


def test_band_is_valid_and_in_range():
    r = _score(load_demo_corpus())
    assert r.band in ("L1", "L2", "L3", "L4", "L5")
    assert 0.0 <= r.overall_score <= 100.0
