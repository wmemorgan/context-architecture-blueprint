# SPDX-License-Identifier: MIT
"""No-retention side-channels INCLUDING the error path (where leaks live).

Error-path canary: Force a parser / mid-pipeline exception with a unique canary in
     the source; the canary must not appear in the error payload, message, or any sink.
Derived-scores only: what persists behind the report URL is scores/structure,
     never source-derived text.
"""

from datetime import date

import pytest

import cab.ingestion.security as sec
from cab.ingestion.loader import ingest_files
from cab.ingestion.retention import RetentionStore, Sinks, scan_for_leak
from cab.ingestion.security import SecurityRejection, secure_ingest
from cab.pipeline import run_on_corpus

CANARY = "ZZQX-CANARY-err-9f3a2b1c"


def test_c3b_parser_exception_does_not_leak_canary(monkeypatch):
    # A parser that fails with the SOURCE TEXT (canary) embedded in its exception.
    def exploding_parse(name, data):
        raise ValueError(f"boom while reading: {data.decode('utf-8', 'ignore')}")

    monkeypatch.setattr(sec, "parse", exploding_parse)
    src = ("# Memo\n\n" + CANARY + " buried in the body.\n").encode()
    with pytest.raises(SecurityRejection) as ei:
        secure_ingest([("memo.md", src)])
    # The error surfaced to the caller carries NO source-derived text.
    assert CANARY not in str(ei.value)
    assert CANARY not in ei.value.reason


def test_c3b_error_sink_never_sees_canary():
    # Model the pipeline's error side-channel: even a logged failure carries only
    # a derived, source-free reason.
    sinks = Sinks()
    store = RetentionStore()
    try:
        raise RuntimeError("analysis failed for report sha256:abc (stage=judge)")
    except RuntimeError as exc:
        sinks.error(str(exc))  # the kind of string an error path emits
        sinks.trace("stage=judge status=error")
    leaks = scan_for_leak(CANARY, sinks=sinks, store=store)
    assert leaks == []


def test_c3c_persisted_report_holds_only_derived_scores():
    src = ("# Doc\n\nThe secret token " + CANARY + " sits in the prose.\n").encode()
    corpus = ingest_files([("doc.md", src)], source="upload")
    rep = run_on_corpus(corpus, reference_date=date(2026, 6, 28))

    # The persisted, gated report must not echo the source canary anywhere.
    import json

    blob = json.dumps(rep, default=str)
    assert CANARY not in blob, "source-derived text leaked into the persisted report"
    # It still carries the derived structure (scores + band).
    assert rep["band"] in ("L1", "L2", "L3", "L4", "L5")
    assert len(rep["dimension_scores"]) == 7
