# SPDX-License-Identifier: MIT
"""Server-side branded PDF (dependency-free).

Emits a minimal but valid PDF carrying WM.com branding — no third-party
renderer required, so the build + tests are hermetic. A production deployment may
swap in a richer renderer through the same `render_pdf` signature. The brand is
applied via the pluggable BrandProfile; The Comprehension Standard is the
headline.
"""

from __future__ import annotations

from typing import Any

from cab.interfaces.brand import DEFAULT_BRAND, BrandProfile

_DIM_LABELS = {
    "extractability_structure": "Extractability & Structure",
    "metadata_provenance": "Metadata & Provenance",
    "freshness_versioning": "Freshness & Versioning",
    "cross_document_consistency": "Cross-Document Consistency",
    "attributability": "Attributability",
    "redundancy_uniqueness": "Redundancy & Uniqueness",
    "terminology_consistency": "Terminology Consistency",
}


def render_pdf(report: dict[str, Any], brand: BrandProfile = DEFAULT_BRAND) -> bytes:
    """Render the report to branded PDF bytes."""
    lines = _report_lines(report, brand)
    return _pdf_from_lines(lines)


def _report_lines(report: dict[str, Any], brand: BrandProfile) -> list[str]:
    manifest = report.get("manifest") or {}
    out = [
        brand.standard,  # headline (Standard foregrounded)
        brand.product,
        "",
        f"Context Readiness Band: {report.get('band')}   (overall {report.get('overall_score')})",
        f"Confidence: {report.get('confidence')}",
        "",
        "ADVISORY: " + (report.get("scope_disclaimer") or "")[:120],
        "",
        "BLUEPRINT MANIFEST (your buildable spec):",
        "  " + (manifest.get("summary") or "")[:160],
        "",
        "Dimensions:",
    ]
    for d, label in _DIM_LABELS.items():
        sc = report.get("dimension_scores", {}).get(d)
        heavy = " *" if d in ("cross_document_consistency", "attributability") else ""
        out.append(f"  - {label}{heavy}: {sc}")
    out += [
        "",
        "Built on / Cites: " + ", ".join(brand.cites[:6]) + ", ...",
        "",
        brand.footer,
        brand.owner + " - " + brand.domain,
    ]
    return out


# ── minimal PDF writer ───────────────────────────────────────────────────────
def _esc(s: str) -> str:
    out = []
    for ch in s:
        o = ord(ch)
        if ch in "()\\":
            out.append("\\" + ch)
        elif 32 <= o < 127:
            out.append(ch)
        else:
            out.append("-")  # downgrade non-ASCII to keep WinAnsi-safe
    return "".join(out)


def _pdf_from_lines(lines: list[str]) -> bytes:
    # Content stream: 12pt, 16pt leading, starting near the top of US-Letter.
    parts = ["BT", "/F1 12 Tf", "16 TL", "1 0 0 1 54 740 Tm"]
    for line in lines:
        parts.append(f"({_esc(line)}) Tj")
        parts.append("T*")
    parts.append("ET")
    content = "\n".join(parts).encode("latin-1", "replace")

    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
    )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"
    )

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objects) + 1
    out += f"xref\n0 {n}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(out)
