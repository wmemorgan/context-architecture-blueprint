# SPDX-License-Identifier: MIT
"""LIVE-judge cluster. Runs ONLY when a real key is already in the
environment (ANTHROPIC_API_KEY). With no key the whole module is skipped and the
items are reported BLOCKED-pending-key — the executor never crawls a secret store.

Paraphrased/implied case: Real contradiction in messy prose — paraphrased (low
     lexical overlap) AND implied/cross-document (no shared antonym; requires
     inference). The mock cannot validate either.
Dual-run stability: same corpus repeated; the band reproduces across N>=5
     live runs at temp 0.0 (reproducibility on the live judge, not just the mock).
Live false positives: a clean, consistent corpus must NOT yield a fabricated
     cross-document CONTRADICTION (no high-severity CDC finding).
Live-judge reproducibility — same assertion path as the dual-run stability case (band stability).

Observed drift bound (claude-sonnet, temp 0.0) is recorded in internal/TEST_REPORT.md.
"""

import os
from datetime import date

import pytest

from cab.analysis.judge import ClaudeJudge
from cab.models import Corpus, Document
from cab.pipeline import run_on_corpus

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="BLOCKED-pending-key: set ANTHROPIC_API_KEY to run the live-judge cluster (C2/G3)",
)
REF = date(2026, 6, 28)


def _doc(name, text, **meta):
    return Document(name=name, ext="md", text=text, metadata=meta)


def _paraphrased_contradiction_corpus():
    a = _doc(
        "policy.md",
        "Our handling rules are firm. Once a customer closes their account, we keep "
        "their records on file for a year before secure deletion.",
        source="Legal",
    )
    b = _doc(
        "faq.md",
        "Customers often ask what happens to their information. The short answer: when "
        "you leave, nothing is deleted — we hold account history permanently.",
        source="Support",
    )
    return Corpus(documents=[a, b], source="live-test")


def _implied_contradiction_corpus():
    a = _doc(
        "vendor_policy.md",
        "Vendor onboarding standard: no third party may be granted production access "
        "until their SOC 2 Type II audit is complete and on file with Security.",
        source="Security",
    )
    b = _doc(
        "status_update.md",
        "Great news — Acme Logistics went live in production this week and is already "
        "processing orders. Their SOC 2 audit is booked for next quarter.",
        source="Ops",
    )
    return Corpus(documents=[a, b], source="live-onboarding")


def _cdc(rep):
    return rep["dimensions"]["cross_document_consistency"]


@pytest.mark.parametrize(
    "corpus_fn", [_paraphrased_contradiction_corpus, _implied_contradiction_corpus]
)
def test_c2a_live_judge_surfaces_messy_contradiction(corpus_fn):
    rep = run_on_corpus(corpus_fn(), reference_date=REF, judge=ClaudeJudge())
    assert rep["band"] not in ("L4", "L5"), rep["band"]
    cdc = _cdc(rep)
    assert cdc["findings"], "no cross-document-consistency finding surfaced"
    docs = {d for f in cdc["findings"] for d in f["documents"]}
    assert len(docs) >= 2, f"contradiction did not name both documents: {docs}"


def test_c2b_g3_dual_run_reproduces_band():
    corpus = _paraphrased_contradiction_corpus()
    bands = [
        run_on_corpus(corpus, reference_date=REF, judge=ClaudeJudge())["band"] for _ in range(5)
    ]
    assert len(set(bands)) == 1, f"temp-0.0 band drifted across {len(bands)} live runs: {bands}"
    assert bands[0] not in ("L4", "L5"), bands[0]


def test_c2c_live_judge_no_fabricated_contradiction_on_clean_corpus():
    clean = Corpus(
        documents=[
            _doc("a.md", "Accounts are encrypted at rest with AES-256.", source="Sec"),
            _doc("b.md", "All customer data at rest uses AES-256 encryption.", source="Sec"),
        ],
        source="live-clean",
    )
    rep = run_on_corpus(clean, reference_date=REF, judge=ClaudeJudge())
    cdc = _cdc(rep)
    # No FABRICATED contradiction: the live judge may note a hedged scope nuance, but it
    # must not raise a high-severity cross-document-consistency finding on a consistent
    # corpus, and the CDC score must stay high.
    high = [f for f in cdc["findings"] if f["severity"] == "high"]
    assert high == [], f"live judge fabricated a contradiction on a clean corpus: {high}"
    assert cdc["score"] >= 60.0, f"clean-corpus CDC score unexpectedly low: {cdc['score']}"


def test_c3c_live_persisted_report_is_capped_and_expirable():
    """Persisted-report privacy (redefined): no source FILES retained; no persisted span exceeds the
    cap even when the live judge over-quotes a long planted span; the report self-expires.

    The absolute "no source-derived text" claim was retired — the capped finding IS the
    public deliverable. What must hold on the live path: doc-name references + capped minimal
    spans only, never a reproduced paragraph, behind an enforced TTL.
    """
    import json as _json

    from cab.privacy import build_source_index, load_privacy_config, longest_verbatim_run
    from cab.report import email_gate

    # A long, distinctive verbatim span (> cap) planted in the source. If the live judge
    # quotes it, the scrub MUST cap it; if it paraphrases, nothing long persists.
    planted = (
        "our account closure policy retains every customer record on encrypted "
        "storage for a full calendar year before any irreversible secure deletion "
        "is performed across all regions"
    )
    corpus = Corpus(
        documents=[
            _doc("policy.md", planted + ".", source="Legal"),
            _doc(
                "faq.md",
                "When you leave, nothing is deleted — we hold account history permanently.",
                source="Support",
            ),
        ],
        source="canary",
    )
    email_gate._clear()
    rep = run_on_corpus(corpus, reference_date=REF, judge=ClaudeJudge())
    url = rep["report_url"]
    persisted = email_gate._REGISTRY[url]
    blob = _json.dumps(persisted, default=str)

    cap = load_privacy_config().span_cap
    src_idx = build_source_index([d.text for d in corpus.documents])

    # (1) No source FILE bytes persist (only the derived report behind the URL).
    assert all(k not in persisted for k in ("text", "raw", "raw_bytes", "source_text"))

    # (2) The full planted paragraph never survives, and no persisted prose string
    #     carries a verbatim source run past the cap — even if the judge over-quoted.
    assert planted not in blob, "the live judge's quote persisted past the cap"

    def _strings(o):
        if isinstance(o, dict):
            for v in o.values():
                yield from _strings(v)
        elif isinstance(o, list):
            for v in o:
                yield from _strings(v)
        elif isinstance(o, str):
            yield o

    worst = max((longest_verbatim_run(s, src_idx) for s in _strings(persisted)), default=0)
    assert worst <= cap.max_chars, f"persisted verbatim run {worst} > cap {cap.max_chars}"

    # (3) The persisted report self-expires (TTL deletes it).
    meta = email_gate._META[url]
    assert email_gate._get(url) is not None
    email_gate.purge_expired(now=(meta["stored_at"] or 0) + (meta["ttl_seconds"] or 0) + 1)
    assert email_gate._get(url) is None
