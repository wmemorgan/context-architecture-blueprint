# SPDX-License-Identifier: MIT
"""Persisted-report privacy constraint — span cap + retention/TTL, hermetic.

These run with NO key. They prove the engine-side guarantees the live-judge privacy
test exercises end-to-end: an over-quoting judge cannot leak a verbatim source
span past the cap into the persisted report, the report self-expires under a TTL,
the ephemeral mode persists nothing, and no hosted retention value is baked in.
"""

from __future__ import annotations

import json
from datetime import date

import yaml

from cab.analysis.judge import JudgePass
from cab.models import Corpus, Document, Finding
from cab.pipeline import run_on_corpus
from cab.privacy import (
    RetentionPolicy,
    SpanCap,
    build_source_index,
    load_privacy_config,
    longest_verbatim_run,
    scrub_text,
)
from cab.report import email_gate

REF = date(2026, 6, 28)

LONG_SPAN = (
    "our customer data retention policy mandates that all personal records are kept "
    "on encrypted storage for exactly three hundred and sixty five days before "
    "irreversible cryptographic deletion across every operating region worldwide"
)


class OverQuotingJudge:
    """Adversarial judge: floods findings + narrative with a long verbatim source span."""

    def run(self, corpus: Corpus) -> JudgePass:
        return JudgePass(
            scores={
                "cross_document_consistency": 0.05,
                "attributability": 0.5,
                "terminology_consistency": 0.8,
            },
            findings=[
                Finding(
                    "cross_document_consistency",
                    "high",
                    f'Doc a.md states verbatim: "{LONG_SPAN}" — which conflicts with b.md.',
                    documents=["a.md", "b.md"],
                    evidence=f'"{LONG_SPAN}"',
                )
            ],
            narrative=f'The corpus asserts "{LONG_SPAN}" while another document disagrees.',
        )


def _over_quoting_corpus():
    a = Document(
        "a.md", "md", LONG_SPAN + " and nothing else changes.", metadata={"source": "Legal"}
    )
    b = Document(
        "b.md",
        "md",
        "Records are deleted immediately on account closure.",
        metadata={"source": "Support"},
    )
    return Corpus(documents=[a, b], source="over-quote")


def _prose_strings(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _prose_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _prose_strings(v)
    elif isinstance(obj, str):
        yield obj


# ── Span cap ─────────────────────────────────────────────────────────────────
def test_scrub_caps_a_long_verbatim_span():
    cap = SpanCap(max_words=15, max_chars=120, elision_marker="[…]")
    src = build_source_index([LONG_SPAN])
    out = scrub_text(f'It says "{LONG_SPAN}" verbatim.', src, cap)
    assert LONG_SPAN not in out, "scrub left the full verbatim span"
    assert cap.elision_marker in out, "scrub did not mark the elision"
    assert longest_verbatim_run(out, src) <= cap.max_chars


def test_scrub_leaves_paraphrase_untouched():
    cap = load_privacy_config().span_cap
    src = build_source_index([LONG_SPAN])
    paraphrase = "Doc a.md keeps records about a year before deletion; b.md says immediately."
    assert scrub_text(paraphrase, src, cap) == paraphrase


def test_ac20_over_quoting_judge_cannot_leak_a_span_past_the_cap():
    cap = load_privacy_config().span_cap
    corpus = _over_quoting_corpus()
    email_gate._clear()
    rep = run_on_corpus(corpus, judge=OverQuotingJudge(), reference_date=REF)
    persisted = email_gate._REGISTRY[rep["report_url"]]
    blob = json.dumps(persisted, default=str)
    # The full planted span is gone from every persisted surface...
    assert LONG_SPAN not in blob, "over-quoted span persisted past the cap"
    # ...and no individual persisted prose string carries a verbatim run past the cap.
    src_idx = build_source_index([d.text for d in corpus.documents])
    worst = max((longest_verbatim_run(s, src_idx) for s in _prose_strings(persisted)), default=0)
    assert worst <= cap.max_chars, f"longest persisted verbatim run {worst} > cap {cap.max_chars}"
    # The finding is still legible — doc names survive (capped span, not erased).
    cdc = persisted["dimensions"]["cross_document_consistency"]["findings"]
    assert any(set(f["documents"]) == {"a.md", "b.md"} for f in cdc)


# ── Retention / TTL ──────────────────────────────────────────────────────────
def test_ac21_ttl_deletes_the_persisted_report():
    email_gate._clear()
    rep = run_on_corpus(
        _over_quoting_corpus(),
        judge=OverQuotingJudge(),
        reference_date=REF,
        retention=RetentionPolicy(mode="ttl", ttl_seconds=100),
    )
    url = rep["report_url"]
    assert email_gate._get(url) is not None
    # Before TTL: present. Past TTL: deleted.
    meta = email_gate._META[url]
    assert email_gate._get(url, now=meta["stored_at"] + 50) is not None
    purged = email_gate.purge_expired(now=meta["stored_at"] + 101)
    assert url in purged and email_gate._get(url) is None


def test_ac21_ephemeral_mode_persists_nothing():
    email_gate._clear()
    rep = run_on_corpus(
        _over_quoting_corpus(),
        judge=OverQuotingJudge(),
        reference_date=REF,
        retention=RetentionPolicy(mode="ephemeral", ttl_seconds=None),
    )
    assert rep["band"].startswith("L")  # full report still returned live
    assert email_gate._REGISTRY == {}  # but nothing persisted
    assert email_gate._get(rep["report_url"]) is None


def test_ac21_engine_default_is_conservative_and_not_a_hosted_value():
    cfg = load_privacy_config()
    assert cfg.retention.mode == "ttl"
    assert cfg.retention.ttl_seconds is not None
    # Conservative + NOT a hosted policy value (30/14 days) hardcoded in the engine.
    assert cfg.retention.ttl_seconds <= 14 * 86400 - 1
    raw = yaml.safe_load(open("config/privacy.yaml"))
    assert raw["retention"]["ttl_seconds"] not in (30 * 86400, 14 * 86400)
