# SPDX-License-Identifier: MIT
"""Combine signals into per-dimension scores and an L1–L5 band under the locked
contract. Deterministic and reproducible: identical inputs → identical output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cab import DIMENSIONS
from cab.models import AnalysisResult, Finding
from cab.scoring.contract import ScoringContract, load_contract


@dataclass
class DimensionResult:
    dimension: str
    score: float  # 0..100
    confidence: float
    method: str
    weight: float
    findings: list[Finding] = field(default_factory=list)


@dataclass
class ScoreResult:
    band: str
    overall_score: float
    confidence: float
    dimensions: dict[str, DimensionResult]
    contract_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "band": self.band,
            "overall_score": self.overall_score,
            "confidence": self.confidence,
            "contract_version": self.contract_version,
            "dimension_scores": {d: round(r.score, 4) for d, r in self.dimensions.items()},
            "dimensions": {
                d: {
                    "score": r.score,
                    "confidence": r.confidence,
                    "method": r.method,
                    "weight": r.weight,
                    "findings": [
                        {
                            "severity": f.severity,
                            "message": f.message,
                            "documents": f.documents,
                            "evidence": f.evidence,
                            "is_injection_attempt": f.is_injection_attempt,
                        }
                        for f in r.findings
                    ],
                }
                for d, r in self.dimensions.items()
            },
        }


def score(analysis: AnalysisResult, contract: ScoringContract | None = None) -> ScoreResult:
    c = contract or load_contract()
    divergence = (analysis.judge_divergence or {}).get("per_dimension", {})

    dim_results: dict[str, DimensionResult] = {}
    for dim in DIMENSIONS:
        signals = analysis.by_dimension(dim)
        det = next((s for s in signals if s.method == "deterministic"), None)
        jud = next((s for s in signals if s.method == "judge"), None)

        if det and jud:
            wd, wj = c.method_weights["deterministic"], c.method_weights["judge"]
            tot = wd + wj
            combined01 = (wd * det.score + wj * jud.score) / tot
            method = "hybrid"
            conf = (det.confidence + jud.confidence) / 2
        elif det:
            combined01, method, conf = det.score, "deterministic", det.confidence
        elif jud:
            combined01, method, conf = jud.score, "judge", jud.confidence
        else:
            combined01, method, conf = 1.0, "none", 0.0

        # Judge divergence reduces confidence (uncertainty-forward).
        conf = max(0.0, conf - divergence.get(dim, 0.0))

        findings = []
        if det:
            findings += det.findings
        if jud:
            findings += jud.findings

        score100 = round(combined01 * 100.0, c.score_decimals)
        # False-high guard: a HIGH-severity finding caps the dimension score —
        # a deterministic floor cannot prop up a dimension the judge found broken.
        cap = c.critical_severity_caps.get(dim)
        if cap is not None and any(
            f.severity == "high"
            for f in ((det.findings if det else []) + (jud.findings if jud else []))
        ):
            score100 = min(score100, cap)

        dim_results[dim] = DimensionResult(
            dimension=dim,
            score=score100,
            confidence=round(conf, c.score_decimals),
            method=method,
            weight=c.weights[dim],
            findings=findings,
        )

    overall01 = sum(c.weights[d] * (dim_results[d].score / 100.0) for d in DIMENSIONS)
    overall100 = round(overall01 * 100.0, c.score_decimals)
    band = _apply_ceilings(band_for(overall100, c), dim_results, c)
    overall_conf = round(
        sum(c.weights[d] * dim_results[d].confidence for d in DIMENSIONS), c.score_decimals
    )
    return ScoreResult(
        band=band,
        overall_score=overall100,
        confidence=overall_conf,
        dimensions=dim_results,
        contract_version=c.contract_version,
    )


def band_for(overall: float, c: ScoringContract) -> str:
    for band in ("L5", "L4", "L3", "L2"):
        if overall >= c.cut_lines[band]:
            return band
    return "L1"


_BAND_ORDER = ("L1", "L2", "L3", "L4", "L5")


def _apply_ceilings(band: str, dims: dict[str, DimensionResult], c: ScoringContract) -> str:
    """Cap the band when a dimension is broken — you cannot be 'AI-ready' with a
    contradiction or untraceable claims, however high the weighted average."""
    heaviest = {"cross_document_consistency", "attributability"}
    ceilings = c.band_ceilings or {}
    any_rule = ceilings.get("any_dimension_at_or_below")
    heavy_rule = ceilings.get("heaviest_dimension_at_or_below")

    capped = band
    for dim, r in dims.items():
        if any_rule and r.score <= float(any_rule["threshold"]):
            capped = _min_band(capped, any_rule["max_band"])
        if heavy_rule and dim in heaviest and r.score <= float(heavy_rule["threshold"]):
            capped = _min_band(capped, heavy_rule["max_band"])
    return capped


def _min_band(a: str, b: str) -> str:
    return a if _BAND_ORDER.index(a) <= _BAND_ORDER.index(b) else b
