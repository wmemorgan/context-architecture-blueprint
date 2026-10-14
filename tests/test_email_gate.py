# SPDX-License-Identifier: MIT
"""Email gate — the report route requires an email before the full report/PDF."""

from datetime import date

from cab.pipeline import run_demo
from cab.report import email_gate
from cab.report.email_gate import fetch_gated, get_pdf, register_report


def _registered():
    email_gate._clear()
    report = run_demo(reference_date=date(2026, 6, 28))
    register_report(report["report_url"], report)
    return report


def test_report_is_gated_without_email():
    report = _registered()
    payload, status = fetch_gated(report["report_url"], email=None)
    assert status == 403
    assert payload["gated"] is True
    # The teaser exposes only the band, not the full findings.
    assert "dimensions" not in payload


def test_report_unlocks_with_valid_email_and_captures_lead():
    from cab.interfaces.email import LocalEmailSink

    report = _registered()
    sink = LocalEmailSink()
    payload, status = fetch_gated(report["report_url"], email="lead@example.com", sink=sink)
    assert status == 200
    assert payload["gated"] is False
    assert payload["band"] == report["band"]
    assert ("lead@example.com", report["report_url"]) in sink.leads


def test_invalid_email_stays_gated():
    report = _registered()
    _, status = fetch_gated(report["report_url"], email="not-an-email")
    assert status == 403


def test_pdf_download_is_gated():
    report = _registered()
    pdf_none, status = get_pdf(report["report_url"], email=None)
    assert status == 403 and pdf_none is None
    pdf, status = get_pdf(report["report_url"], email="lead@example.com")
    assert status == 200 and pdf.startswith(b"%PDF")


def test_missing_report_404():
    email_gate._clear()
    _, status = fetch_gated("sha256:nope", email="lead@example.com")
    assert status == 404
