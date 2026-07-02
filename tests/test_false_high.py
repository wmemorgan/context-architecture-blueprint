# SPDX-License-Identifier: MIT
"""False-high prevention (the reason the product exists).

Polished-corpus case: A POLISHED corpus (rich metadata, citations, consistent
     terminology, fresh, well-structured) with ONE buried material contradiction
     must NOT reach L4/L5, and the contradiction must surface naming both documents.
     The single most important test — it bounds the worst output (confident-wrong
     high band).
Boundary-stability case: A corpus sitting at the L3/L4 boundary must not flip its
     band under trivial, semantics-preserving perturbations (whitespace, document order).
"""

import os
from datetime import date

from cab.ingestion.loader import ingest_directory
from cab.models import Corpus
from cab.pipeline import run_on_corpus
from cab.scoring.contract import load_contract

REF = date(2026, 6, 28)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _fixture(name):
    return ingest_directory(os.path.join(ROOT, "corpora", "fixtures", name))


def _cal(name):
    return ingest_directory(os.path.join(ROOT, "corpora", "calibration", name))


def test_c1a_polished_but_contradictory_not_ai_ready():
    corpus = _fixture("polished_contradiction")
    rep = run_on_corpus(corpus, reference_date=REF)

    # Despite a high weighted average, a buried contradiction caps the band.
    assert rep["band"] not in ("L4", "L5"), (
        f"FALSE-HIGH: polished-but-contradictory corpus banded {rep['band']} "
        f"(overall {rep['overall_score']}) — a buried contradiction rode the average up."
    )
    # The contradiction surfaced and names BOTH conflicting documents.
    cdc = rep["dimensions"]["cross_document_consistency"]
    assert cdc["findings"], "contradiction was not surfaced at all"
    named = {d for f in cdc["findings"] for d in f["documents"]}
    assert {
        "security_policy.md",
        "data_handling.md",
    } <= named, f"contradiction must name both conflicting docs; named {named}"


def test_c1a_high_average_alone_would_have_been_l5():
    # Prove the guard is doing the work: the weighted average is L5-class, yet the
    # band is held down by the dimension cap + band ceiling (not by a low average).
    rep = run_on_corpus(_fixture("polished_contradiction"), reference_date=REF)
    c = load_contract()
    assert rep["overall_score"] >= c.cut_lines["L4"], "fixture isn't actually high-average"
    assert rep["dimensions"]["cross_document_consistency"]["score"] <= 40.0


def test_c1c_near_cut_line_band_is_stable_under_trivial_change():
    base = _cal("bad_missing_metadata")  # overall ~69.0 — just under the L4 cut-line
    rep = run_on_corpus(base, reference_date=REF)
    band0, overall = rep["band"], rep["overall_score"]

    c = load_contract()
    nearest = min(abs(overall - v) for v in c.cut_lines.values())
    # Documented sensitivity: the corpus is genuinely near a cut-line.
    assert nearest <= 5.0, f"fixture not near a cut-line (margin {nearest})"

    # Perturbation 1 — append whitespace to every document (semantics preserved).
    ws = Corpus(
        documents=[
            type(d)(
                name=d.name,
                ext=d.ext,
                text=d.text + "\n\n   \n",
                raw_bytes_len=d.raw_bytes_len,
                metadata=dict(d.metadata),
                parsed_ok=d.parsed_ok,
                notes=list(d.notes),
            )
            for d in base.documents
        ],
        source=base.source,
    )
    assert run_on_corpus(ws, reference_date=REF)["band"] == band0

    # Perturbation 2 — reverse document order.
    rev = Corpus(documents=list(reversed(base.documents)), source=base.source)
    assert run_on_corpus(rev, reference_date=REF)["band"] == band0
