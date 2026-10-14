# SPDX-License-Identifier: MIT
"""Build the report render contract.

The corpus-specific manifest is the HERO — it precedes and outweighs the score
block. The Comprehension Standard is the headline; public framework canon appears
only under `cites`. The advisory scope + confidence render above the fold. The
radar covers all seven dimensions and the L1–L5 band.

The engine emits this contract; the site renders it. Live site state is
authoritative on any conflict.
"""

from __future__ import annotations

from typing import Any

from cab import DIMENSIONS
from cab.interfaces.brand import DEFAULT_BRAND, BrandProfile
from cab.interfaces.pipeline import route_for_band

# Manifest outweighs the score block.
SECTION_WEIGHTS = {
    "above_the_fold": 0.10,
    "manifest": 0.40,
    "radar": 0.18,
    "findings": 0.12,
    "remediation": 0.12,
    "whats_next": 0.05,
    "cites": 0.03,
}
SECTION_ORDER = [
    "above_the_fold",
    "manifest",
    "radar",
    "findings",
    "remediation",
    "whats_next",
    "cites",
]

_DIM_LABELS = {
    "extractability_structure": "Extractability & Structure",
    "metadata_provenance": "Metadata & Provenance",
    "freshness_versioning": "Freshness & Versioning",
    "cross_document_consistency": "Cross-Document Consistency",
    "attributability": "Attributability",
    "redundancy_uniqueness": "Redundancy & Uniqueness",
    "terminology_consistency": "Terminology Consistency",
}


def build_render_contract(
    report: dict[str, Any], brand: BrandProfile = DEFAULT_BRAND
) -> dict[str, Any]:
    dims = report.get("dimensions", {})
    radar = [
        {
            "dimension": d,
            "label": _DIM_LABELS[d],
            "score": dims.get(d, {}).get("score", report["dimension_scores"].get(d)),
            "weight": dims.get(d, {}).get("weight"),
            "heaviest": d in ("cross_document_consistency", "attributability"),
        }
        for d in DIMENSIONS
    ]
    all_findings = []
    for d, info in dims.items():
        for f in info.get("findings", []):
            all_findings.append({**f, "dimension": d})

    return {
        # The authored Standard is the headline; canon is NOT here.
        "headline": {
            "standard": brand.standard,
            "product": brand.product,
            "tagline": f"Measured against {brand.standard}.",
        },
        "standard_is_headline": True,
        # Advisory scope + confidence above the fold.
        "above_the_fold": {
            "scope_disclaimer": report.get("scope_disclaimer"),
            "confidence": report.get("confidence"),
            "band": report.get("band"),
            "calibration": report.get("calibration"),
            "uncertainty_note": "Visual weight matches epistemic weight: this is advisory.",
        },
        "section_order": SECTION_ORDER,
        "section_weights": SECTION_WEIGHTS,
        # The manifest is the hero, placed before the score block.
        "manifest": report.get("manifest"),
        # Radar across all 7 dimensions + the band.
        "radar": {
            "dimensions": radar,
            "band": report.get("band"),
            "overall_score": report.get("overall_score"),
            "narrative": report.get("narrative"),
        },
        "findings": all_findings,
        "remediation": (report.get("manifest") or {}).get("remediation_priorities", []),
        "whats_next": {
            "band": report.get("band"),
            "route": route_for_band(report.get("band", "L1")),
        },
        # Public framework canon appears ONLY here, as cited foundations.
        "cites": list(brand.cites),
        "brand": {"owner": brand.owner, "domain": brand.domain, "footer": brand.footer},
        "report_url": report.get("report_url"),
    }
