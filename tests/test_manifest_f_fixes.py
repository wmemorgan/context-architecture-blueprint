# SPDX-License-Identifier: MIT
"""Manifest-credibility fixes — corpus-responsive chunking, flagship contradiction
specificity, and the vocabulary stopword/noise filter. These lock the manifest
credibility fixes deterministically (MockJudge) so CI gates them.
"""

from datetime import date

from cab.analysis.engine import run_analysis
from cab.analysis.judge import MockJudge
from cab.manifest.generator import generate_manifest
from cab.models import Corpus, Document
from cab.privacy import build_source_index, load_privacy_config, longest_verbatim_run
from cab.scoring.banding import score
from cab.scoring.contract import load_contract

REF = date(2026, 6, 28)


def _doc(name, text, **meta):
    return Document(name=name, ext="md", text=text, raw_bytes_len=len(text), metadata=meta)


def _manifest(corpus):
    analysis = run_analysis(corpus, judge=MockJudge(), reference_date=REF)
    return generate_manifest(corpus, score(analysis, load_contract()))


def _small_corpus():
    # ~180-char documents — must NOT inherit the old 800/120 default.
    return Corpus(
        documents=[
            _doc(
                "doc1.md",
                "# Process Notes\n\nThe pipeline ingests files and produces summaries. "
                "Each step writes output to the next. No author, date, or source here.",
            ),
            _doc(
                "doc2.md",
                "# More Notes\n\nThe workflow runs again on a schedule and emits a report. "
                "Records are kept briefly then dropped from the working set.",
            ),
        ],
        source="small",
    )


def _large_corpus():
    body = (
        "# Platform Overview\n\n"
        + (
            "The workspace connector syncs each collection into the "
            "knowledge platform across every tenant region. "
        )
        * 12
    )
    return Corpus(
        documents=[
            _doc(
                f"d{i}.md", body, title="T", author="a", date="2026-05-01", source="s", version="1"
            )
            for i in range(3)
        ],
        source="large",
    )


# ── Corpus-responsive chunking ───────────────────────────────────────────────
def test_f1_chunk_size_tracks_document_length():
    small = _manifest(_small_corpus())["chunking"]
    large = _manifest(_large_corpus())["chunking"]
    # Small-doc corpus must not get the old fixed 800-char / 120-overlap default.
    assert small["target_chunk_chars"] < 800
    assert small["overlap_chars"] != 120
    # Chunk size is responsive: a longer-document corpus gets a larger window.
    assert large["target_chunk_chars"] > small["target_chunk_chars"]


def test_f1_header_ratio_is_measured():
    m = _manifest(_small_corpus())["chunking"]
    # header_ratio is a measured fraction in [0, 1], not a pinned constant, and the
    # corpus-average document length is surfaced as the sizing basis.
    assert 0.0 <= m["header_ratio"] <= 1.0
    assert "avg_doc_chars" in m


def test_f1_params_differ_across_corpora():
    a = _manifest(_small_corpus())["chunking"]
    b = _manifest(_large_corpus())["chunking"]
    assert (a["target_chunk_chars"], a["overlap_chars"]) != (
        b["target_chunk_chars"],
        b["overlap_chars"],
    )


# ── Flagship contradiction specificity (with the minimal-span cap intact) ────
def _contradiction_corpus():
    return Corpus(
        documents=[
            _doc(
                "data_handling.md",
                "# Data Handling\n\nCustomer records are never purged; they are "
                "retained indefinitely for audit.",
                source="Gov",
            ),
            _doc(
                "security_policy.md",
                "# Security Policy\n\nCustomer records are retained for exactly "
                "30 days, then purged.",
                source="Gov",
            ),
        ],
        source="contra",
    )


def test_f2_flagship_remediation_names_both_docs_and_claims():
    corpus = _contradiction_corpus()
    m = _manifest(corpus)
    cdc = [r for r in m["remediation_priorities"] if r["dimension"] == "cross_document_consistency"]
    assert cdc, "expected a cross-document remediation entry"
    action = cdc[0]["action"]
    # Names BOTH documents and reads as a contradiction (not the generic template).
    assert "data_handling.md" in action and "security_policy.md" in action
    assert "contradiction" in action.lower()
    assert "opposite claims about the same subject" not in action
    # Names the contradicting claim shape (retain vs purge).
    assert "purged" in action.lower() and "retained" in action.lower()


def test_f2_span_cap_holds_on_manifest():
    corpus = _contradiction_corpus()
    m = _manifest(corpus)
    cap = load_privacy_config().span_cap
    src = build_source_index([d.text for d in corpus.documents])

    def strings(o):
        if isinstance(o, dict):
            for v in o.values():
                yield from strings(v)
        elif isinstance(o, list):
            for v in o:
                yield from strings(v)
        elif isinstance(o, str):
            yield o

    # The generator does not over-quote: every verbatim source run in the manifest
    # is already within the cap (the pipeline scrub is the belt-and-suspenders).
    worst = max((longest_verbatim_run(s, src) for s in strings(m)), default=0)
    assert worst <= cap.max_chars


# ── Vocabulary stopword / noise filter ───────────────────────────────────────
def test_f3_no_stopword_or_junk_key_terms():
    corpus = Corpus(
        documents=[
            _doc(
                "a.md",
                "# Notes\n\nThere is no front matter here. According to the team, the workflow "
                "runs again. The connector syncs the collection into the workspace.",
            ),
        ],
        source="junk",
    )
    terms = {e["term"] for e in _manifest(corpus)["glossary"]["entries"]}
    junk = {"there", "according", "again", "front", "matter"}
    assert not (terms & junk), f"junk key terms leaked: {terms & junk}"
    # The real domain vocabulary still surfaces.
    assert {"connector", "collection", "workspace"} & terms


def test_f3_frontmatter_metadata_not_in_glossary():
    corpus = Corpus(
        documents=[
            Document(
                "d.md",
                "md",
                "---\nauthor: A. Lead\nsource: Governance Office\nversion: '3.2'\n---\n"
                "# Policy\n\nCustomer records are encrypted at rest and access is logged.",
                metadata={"author": "A. Lead", "source": "Governance Office", "version": "3.2"},
            ),
        ],
        source="fm",
    )
    terms = {e["term"] for e in _manifest(corpus)["glossary"]["entries"]}
    # The author-name fragment from front matter must not be a glossary key term.
    assert "lead" not in terms
    assert {"customer", "encrypted", "access", "logged"} & terms
