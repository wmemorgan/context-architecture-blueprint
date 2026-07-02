# SPDX-License-Identifier: MIT
"""G — reproducibility & band stability (mock judge).

G1  10x identical-corpus replay → identical band + scores every time.
G2  Order / filename / whitespace invariance → same band.
"""

import os
from datetime import date

from cab.ingestion.demo import load_demo_corpus
from cab.ingestion.loader import ingest_directory
from cab.models import Corpus, Document
from cab.pipeline import run_on_corpus

REF = date(2026, 6, 28)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_g1_ten_replays_identical():
    corpus = load_demo_corpus()
    runs = [run_on_corpus(corpus, reference_date=REF) for _ in range(10)]
    bands = {r["band"] for r in runs}
    assert len(bands) == 1, f"band drifted across replays: {bands}"
    first = runs[0]["dimension_scores"]
    for r in runs[1:]:
        assert r["dimension_scores"] == first
        assert r["overall_score"] == runs[0]["overall_score"]


def test_g2_filename_and_order_invariance():
    base = ingest_directory(os.path.join(ROOT, "corpora", "calibration", "good_strong"))
    band0 = run_on_corpus(base, reference_date=REF)["band"]
    # Reverse order.
    rev = Corpus(documents=list(reversed(base.documents)), source=base.source)
    assert run_on_corpus(rev, reference_date=REF)["band"] == band0
    # Rename files (content identical) — band keys on content, not filename.
    renamed = Corpus(
        documents=[
            Document(
                name=f"renamed_{i}.md",
                ext=d.ext,
                text=d.text,
                raw_bytes_len=d.raw_bytes_len,
                metadata=dict(d.metadata),
                parsed_ok=d.parsed_ok,
            )
            for i, d in enumerate(base.documents)
        ],
        source=base.source,
    )
    assert run_on_corpus(renamed, reference_date=REF)["band"] == band0


def test_g2_trailing_whitespace_invariance():
    base = ingest_directory(os.path.join(ROOT, "corpora", "calibration", "good_modest"))
    band0 = run_on_corpus(base, reference_date=REF)["band"]
    ws = Corpus(
        documents=[
            Document(
                name=d.name,
                ext=d.ext,
                text=d.text + "   \n\n  \t",
                raw_bytes_len=d.raw_bytes_len,
                metadata=dict(d.metadata),
                parsed_ok=d.parsed_ok,
            )
            for d in base.documents
        ],
        source=base.source,
    )
    assert run_on_corpus(ws, reference_date=REF)["band"] == band0
