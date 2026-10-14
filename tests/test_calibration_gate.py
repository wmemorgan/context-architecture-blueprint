# SPDX-License-Identifier: MIT
"""Two-sided calibration gate: CI fails on a MISSED BAD (planted
defect not driven down) OR a PENALIZED GOOD (good corpus banded too low).
Includes an anti-gaming case (padding must not hide a contradiction)."""

from cab.calibration import run_calibration


def test_calibration_gate_two_sided():
    results = run_calibration()
    failures = [r for r in results if not r.passed]
    msg = "\n".join(f"{r.name} [{r.kind}] band={r.band}: {'; '.join(r.reasons)}" for r in failures)
    assert not failures, f"calibration gate failures:\n{msg}"


def test_calibration_has_both_sides():
    results = run_calibration()
    kinds = {r.kind for r in results}
    assert "good" in kinds and "bad" in kinds


def test_anti_gaming_contradiction_caught_despite_padding():
    results = {r.name: r for r in run_calibration()}
    ag = results["anti_gaming_padded_contradiction"]
    assert ag.passed
    # The contradiction drove cross-document consistency down despite the padding.
    assert ag.dimension_scores["cross_document_consistency"] <= 40.0


def test_known_good_not_penalized():
    results = {r.name: r for r in run_calibration()}
    assert results["good_strong"].passed
    assert results["good_modest"].passed
