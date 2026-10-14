# SPDX-License-Identifier: MIT
"""Deterministic dimension checks — the reliable, reproducible subset.

Each check traces to a public framework canon entry (DAMA-DMBOK data-quality
dimensions; Dublin Core / schema.org metadata; LangChain/LlamaIndex chunking),
never to a production implementation. Every check returns a Signal with a 0..1
score (1.0 = healthy) plus concrete, corpus-specific findings.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date

from cab.analysis.embeddings import Embedder, HashingEmbedder, cosine
from cab.models import Corpus, Finding, Signal

_HEADING_RE = re.compile(r"^#{1,6}\s+\S|^\S.{0,80}\n[=-]{3,}\s*$", re.MULTILINE)
_METADATA_FIELDS = ("title", "author", "date", "source")
_STALE_DAYS = 365
_NEAR_DUP_THRESHOLD = 0.85
# Common domain stopwords excluded from terminology-variant analysis.
_STOP = {
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
    "each",
    "your",
    "you",
    "we",
    "all",
    "one",
    "per",
    "into",
    "when",
    "so",
    "keep",
}


def run_deterministic(
    corpus: Corpus,
    embedder: Embedder | None = None,
    reference_date: date | None = None,
) -> list[Signal]:
    embedder = embedder or HashingEmbedder()
    ref = reference_date or date.today()
    return [
        _extractability_structure(corpus),
        _metadata_provenance(corpus),
        _freshness_versioning(corpus, ref),
        _cross_document_consistency_det(corpus),
        _attributability_det(corpus),
        _redundancy_uniqueness(corpus, embedder),
        _terminology_consistency(corpus),
    ]


def _extractability_structure(corpus: Corpus) -> Signal:
    findings: list[Finding] = []
    extract_scores, structure_scores = [], []
    for d in corpus.documents:
        ok = 1.0 if (d.parsed_ok and len(d.text.strip()) > 20) else 0.0
        extract_scores.append(ok)
        if not ok:
            findings.append(
                Finding(
                    "extractability_structure",
                    "high",
                    "Document did not yield extractable text.",
                    [d.name],
                )
            )
        has_structure = 1.0 if _HEADING_RE.search(d.text) else 0.0
        structure_scores.append(has_structure)
        if not has_structure and ok:
            findings.append(
                Finding(
                    "extractability_structure",
                    "medium",
                    "No headings/sections detected — flat, hard-to-chunk text.",
                    [d.name],
                )
            )
    score = _mean(extract_scores) * 0.6 + _mean(structure_scores) * 0.4
    return Signal(
        "extractability_structure", "format+structure", "deterministic", score, 1.0, findings
    )


def _metadata_provenance(corpus: Corpus) -> Signal:
    findings: list[Finding] = []
    per_doc = []
    for d in corpus.documents:
        present = [f for f in _METADATA_FIELDS if d.metadata.get(f)]
        per_doc.append(len(present) / len(_METADATA_FIELDS))
        missing = [f for f in _METADATA_FIELDS if not d.metadata.get(f)]
        if missing:
            findings.append(
                Finding(
                    "metadata_provenance",
                    "high" if len(missing) >= 3 else "medium",
                    f"Missing metadata: {', '.join(missing)}.",
                    [d.name],
                )
            )
    return Signal(
        "metadata_provenance",
        "dublin-core-presence",
        "deterministic",
        _mean(per_doc),
        1.0,
        findings,
    )


def _freshness_versioning(corpus: Corpus, ref: date) -> Signal:
    findings: list[Finding] = []
    dated, fresh, versioned = [], [], []
    for d in corpus.documents:
        ds = d.metadata.get("date")
        has_date = bool(ds)
        dated.append(1.0 if has_date else 0.0)
        if not has_date:
            findings.append(
                Finding(
                    "freshness_versioning",
                    "medium",
                    "No date — freshness cannot be assessed.",
                    [d.name],
                )
            )
            fresh.append(0.5)
        else:
            age = _age_days(str(ds), ref)
            if age is None:
                fresh.append(0.5)
            elif age > _STALE_DAYS:
                fresh.append(0.0)
                findings.append(
                    Finding(
                        "freshness_versioning",
                        "high",
                        f"Stale: last dated {ds} (~{age} days old).",
                        [d.name],
                    )
                )
            else:
                fresh.append(1.0)
        versioned.append(1.0 if d.metadata.get("version") else 0.0)
    score = _mean(dated) * 0.35 + _mean(fresh) * 0.4 + _mean(versioned) * 0.25
    return Signal(
        "freshness_versioning", "date+staleness+version", "deterministic", score, 1.0, findings
    )


def _cross_document_consistency_det(corpus: Corpus) -> Signal:
    """Deterministic proxy: conflicting numeric claims about the same labeled fact.

    The semantic contradiction detection is the LLM judge's job; this is a
    light deterministic floor that catches blatant numeric conflicts.
    """
    findings: list[Finding] = []
    # Extract "<label> ... <number> <unit>" claims (e.g., "retained for 30 days").
    claim_re = re.compile(
        r"(retained|retention|limit|limited to|expires?|kept)\D{0,30}?(\d+)\s*(days?|months?|years?|minutes?|requests?)",
        re.IGNORECASE,
    )
    facts: dict[str, set[tuple[str, str]]] = defaultdict(set)
    where: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for d in corpus.documents:
        for m in claim_re.finditer(d.text):
            label = m.group(1).lower().rstrip("s")
            value = (m.group(2), m.group(3).lower().rstrip("s"))
            facts[label].add(value)
            where[(label, value[0], value[1])].append(d.name)
    conflicts = 0
    for label, values in facts.items():
        # Same unit, different magnitude = a conflict.
        by_unit: dict[str, set[str]] = defaultdict(set)
        for num, unit in values:
            by_unit[unit].add(num)
        for unit, nums in by_unit.items():
            if len(nums) > 1:
                conflicts += 1
                docs = sorted({dn for n in nums for dn in where[(label, n, unit)]})
                findings.append(
                    Finding(
                        "cross_document_consistency",
                        "high",
                        f"Conflicting '{label}' values across documents: "
                        f"{sorted(nums)} {unit}.",
                        docs,
                    )
                )
    score = 1.0 if conflicts == 0 else max(0.0, 1.0 - 0.4 * conflicts)
    return Signal(
        "cross_document_consistency",
        "numeric-claim-conflict",
        "deterministic",
        score,
        0.6,
        findings,
    )


def _attributability_det(corpus: Corpus) -> Signal:
    """Deterministic proxy: fraction of documents that declare a source."""
    findings: list[Finding] = []
    sourced = []
    for d in corpus.documents:
        has_src = bool(d.metadata.get("source") or d.metadata.get("author"))
        sourced.append(1.0 if has_src else 0.0)
        if not has_src:
            findings.append(
                Finding(
                    "attributability",
                    "high",
                    "No source/author — claims cannot be traced.",
                    [d.name],
                )
            )
    return Signal(
        "attributability", "source-presence", "deterministic", _mean(sourced), 0.6, findings
    )


def _redundancy_uniqueness(corpus: Corpus, embedder: Embedder) -> Signal:
    findings: list[Finding] = []
    docs = corpus.documents
    vecs = [embedder.embed(d.text) for d in docs]
    dup_pairs = 0
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            sim = cosine(vecs[i], vecs[j])
            if sim >= _NEAR_DUP_THRESHOLD:
                dup_pairs += 1
                findings.append(
                    Finding(
                        "redundancy_uniqueness",
                        "medium",
                        f"Near-duplicate content (similarity {sim:.2f}).",
                        [docs[i].name, docs[j].name],
                    )
                )
    total_pairs = max(1, len(docs) * (len(docs) - 1) // 2)
    score = max(0.0, 1.0 - dup_pairs / total_pairs)
    return Signal(
        "redundancy_uniqueness", "near-duplicate-clustering", "deterministic", score, 1.0, findings
    )


def _terminology_consistency(corpus: Corpus) -> Signal:
    """Detect genuine surface variants of one concept (spacing/hyphen drift).

    NOT flagged: mere capitalization (sentence-start) or regular singular/plural.
    Flagged: "work space" vs "workspace", "e-mail" vs "email" — same concept,
    inconsistent surface form.
    """
    findings: list[Finding] = []
    cluster_surfaces: dict[str, set[str]] = defaultdict(set)
    for d in corpus.documents:
        for raw in re.findall(r"[A-Za-z][A-Za-z][A-Za-z]+(?:[ -][A-Za-z]+)?", d.text):
            tok = raw.strip()
            low = tok.lower()
            if low in _STOP or len(low.replace(" ", "")) < 4:
                continue
            norm = _normalize_term(low)  # spaces/hyphens removed + depluralized
            if len(norm) >= 4:
                cluster_surfaces[norm].add(tok)
    variant_terms = 0
    for _norm, surfaces in cluster_surfaces.items():
        # Depluralized lowforms that KEEP spacing/hyphens: drift iff >= 2 distinct.
        depluralized = {_depluralize(s.lower()) for s in surfaces}
        if len(depluralized) >= 2:
            variant_terms += 1
            findings.append(
                Finding(
                    "terminology_consistency",
                    "medium",
                    f"Terminology drift: {sorted(surfaces)} refer to one concept.",
                    [],
                )
            )
    score = 1.0 if variant_terms == 0 else max(0.3, 1.0 - 0.1 * variant_terms)
    return Signal(
        "terminology_consistency", "term-variant-clustering", "deterministic", score, 0.7, findings
    )


# ── helpers ──────────────────────────────────────────────────────────────────
def _normalize_term(low: str) -> str:
    t = low.replace("-", "").replace("_", "")
    t = re.sub(r"\s+", "", t)  # collapse spacing: "work space" == "workspace"
    return _depluralize(t)


def _depluralize(t: str) -> str:
    t = t.strip()
    if t.endswith("es") and len(t) > 4:
        return t[:-2]
    if t.endswith("s") and len(t) > 3:
        return t[:-1]
    return t


def _age_days(ds: str, ref: date) -> int | None:
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", ds)
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    return (ref - d).days


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0
