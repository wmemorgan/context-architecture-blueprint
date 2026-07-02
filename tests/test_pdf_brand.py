# SPDX-License-Identifier: MIT
"""Branded PDF — the server-side PDF is a valid PDF carrying WM.com branding."""

from datetime import date

from cab.interfaces.brand import DEFAULT_BRAND
from cab.pipeline import run_demo
from cab.report.pdf import render_pdf


def test_pdf_is_valid_and_branded():
    report = run_demo(reference_date=date(2026, 6, 28))
    pdf = render_pdf(report)
    assert pdf.startswith(b"%PDF-1.")
    assert pdf.rstrip().endswith(b"%%EOF")
    for marker in DEFAULT_BRAND.markers():
        assert marker.encode("latin-1") in pdf, f"brand marker missing: {marker}"


def test_pdf_includes_band_and_dimensions():
    report = run_demo(reference_date=date(2026, 6, 28))
    pdf = render_pdf(report)
    assert b"Context Readiness Band" in pdf
    assert b"Cross-Document Consistency" in pdf
