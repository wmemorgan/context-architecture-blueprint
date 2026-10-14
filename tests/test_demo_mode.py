# SPDX-License-Identifier: MIT
"""Demo mode loads and analyzes the bundled sample corpus with NO upload."""

from cab.ingestion.demo import load_demo_corpus


def test_demo_corpus_loads_without_upload():
    corpus = load_demo_corpus()
    assert corpus.source == "demo"
    assert len(corpus) >= 3
    # Every bundled document parses to non-empty normalized text.
    for doc in corpus.documents:
        assert doc.parsed_ok, f"{doc.name} failed to parse"
        assert doc.text.strip()


def test_demo_corpus_has_metadata_and_dates():
    corpus = load_demo_corpus()
    # The bundled corpus carries Dublin-Core-style metadata (title/author/date).
    assert all("title" in d.metadata for d in corpus.documents)
    assert any("date" in d.metadata for d in corpus.documents)
