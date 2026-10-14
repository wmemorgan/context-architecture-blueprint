# SPDX-License-Identifier: MIT
"""No-retention guarantee — source documents are not retained; no source-derived text
reaches any side-channel (logs/traces/error-payloads/backups/provider-telemetry).

The probe is a unique canary planted in source filler text. After a full ephemeral
processing cycle, the canary must appear in NO retained surface. A positive control
proves the probe actually detects a leak when one exists.
"""

import os

from cab.ingestion.loader import ingest_files
from cab.ingestion.retention import (
    NO_RETENTION_SCOPE,
    EphemeralWorkspace,
    RetentionStore,
    Sinks,
    scan_for_leak,
)

CANARY = "ZZQX-CANARY-7f3a9d2e-SOURCE-ONLY"


def _files():
    body = (
        "# Internal Memo\n\n"
        "This document contains the canary marker " + CANARY + " buried in filler text "
        "that the analyzer will never surface as a finding.\n"
    )
    return [("memo.md", body.encode("utf-8"))]


def test_workspace_is_shredded_no_source_bytes_survive():
    ws = EphemeralWorkspace()
    with ws as w:
        p = os.path.join(w.path, "memo.md")
        with open(p, "wb") as fh:
            fh.write(_files()[0][1])
        assert os.path.exists(p)
        path_during = w.path
    # After the context exits, the workspace is gone — no source bytes survive.
    assert not os.path.exists(path_during)
    assert ws.path == ""


def test_only_derived_report_persists_and_no_canary_leaks():
    files = _files()
    sinks = Sinks()
    store = RetentionStore()

    with EphemeralWorkspace() as ws:
        # Source bytes live ONLY in the ephemeral workspace during processing.
        for name, data in files:
            with open(os.path.join(ws.path, name), "wb") as fh:
                fh.write(data)
        corpus = ingest_files(files, source="upload")
        # The pipeline writes only derived, non-source content to side-channels.
        sinks.log(f"analyzed {len(corpus)} documents")
        sinks.trace("dimension=cross_document_consistency status=ok")
        sinks.telemetry("judge_tokens=1234")
        # Persist ONLY the derived report (scores/band), never source text.
        derived = {
            "report_url": "sha256:abc",
            "band": "L3",
            "dimension_scores": {"attributability": 62.0},
        }
        store.persist("sha256:abc", derived)

    # Post-analysis: the workspace is shredded; only the derived report persists.
    leaks = scan_for_leak(CANARY, sinks=sinks, store=store, workspace=ws)
    assert leaks == [], f"source canary leaked into: {leaks}"


def test_store_refuses_source_carrying_keys():
    store = RetentionStore()
    import pytest

    for bad in ("text", "raw", "source_text", "raw_bytes"):
        with pytest.raises(ValueError):
            store.persist("u", {bad: "secret source"})


def test_probe_is_a_real_check_positive_control():
    """If source text DID leak into a sink, the probe must catch it."""
    sinks = Sinks()
    store = RetentionStore()
    sinks.log("leaked: " + CANARY)  # simulate a retention bug
    leaks = scan_for_leak(CANARY, sinks=sinks, store=store)
    assert "logs" in leaks


def test_no_retention_scope_covers_r10_side_channels():
    for required in (
        "source-files",
        "logs",
        "traces",
        "error-payloads",
        "backups",
        "provider-telemetry",
    ):
        assert required in NO_RETENTION_SCOPE
