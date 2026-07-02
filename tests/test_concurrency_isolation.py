# SPDX-License-Identifier: MIT
"""E3 — concurrency: simultaneous runs don't corrupt per-run isolation (run A's
data never appears in run B's report) and don't bypass the cost caps.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import date

from cab.cost.limits import CostGuard, Decision, RateLimiter, SpendLedger
from cab.models import Corpus, Document
from cab.pipeline import run_on_corpus

REF = date(2026, 6, 28)


def _corpus(tag):
    return Corpus(
        documents=[
            Document(
                name=f"{tag}_a.md",
                ext="md",
                text=f"# {tag} overview\n\nUnique marker {tag}-ALPHA in the body, per the {tag} team.",
                metadata={"source": f"{tag} team", "date": "2026-06-01"},
            ),
            Document(
                name=f"{tag}_b.md",
                ext="md",
                text=f"# {tag} detail\n\nUnique marker {tag}-BETA, according to {tag} records.",
                metadata={"source": f"{tag} team", "date": "2026-06-02"},
            ),
        ],
        source=tag,
    )


def test_e3_concurrent_runs_are_isolated():
    tags = [f"run{i}" for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        reports = dict(
            zip(
                tags,
                ex.map(lambda t: run_on_corpus(_corpus(t), reference_date=REF), tags),
                strict=False,
            )
        )
    import json

    for tag, rep in reports.items():
        blob = json.dumps(rep, default=str)
        # No OTHER run's unique marker appears in this run's report.
        for other in tags:
            if other != tag:
                assert (
                    f"{other}-ALPHA" not in blob and f"{other}-BETA" not in blob
                ), f"cross-run leakage: {other} data found in {tag}'s report"
    # All report URLs are distinct (no collision / overwrite).
    assert len({r["report_url"] for r in reports.values()}) == len(tags)


def test_e3_concurrent_load_does_not_bypass_rate_cap():
    guard = CostGuard(
        rate=RateLimiter(per_ip_per_day=10, day_key=lambda: "2026-06-28"),
        ledger=SpendLedger(monthly_ceiling=1e9, month_key=lambda: "2026-06"),
    )
    with ThreadPoolExecutor(max_workers=16) as ex:
        decisions = list(ex.map(lambda _i: guard.admit("203.0.113.7"), range(50)))
    ok = sum(d == Decision.OK for d in decisions)
    # Never admit more paid runs than the cap, no matter the concurrency.
    assert ok <= 10, f"rate cap bypassed under concurrency: {ok} admitted"
    assert any(d == Decision.DEGRADE_TO_DEMO for d in decisions)
