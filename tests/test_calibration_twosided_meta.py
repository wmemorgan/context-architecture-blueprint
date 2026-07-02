# SPDX-License-Identifier: MIT
"""C1b — prove the two-sided calibration gate FAILS in BOTH directions: on a
MISSED BAD (a defect that did not drive the band down) AND on a PENALIZED GOOD
(a genuinely good corpus banded below its floor). The shipping cases.yaml passes;
this meta-test drives the REAL evaluator with deliberately-wrong expectations and
asserts each direction trips a failure.
"""

import os
import textwrap

import cab.calibration as calib
from cab.calibration import run_calibration

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAL = os.path.join(ROOT, "corpora", "calibration")


def _run_with_cases(tmp_path, monkeypatch, cases_yaml: str):
    (tmp_path / "cases.yaml").write_text(cases_yaml)
    monkeypatch.setattr(calib, "calibration_dir", lambda: str(tmp_path))
    return run_calibration()


def test_missed_bad_fails_the_gate(tmp_path, monkeypatch):
    # good_strong bands high; declaring it "bad, max L2" must trip a MISSED BAD.
    cases = textwrap.dedent(f"""
        reference_date: "2026-06-28"
        band_order: [L1, L2, L3, L4, L5]
        cases:
          - name: planted_missed_bad
            kind: bad
            path: {os.path.join(CAL, "good_strong")}
            expected_max_band: L2
            must_flag: cross_document_consistency
    """)
    results = {r.name: r for r in _run_with_cases(tmp_path, monkeypatch, cases)}
    r = results["planted_missed_bad"]
    assert not r.passed
    assert any("MISSED BAD" in x or "DEFECT NOT DRIVEN DOWN" in x for x in r.reasons)


def test_penalized_good_fails_the_gate(tmp_path, monkeypatch):
    # bad_missing_metadata bands L3; declaring it "good, floor L5" trips PENALIZED GOOD.
    cases = textwrap.dedent(f"""
        reference_date: "2026-06-28"
        band_order: [L1, L2, L3, L4, L5]
        cases:
          - name: planted_penalized_good
            kind: good
            path: {os.path.join(CAL, "bad_missing_metadata")}
            expected_min_band: L5
    """)
    results = {r.name: r for r in _run_with_cases(tmp_path, monkeypatch, cases)}
    r = results["planted_penalized_good"]
    assert not r.passed
    assert any("PENALIZED GOOD" in x for x in r.reasons)


def test_shipping_golden_set_passes_both_sides():
    results = run_calibration()
    assert results and all(r.passed for r in results)
    assert {"good", "bad"} <= {r.kind for r in results}
