# SPDX-License-Identifier: MIT
"""The render contract: radar across all 7
dimensions + an L1–L5 band; manifest is the hero (precedes/outweighs the score);
The Comprehension Standard is the headline (canon as citations only); the
advisory scope + confidence render above the fold."""

from datetime import date

from cab.pipeline import run_demo
from cab.report.render import build_render_contract

REF = date(2026, 6, 28)


def _contract():
    report = run_demo(reference_date=REF)
    return build_render_contract(report), report


def test_radar_covers_seven_dimensions_and_a_band():
    rc, _ = _contract()
    assert len(rc["radar"]["dimensions"]) == 7
    assert rc["radar"]["band"] in ("L1", "L2", "L3", "L4", "L5")


def test_manifest_is_hero_precedes_and_outweighs_score():
    rc, _ = _contract()
    order = rc["section_order"]
    assert order.index("manifest") < order.index("radar")
    assert rc["section_weights"]["manifest"] > rc["section_weights"]["radar"]
    assert rc["manifest"] is not None


def test_standard_is_headline_canon_only_in_cites():
    rc, _ = _contract()
    assert rc["standard_is_headline"] is True
    assert rc["headline"]["standard"] == "The Comprehension Standard"
    # Canon strings must not appear in the headline; only under cites.
    headline_blob = str(rc["headline"]).lower()
    for canon in ("ragas", "dama-dmbok", "dublin core", "w3c prov"):
        assert canon not in headline_blob
    assert any("RAGAS" == c or "DAMA-DMBOK" == c for c in rc["cites"])


def test_uncertainty_forward_above_the_fold():
    rc, _ = _contract()
    atf = rc["above_the_fold"]
    assert atf["scope_disclaimer"] and "advisory" in atf["scope_disclaimer"].lower()
    assert atf["confidence"] is not None
    assert rc["section_order"].index("above_the_fold") < rc["section_order"].index("radar")


def test_whats_next_routing_present():
    rc, _ = _contract()
    assert rc["whats_next"]["route"]
