# SPDX-License-Identifier: MIT
"""End-to-end pipeline: ingest → hybrid analysis → score/band → manifest → report.

This is the single orchestration seam the CLI and the reference service call. The
manifest generator (the hero deliverable) and the render contract / report renderer
are integrated here; the email gate and branded PDF are pluggable interfaces.

Privacy (the persisted-report privacy constraint): before the derived report is persisted, a post-process
**span scrub** caps any verbatim source span the judge over-quoted (the minimal-span rule), and
the report is persisted under the configured **retention policy** (the report self-expiry rule) — a
conservative TTL or an ephemeral/no-persist option. Both are policy-neutral config.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from cab.analysis.engine import run_analysis
from cab.analysis.judge import Judge, calibration_provenance, default_judge
from cab.ingestion.demo import load_demo_corpus
from cab.ingestion.loader import ingest_directory, ingest_files
from cab.ingestion.security import secure_ingest
from cab.models import Corpus
from cab.privacy import (
    PrivacyConfig,
    RetentionPolicy,
    build_source_index,
    load_privacy_config,
    scrub_report,
)
from cab.scoring.banding import score
from cab.scoring.contract import ScoringContract

SCOPE_DISCLAIMER = (
    "Structural readiness, advisory — this is not a guarantee that a retrieval or "
    "agent system built on this corpus will behave correctly. The L1–L5 band "
    "describes how comprehensible, attributable, and internally consistent the "
    "corpus is, not the behavior of any system downstream of it."
)


def run_on_corpus(
    corpus: Corpus,
    *,
    judge: Judge | None = None,
    contract: ScoringContract | None = None,
    reference_date: date | None = None,
    email: str | None = None,
    security_findings=None,
    privacy: PrivacyConfig | None = None,
    retention: RetentionPolicy | None = None,
) -> dict[str, Any]:
    privacy = privacy or load_privacy_config()
    retention = retention or privacy.retention

    # Resolve the judge once so the report can record which one produced it (the
    # calibration-provenance label rides on the output — non-reference judges are
    # explicitly marked "unverified calibration").
    judge = judge or default_judge()
    analysis = run_analysis(
        corpus, judge=judge, reference_date=reference_date, extra_findings=security_findings
    )
    result = score(analysis, contract)
    report = result.to_dict()
    report["narrative"] = (analysis.judge_divergence or {}).get("narrative", "")
    report["judge_divergence"] = (analysis.judge_divergence or {}).get("per_dimension", {})
    report["scope_disclaimer"] = SCOPE_DISCLAIMER
    report["calibration"] = calibration_provenance(judge)
    report["document_count"] = len(corpus)
    report["report_url"] = _report_url(corpus, report)

    # Hero deliverable — the corpus-specific blueprint manifest.
    try:
        from cab.manifest.generator import generate_manifest

        report["manifest"] = generate_manifest(corpus, result)
    except Exception:
        report["manifest"] = None

    # Render contract for the site — the engine emits a contract; the site consumes it.
    try:
        from cab.report.render import build_render_contract

        report["render_contract"] = build_render_contract(report)
    except Exception:
        report["render_contract"] = None

    # Minimal-span rule: cap any verbatim source span before anything is persisted.
    # Belt-and-suspenders behind the constrained judge prompt — guarantees the cap
    # even when the live judge over-quotes. Doc-name references are preserved.
    source_index = build_source_index(d.text for d in corpus.documents)
    scrub_report(report, source_index, privacy.span_cap)

    # Persist only the derived report behind the gated URL, under the retention
    # policy (self-expiry rule); register the email gate.
    try:
        from cab.report.email_gate import register_report

        register_report(
            report["report_url"],
            report,
            email=email,
            ttl_seconds=retention.ttl_seconds,
            mode=retention.mode,
        )
    except Exception:
        pass

    return report


def run_demo(**kwargs) -> dict[str, Any]:
    return run_on_corpus(load_demo_corpus(), **kwargs)


def run_on_files(files, *, email: str | None = None, secure: bool = True, **kwargs):
    if secure:
        corpus, sec_findings = secure_ingest(files)
        return run_on_corpus(corpus, email=email, security_findings=sec_findings, **kwargs)
    corpus = ingest_files(files, source="upload")
    return run_on_corpus(corpus, email=email, **kwargs)


def run_on_directory(path: str, **kwargs):
    return run_on_corpus(ingest_directory(path), **kwargs)


def _report_url(corpus: Corpus, report: dict) -> str:
    payload = {
        "band": report["band"],
        "dimension_scores": report["dimension_scores"],
        "documents": sorted(d.name for d in corpus.documents),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return f"sha256:{digest}"
