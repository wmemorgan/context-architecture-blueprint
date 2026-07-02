# SPDX-License-Identifier: MIT
"""H — boundary / degenerate inputs. Each must yield a sane band (L1..L5) or an
explicit 'cannot assess', and must NEVER crash or return a misleadingly-high band.
"""

from datetime import date

from cab.models import Corpus, Document
from cab.pipeline import run_on_corpus

REF = date(2026, 6, 28)
BANDS = ("L1", "L2", "L3", "L4", "L5")


def _doc(name, text, **meta):
    return Document(name=name, ext="md", text=text, metadata=meta)


def _band_ok(rep):
    return rep["band"] in BANDS and len(rep["dimension_scores"]) == 7


def test_h_empty_corpus_does_not_crash():
    rep = run_on_corpus(Corpus(documents=[], source="empty"), reference_date=REF)
    assert _band_ok(rep)
    # An empty corpus must not be called AI-ready.
    assert rep["band"] != "L5"


def test_h_single_document():
    rep = run_on_corpus(
        Corpus(
            documents=[
                _doc(
                    "only.md",
                    "# Only doc\n\nA single short document, per the team.",
                    source="t",
                    date="2026-06-01",
                )
            ],
            source="single",
        ),
        reference_date=REF,
    )
    assert _band_ok(rep)


def test_h_all_identical_documents_redundancy_low():
    body = "# Same\n\nIdentical content repeated across files, per the team."
    docs = [_doc(f"dup{i}.md", body, source="t", date="2026-06-01") for i in range(5)]
    rep = run_on_corpus(Corpus(documents=docs, source="identical"), reference_date=REF)
    assert _band_ok(rep)
    assert rep["dimensions"]["redundancy_uniqueness"]["score"] <= 50.0


def test_h_one_enormous_document():
    big = "# Big\n\n" + ("All systems nominal. " * 200000)  # ~4MB of text
    rep = run_on_corpus(
        Corpus(documents=[_doc("huge.md", big, source="t", date="2026-06-01")], source="huge"),
        reference_date=REF,
    )
    assert _band_ok(rep)


def test_h_all_images_no_extractable_text():
    docs = [
        Document(
            name=f"img{i}.pdf",
            ext="pdf",
            text="",
            raw_bytes_len=90000,
            parsed_ok=False,
            notes=["image-only"],
        )
        for i in range(3)
    ]
    rep = run_on_corpus(Corpus(documents=docs, source="images"), reference_date=REF)
    assert _band_ok(rep)
    assert rep["dimensions"]["extractability_structure"]["score"] <= 0.4 * 100
    assert rep["band"] != "L5"


def test_h_non_english_corpus():
    docs = [
        _doc(
            "de.md",
            "# Übersicht\n\nDies ist ein Dokument über Datenverarbeitung.",
            source="Team",
            date="2026-06-01",
        ),
        _doc(
            "fr.md",
            "# Aperçu\n\nCeci est un document sur le traitement des données.",
            source="Équipe",
            date="2026-06-02",
        ),
    ]
    rep = run_on_corpus(Corpus(documents=docs, source="non-en"), reference_date=REF)
    assert _band_ok(rep)


def test_h_out_of_domain_corpus():
    docs = [
        _doc(
            "recipe.md",
            "# Soup\n\nBoil water. Add vegetables. Simmer for an hour.",
            source="Cook",
            date="2026-06-01",
        ),
        _doc(
            "poem.md",
            "# Spring\n\nThe blossoms fall softly on the quiet pond.",
            source="Poet",
            date="2026-06-02",
        ),
    ]
    rep = run_on_corpus(Corpus(documents=docs, source="ood"), reference_date=REF)
    assert _band_ok(rep)
