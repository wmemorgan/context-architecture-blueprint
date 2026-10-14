# SPDX-License-Identifier: MIT
"""Two-sided calibration runner.

Loads the golden-set cases (corpora/calibration/cases.yaml), scores each, and
evaluates the two-sided guarantee:

  • a known-BAD corpus must NOT band above its `expected_max_band`, and its
    planted-defect dimension must be driven down (a MISSED BAD fails the gate);
  • a known-GOOD corpus must NOT band below its `expected_min_band`
    (a PENALIZED GOOD fails the gate).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date

import yaml

from cab.ingestion.loader import ingest_directory
from cab.pipeline import run_on_corpus
from cab.scoring.contract import load_contract

BAND_ORDER = ("L1", "L2", "L3", "L4", "L5")


def calibration_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(root, "corpora", "calibration")


@dataclass
class CaseResult:
    name: str
    kind: str
    band: str
    passed: bool
    reasons: list[str] = field(default_factory=list)
    dimension_scores: dict = field(default_factory=dict)


def _parse_date(s: str) -> date:
    y, m, d = (int(x) for x in s.split("-"))
    return date(y, m, d)


def run_calibration() -> list[CaseResult]:
    cdir = calibration_dir()
    with open(os.path.join(cdir, "cases.yaml")) as fh:
        spec = yaml.safe_load(fh)
    ref = _parse_date(spec["reference_date"])
    low = load_contract().low_threshold
    results: list[CaseResult] = []

    for case in spec["cases"]:
        corpus = ingest_directory(os.path.join(cdir, case["path"]))
        report = run_on_corpus(corpus, reference_date=ref)
        band = report["band"]
        bi = BAND_ORDER.index(band)
        reasons: list[str] = []

        if case["kind"] == "good":
            floor = BAND_ORDER.index(case["expected_min_band"])
            if bi < floor:
                reasons.append(
                    f"PENALIZED GOOD: banded {band} below floor {case['expected_min_band']}"
                )
        else:
            ceil = BAND_ORDER.index(case["expected_max_band"])
            if bi > ceil:
                reasons.append(
                    f"MISSED BAD: banded {band} above ceiling {case['expected_max_band']}"
                )
            flag = case.get("must_flag")
            if flag:
                dim = report["dimensions"].get(flag, {})
                score = dim.get("score", 100.0)
                has_finding = bool(dim.get("findings"))
                if not (score <= low and has_finding):
                    reasons.append(
                        f"DEFECT NOT DRIVEN DOWN: {flag} score={score} "
                        f"(<= {low}?) findings={has_finding}"
                    )

        results.append(
            CaseResult(
                name=case["name"],
                kind=case["kind"],
                band=band,
                passed=not reasons,
                reasons=reasons,
                dimension_scores=report["dimension_scores"],
            )
        )
    return results
