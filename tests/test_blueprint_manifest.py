# SPDX-License-Identifier: MIT
"""The Blueprint Manifest is corpus-specific (not a template):
it references terms/structure actually present in the input corpus, and differs
between different corpora."""

from datetime import date

from cab.analysis.engine import run_analysis
from cab.analysis.judge import MockJudge
from cab.ingestion.demo import load_demo_corpus
from cab.manifest.generator import generate_manifest
from cab.models import Corpus, Document
from cab.scoring.banding import score
from cab.scoring.contract import load_contract

REF = date(2026, 6, 28)


def _manifest(corpus):
    analysis = run_analysis(corpus, judge=MockJudge(), reference_date=REF)
    result = score(analysis, load_contract())
    return generate_manifest(corpus, result)


def _doc(name, text, **meta):
    return Document(name=name, ext="md", text=text, raw_bytes_len=len(text), metadata=meta)


def test_manifest_has_all_hero_sections():
    m = _manifest(load_demo_corpus())
    for key in (
        "summary",
        "metadata_schema",
        "chunking",
        "versioning",
        "glossary",
        "remediation_priorities",
        "derived_from",
    ):
        assert key in m


def test_glossary_references_actual_corpus_terms():
    m = _manifest(load_demo_corpus())
    terms = {e["term"] for e in m["glossary"]["entries"]}
    # The demo corpus is about workspaces / connectors / collections.
    assert {"workspace", "connector", "collection"} & terms


def test_metadata_schema_reflects_actual_presence():
    corpus = Corpus(documents=[_doc("a.md", "# A\n\nNo metadata here.")], source="t")
    m = _manifest(corpus)
    by_field = {f["field"]: f for f in m["metadata_schema"]["fields"]}
    assert by_field["author"]["presence_rate"] == 0.0
    assert "add to" in by_field["author"]["recommendation"]


def test_manifest_is_not_a_static_template():
    a = _manifest(
        Corpus(
            documents=[
                _doc(
                    "x.md",
                    "# Widgets\n\nThe widget pipeline assembles gizmos and sprockets.",
                    title="W",
                    author="a",
                    date="2026-05-01",
                    source="s",
                )
            ],
            source="t",
        )
    )
    b = _manifest(load_demo_corpus())
    a_terms = {e["term"] for e in a["glossary"]["entries"]}
    b_terms = {e["term"] for e in b["glossary"]["entries"]}
    assert a_terms != b_terms
    assert "widget" in a_terms or "gizmos" in a_terms or "sprockets" in a_terms


def test_chunking_recommendation_is_structure_aware():
    m = _manifest(load_demo_corpus())
    assert m["chunking"]["header_ratio"] >= 0.6
    assert "header-aware" in m["chunking"]["strategy"]
