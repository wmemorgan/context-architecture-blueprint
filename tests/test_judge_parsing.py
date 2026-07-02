# SPDX-License-Identifier: MIT
"""Hermetic regression tests for the live-judge response parser (no key, no network).

These pin `_parse_judge_response` against the ACTUAL output shapes claude-sonnet
(temp 0.0) was observed to emit during the C2 live-judge pass. The original parser
assumed the flat schema the MockJudge produces and crashed on the live judge
(findings keyed by dimension → AttributeError); the mock could never have caught it.
"""

import pytest

from cab.analysis.judge import JUDGE_DIMENSIONS, _parse_judge_response


def _cdc(p):
    return [f for f in p.findings if f.dimension == "cross_document_consistency"]


def test_findings_keyed_by_dimension_with_fence():
    """The exact shape that crashed C2: ```json fence + findings as a dict keyed by dim."""
    text = (
        "```json\n"
        '{ "scores": {"cross_document_consistency": 0.05, "attributability": 0.4, '
        '"terminology_consistency": 0.35},\n'
        '  "findings": {\n'
        '    "cross_document_consistency": [{"documents": ["policy.md","faq.md"], '
        '"issue": "Direct contradiction on retention duration."}],\n'
        '    "attributability": [{"documents":["policy.md"], "issue":"No source cited."}]\n'
        "  },\n"
        '  "readiness_narrative": "Not ready." }\n'
        "```"
    )
    p = _parse_judge_response(text)
    assert p.scores["cross_document_consistency"] == 0.05
    cdc = _cdc(p)
    assert len(cdc) == 1
    assert set(cdc[0].documents) == {"policy.md", "faq.md"}
    assert cdc[0].severity == "high"  # inferred from the low cdc score → trips the band cap
    assert "contradiction" in cdc[0].message.lower()
    assert p.narrative == "Not ready."


def test_dims_at_top_level_and_overall_scores():
    """{dim: {score, findings}} with scores under `overall_scores`, wrapped in `analysis`."""
    text = (
        '{ "analysis": {'
        '  "cross_document_consistency": {"score":0.05,"findings":[{"documents":["a.md","b.md"],'
        '"finding":"contradiction"}]},'
        '  "attributability": {"score":0.4,"findings":[]},'
        '  "terminology_consistency":{"score":0.35,"findings":[]},'
        '  "overall_scores": {"cross_document_consistency":0.05,"attributability":0.4,'
        '"terminology_consistency":0.35},'
        '  "readiness_narrative":"x"}}'
    )
    p = _parse_judge_response(text)
    assert p.scores == {
        "cross_document_consistency": 0.05,
        "attributability": 0.4,
        "terminology_consistency": 0.35,
    }
    cdc = _cdc(p)
    assert cdc and set(cdc[0].documents) == {"a.md", "b.md"}


def test_clean_flat_list_no_findings():
    text = (
        '{"scores":{"cross_document_consistency":0.95,"attributability":0.9,'
        '"terminology_consistency":0.92},"findings":[],"narrative":"clean"}'
    )
    p = _parse_judge_response(text)
    assert p.scores["cross_document_consistency"] == 0.95
    assert p.findings == []


def test_flat_list_with_explicit_severity():
    text = (
        '{"scores":{"cross_document_consistency":0.1,"attributability":0.8,'
        '"terminology_consistency":0.8},'
        '"findings":[{"dimension":"cross_document_consistency","severity":"high",'
        '"message":"They disagree","documents":["x.md","y.md"]}],"narrative":"n"}'
    )
    p = _parse_judge_response(text)
    f = _cdc(p)[0]
    assert f.severity == "high" and set(f.documents) == {"x.md", "y.md"}


def test_missing_dimension_defaults_conservative_not_inflated():
    """A judge that omits a dimension must NOT default it to a band-inflating 1.0."""
    text = '{"scores":{"attributability":0.9,"terminology_consistency":0.9},"findings":[]}'
    p = _parse_judge_response(text)
    assert p.scores["cross_document_consistency"] == 0.5  # conservative neutral, not 1.0


@pytest.mark.parametrize("text", ["not json at all", "", "{ broken json", "[]"])
def test_unparseable_falls_back_safely(text):
    p = _parse_judge_response(text)
    assert all(p.scores[d] == 0.5 for d in JUDGE_DIMENSIONS)
    assert p.findings == []
