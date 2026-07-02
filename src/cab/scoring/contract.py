# SPDX-License-Identifier: MIT
"""Load + validate the locked, reproducible scoring contract.

Validation enforces the load-bearing invariants:
  • all seven dimensions are weighted and weights sum to ~1.0;
  • Cross-Document Consistency and Attributability are the heaviest, each
    exceeding every other dimension by at least `heaviest_min_delta`;
  • cut-lines, low-threshold, arbitration rule, and rounding are present + typed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import yaml

from cab import DIMENSIONS


@dataclass(frozen=True)
class ScoringContract:
    contract_version: str
    weights: dict[str, float]
    heaviest_min_delta: float
    heaviest_dimensions: tuple[str, ...]
    method_weights: dict[str, float]
    cut_lines: dict[str, float]
    low_threshold: float
    critical_severity_caps: dict[str, float]
    band_ceilings: dict[str, dict]
    dual_run_arbitration: str
    score_decimals: int


def default_contract_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    return os.path.join(root, "config", "scoring_contract.yaml")


def load_contract(path: str | None = None) -> ScoringContract:
    path = path or default_contract_path()
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    contract = ScoringContract(
        contract_version=str(raw["contract_version"]),
        weights={k: float(v) for k, v in raw["weights"].items()},
        heaviest_min_delta=float(raw["heaviest_min_delta"]),
        heaviest_dimensions=tuple(raw["heaviest_dimensions"]),
        method_weights={k: float(v) for k, v in raw["method_weights"].items()},
        cut_lines={k: float(v) for k, v in raw["cut_lines"].items()},
        low_threshold=float(raw["low_threshold"]),
        critical_severity_caps={
            k: float(v) for k, v in raw.get("critical_severity_caps", {}).items()
        },
        band_ceilings=raw.get("band_ceilings", {}),
        dual_run_arbitration=str(raw["dual_run_arbitration"]),
        score_decimals=int(raw["score_decimals"]),
    )
    _validate(contract)
    return contract


def _validate(c: ScoringContract) -> None:
    missing = set(DIMENSIONS) - set(c.weights)
    if missing:
        raise ValueError(f"scoring contract is missing weights for: {sorted(missing)}")
    total = sum(c.weights.values())
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"scoring weights must sum to 1.0 (got {total:.4f})")
    if set(c.heaviest_dimensions) != {"cross_document_consistency", "attributability"}:
        raise ValueError("heaviest_dimensions must be cross_document_consistency + attributability")
    others = [d for d in DIMENSIONS if d not in c.heaviest_dimensions]
    max_other = max(c.weights[d] for d in others)
    for h in c.heaviest_dimensions:
        if c.weights[h] - max_other < c.heaviest_min_delta:
            raise ValueError(
                f"Weighting invariant violated: Cross-Document Consistency and Attributability "
                f"must carry the two highest weights — '{h}' weight {c.weights[h]} does not exceed "
                f"the heaviest non-headline dimension ({max_other}) by >= {c.heaviest_min_delta}"
            )
    for band in ("L5", "L4", "L3", "L2"):
        if band not in c.cut_lines:
            raise ValueError(f"cut_lines missing band {band}")
    if c.dual_run_arbitration not in ("min", "mean", "max"):
        raise ValueError(f"unknown arbitration rule: {c.dual_run_arbitration}")
