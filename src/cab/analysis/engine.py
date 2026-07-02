# SPDX-License-Identifier: MIT
"""Hybrid analysis orchestrator — runs BOTH the deterministic checks and the
dual-run LLM judge in a single pass and merges them into one AnalysisResult.

This is the hybrid surface: every run exercises ≥1 deterministic check and
≥1 dual-run judge check, and both contribute to the score (cab.scoring).
"""

from __future__ import annotations

from datetime import date

from cab.analysis.deterministic import run_deterministic
from cab.analysis.embeddings import Embedder
from cab.analysis.judge import Judge, dual_run
from cab.models import AnalysisResult, Corpus


def run_analysis(
    corpus: Corpus,
    judge: Judge | None = None,
    embedder: Embedder | None = None,
    reference_date: date | None = None,
    extra_findings=None,
) -> AnalysisResult:
    det_signals = run_deterministic(corpus, embedder=embedder, reference_date=reference_date)
    dr = dual_run(corpus, judge)
    signals = det_signals + dr.signals
    # Security findings (e.g., surfaced prompt-injection) flow through untouched.
    if extra_findings:
        for s in signals:
            if s.dimension == "attributability":
                s.findings = list(s.findings) + list(extra_findings)
                break
    return AnalysisResult(
        signals=signals,
        judge_divergence={
            "per_dimension": dr.divergence,
            "narrative": dr.narrative,
            "runs": dr.runs,
        },
    )
