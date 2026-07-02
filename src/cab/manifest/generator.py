# SPDX-License-Identifier: MIT
"""Generate the corpus-specific Blueprint Manifest.

Everything here is DERIVED from the corpus actually supplied — the metadata schema
reflects the fields the documents do/don't carry, the chunking recommendation
reflects their real structure and length, the glossary is built from the terms
that actually appear, and remediation is ordered by the corpus's weakest
dimensions. Chunking/retrieval recommendations trace to LangChain / LlamaIndex /
GraphRAG public patterns (citations, not a template).
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from cab.analysis.embeddings import tokenize
from cab.models import Corpus
from cab.scoring.banding import ScoreResult

_DUBLIN_CORE = ("title", "author", "date", "source", "version")
# Stopword / noise filter (F3). Key terms must be domain-bearing vocabulary the
# prospect can act on — function words ("there", "which", "while"), generic
# document-process boilerplate ("document", "process", "step"), and bare verbs
# are NOT glossary-worthy and were surfacing as junk key terms (e.g. "there" in
# the messy_export corpus). Anything in this set is dropped before ranking.
_STOP = {
    # articles / conjunctions / prepositions / particles
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "for",
    "is",
    "are",
    "be",
    "this",
    "that",
    "with",
    "as",
    "by",
    "on",
    "at",
    "it",
    "its",
    "from",
    "all",
    "will",
    "may",
    "can",
    "must",
    "should",
    "your",
    "you",
    "we",
    "each",
    "per",
    "into",
    "when",
    "so",
    "keep",
    "one",
    "every",
    "their",
    "they",
    "them",
    "has",
    "have",
    "any",
    "use",
    "used",
    "uses",
    "data",
    "document",
    "documents",
    "team",
    "teams",
    "first",
    "more",
    "than",
    "out",
    "how",
    "long",
    "kept",
    # additional function words / discourse particles that are never domain terms
    "there",
    "here",
    "where",
    "which",
    "what",
    "who",
    "whom",
    "whose",
    "why",
    "then",
    "these",
    "those",
    "such",
    "also",
    "very",
    "much",
    "many",
    "most",
    "some",
    "other",
    "others",
    "another",
    "between",
    "among",
    "across",
    "within",
    "without",
    "about",
    "after",
    "before",
    "while",
    "during",
    "being",
    "been",
    "were",
    "was",
    "does",
    "did",
    "doing",
    "done",
    "only",
    "just",
    "over",
    "under",
    "both",
    "upon",
    "onto",
    "however",
    "therefore",
    "thus",
    "because",
    "though",
    "although",
    "until",
    "unless",
    "whether",
    "either",
    "neither",
    "but",
    "not",
    "no",
    "nor",
    "yet",
    "if",
    "else",
    "same",
    "own",
    "via",
    "make",
    "made",
    "makes",
    "give",
    "gives",
    "given",
    "get",
    "gets",
    "got",
    "writes",
    "write",
    "output",
    "step",
    "steps",
    "next",
    "produces",
    "produce",
    "according",
    "additional",
    "describe",
    "describes",
    "described",
    "detail",
    "details",
    "detailed",
    "front",
    "matter",
    "general",
    "various",
    "again",
    "once",
    "still",
    "always",
    "often",
    "usually",
    "etc",
}


def generate_manifest(corpus: Corpus, result: ScoreResult) -> dict[str, Any]:
    terms = _key_terms(corpus)
    return {
        "summary": _summary(corpus, result, terms),
        "metadata_schema": _metadata_schema(corpus),
        "chunking": _chunking(corpus),
        "versioning": _versioning(corpus),
        "glossary": _glossary(corpus, terms, result),
        "remediation_priorities": _remediation(result),
        "derived_from": {
            "document_count": len(corpus),
            "documents": [d.name for d in corpus.documents],
        },
        "cites": ["Dublin Core", "schema.org", "LangChain", "LlamaIndex", "GraphRAG", "W3C PROV"],
    }


def _summary(corpus: Corpus, result: ScoreResult, terms: list[tuple[str, int]]) -> str:
    top = ", ".join(t for t, _ in terms[:5]) or "your domain terms"
    return (
        f"A buildable blueprint for your {len(corpus)}-document corpus (band {result.band}). "
        f"It centers on your own vocabulary — {top} — and prescribes the metadata schema, "
        f"chunking, versioning, and glossary needed to make this corpus AI-ready."
    )


def _metadata_schema(corpus: Corpus) -> dict[str, Any]:
    n = max(1, len(corpus))
    fields = []
    for f in _DUBLIN_CORE:
        present = sum(1 for d in corpus.documents if d.metadata.get(f))
        rate = round(present / n, 2)
        fields.append(
            {
                "field": f,
                "vocabulary": "Dublin Core / schema.org",
                "presence_rate": rate,
                "required": f in ("title", "date", "source"),
                "recommendation": (
                    "present — keep it consistent"
                    if rate >= 0.9
                    else f"add to {n - present} document(s) missing it"
                ),
            }
        )
    return {
        "fields": fields,
        "note": "Schema reflects what your documents already carry; close the gaps above.",
    }


def _chunking(corpus: Corpus) -> dict[str, Any]:
    # Corpus-responsive chunking (F1). Chunk size is sized to THIS corpus's own
    # document-length distribution — never a fixed 800/120 default that splits a
    # ~180-char document into a window five times its length. We measure the mean
    # and the 75th-percentile document length and target a chunk that holds a
    # typical section, header-aware. `header_ratio` is MEASURED (fraction of
    # documents that are actually sectioned), not pinned.
    lengths = sorted(len(d.text) for d in corpus.documents)
    n = max(1, len(lengths))
    avg_len = sum(lengths) / n
    p75 = lengths[min(len(lengths) - 1, int(0.75 * (len(lengths) - 1)))] if lengths else 0
    headed = sum(1 for d in corpus.documents if re.search(r"^#{1,6}\s+\S", d.text, re.MULTILINE))
    header_ratio = headed / n
    if header_ratio >= 0.6:
        strategy = "header-aware recursive splitting"
        rationale = (
            "Most documents are sectioned with headings, so split on the heading "
            "hierarchy first (LangChain RecursiveCharacterTextSplitter / "
            "LlamaIndex MarkdownNodeParser), preserving section context per chunk."
        )
        size_factor, overlap_frac = 0.6, 0.10
    else:
        strategy = "fixed-size windows with overlap"
        rationale = (
            "Documents are largely flat, so use fixed-size windows with overlap "
            "until structure is added; revisit once headings exist."
        )
        size_factor, overlap_frac = 0.9, 0.15
    # Blend mean + p75 so a few long documents widen the window without a single
    # outlier dominating; clamp to a sane retrieval range and round for legibility.
    base = (avg_len + p75) / 2
    target = int(max(120, min(1500, round(base * size_factor / 10) * 10)))
    overlap = int(max(15, round(target * overlap_frac / 5) * 5))
    return {
        "strategy": strategy,
        "rationale": rationale,
        "target_chunk_chars": target,
        "overlap_chars": overlap,
        "header_ratio": round(header_ratio, 2),
        "avg_doc_chars": round(avg_len, 1),
        "cites": ["LangChain", "LlamaIndex", "GraphRAG"],
    }


def _versioning(corpus: Corpus) -> dict[str, Any]:
    n = max(1, len(corpus))
    versioned = sum(1 for d in corpus.documents if d.metadata.get("version"))
    dated = sum(1 for d in corpus.documents if d.metadata.get("date"))
    if versioned / n >= 0.6:
        policy = (
            "Documents already carry versions — formalize: increment on change, "
            "retain the prior version for audit, and stamp an updated date."
        )
    else:
        policy = (
            "Add an explicit version field and an updated date to every document; "
            "increment on change and retain prior versions for audit."
        )
    return {
        "policy": policy,
        "version_coverage": round(versioned / n, 2),
        "date_coverage": round(dated / n, 2),
        "cites": ["W3C PROV", "C2PA"],
    }


def _glossary(corpus: Corpus, terms: list[tuple[str, int]], result: ScoreResult) -> dict[str, Any]:
    # Pull terminology-drift findings so the glossary can prescribe a canonical form.
    drift = []
    term_dim = result.dimensions.get("terminology_consistency")
    if term_dim:
        for f in term_dim.findings:
            drift.append(f.message)
    entries = [
        {
            "term": t,
            "occurrences": c,
            "definition_stub": f"Define “{t}” — appears across {c} mention(s); give one canonical meaning.",
        }
        for t, c in terms[:12]
    ]
    return {
        "entries": entries,
        "drift_to_resolve": drift,
        "note": "Built from the terms that actually appear in your corpus.",
    }


def _short_claim(span: str, max_words: int = 12) -> str:
    """Trim a claim span to a legible, doc-grounded phrase (claim SHAPE, not a quote).

    The post-process span scrub (the minimal-span rule) is the hard guarantee; this keeps the
    pre-scrub text short so a contradiction reads as *which* claims conflict, not
    as a reproduced passage.
    """
    words = span.strip().strip("“”\"'").split()
    out = " ".join(words[:max_words])
    return out + ("…" if len(words) > max_words else "")


def _claim_pair(evidence: str | None) -> list[str]:
    """Split a mock-judge contradiction evidence string ('"A" vs "B"') into [A, B]."""
    if not evidence:
        return []
    parts = re.split(r'["“”]\s+vs\s+["“”]', evidence)
    claims = [_short_claim(p) for p in parts if p.strip().strip("“”\"' ")]
    return claims[:2]


def _contradiction_action(f) -> str:
    """Name BOTH documents + the contradicting claims for the flagship finding.

    The generic 'two documents make opposite claims about the same subject' is
    replaced with a specific, buildable remediation: which two documents, which
    claims, and what to do. Works for the mock judge (claims from `evidence`) and
    the live judge (claims paraphrased in `message`). Every quoted span stays a
    short claim shape; the deterministic scrub (the minimal-span rule) then guarantees the cap.
    """
    docs = [d for d in f.documents if d][:2]
    if len(docs) < 2:
        return f.message
    a, b = docs[0], docs[1]
    claims = _claim_pair(f.evidence)
    if len(claims) == 2:
        detail = f"“{claims[0]}” vs “{claims[1]}”"
    else:
        # Live judge: the message already paraphrases the conflicting claims.
        detail = _short_claim(f.message, max_words=24)
    return (
        f"Resolve the cross-document contradiction between {a} and {b}: {detail}. "
        f"Reconcile the conflicting claims (or scope each to its context) and "
        f"designate a single source of record."
    )


def _remediation_action(r) -> str:
    """The top action for a dimension — specific for a flagship contradiction."""
    if not r.findings:
        return "Strengthen this dimension."
    if r.dimension == "cross_document_consistency":
        contra = next(
            (
                f
                for f in r.findings
                if "contradiction" in f.message.lower() and len([d for d in f.documents if d]) >= 2
            ),
            None,
        )
        if contra is not None:
            return _contradiction_action(contra)
    return r.findings[0].message


def _remediation(result: ScoreResult) -> list[dict[str, Any]]:
    ranked = sorted(result.dimensions.values(), key=lambda r: r.score)
    out = []
    for r in ranked:
        if r.score >= 95.0:
            continue
        out.append(
            {
                "dimension": r.dimension,
                "score": r.score,
                "weight": r.weight,
                "priority": (
                    "high"
                    if r.dimension in ("cross_document_consistency", "attributability")
                    and r.score < 80
                    else "medium"
                ),
                "action": _remediation_action(r),
            }
        )
    return out[:6]


# A leading YAML front-matter block carries metadata field NAMES and values
# (author/date/source/version, an author's name) — provenance, not the corpus's
# domain vocabulary. Stripping it before ranking key terms keeps metadata noise
# (F3) out of the glossary while the parser still reads those fields for the
# metadata schema.
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def _body_text(text: str) -> str:
    return _FRONTMATTER_RE.sub("", text, count=1)


def _key_terms(corpus: Corpus) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for d in corpus.documents:
        for tok in tokenize(_body_text(d.text)):
            if tok in _STOP or len(tok) < 4 or tok.isdigit():
                continue
            counter[tok] += 1
    return counter.most_common(20)
