# SPDX-License-Identifier: MIT
"""A judge that OMITS a dimension must NOT inflate the band (a latent false-high failure mode).

An earlier fix made the response *parser* default a missing dimension to a conservative
0.5. A SECOND instance lived in the dual_run / score-aggregation path: a
`.get(dim, 1.0)` fallback. A judge that simply omits a dimension there would have
silently yielded a PERFECT 1.0 for that dimension — the exact worst-output risk (a gap riding
the average up into L4/L5). These tests pin the conservative resolution in the
dual_run path specifically, with NO API key (hermetic).
"""

from cab.analysis.judge import (
    JUDGE_DIMENSIONS,
    MISSING_DIM_SCORE,
    JudgePass,
    dual_run,
)
from cab.models import Corpus, Document


class _OmitsDimensionJudge:
    """A deterministic judge that DROPS one dimension from its scores dict."""

    def __init__(self, omit: str):
        self.omit = omit

    def run(self, corpus: Corpus) -> JudgePass:
        scores = {d: 1.0 for d in JUDGE_DIMENSIONS if d != self.omit}
        return JudgePass(scores=scores, narrative="ok")


def _corpus() -> Corpus:
    return Corpus(documents=[Document(name="a.md", ext="md", text="hello world")])


def test_missing_dim_resolves_to_conservative_default_not_perfect():
    omit = "cross_document_consistency"
    result = dual_run(_corpus(), judge=_OmitsDimensionJudge(omit))

    by_dim = {s.dimension: s for s in result.signals}
    # The omitted dimension must resolve to the conservative midpoint, NEVER 1.0.
    assert by_dim[omit].score == MISSING_DIM_SCORE, (
        f"FALSE-HIGH: a judge omitting {omit!r} inflated its dual_run score to "
        f"{by_dim[omit].score} instead of the conservative {MISSING_DIM_SCORE}"
    )
    assert by_dim[omit].score != 1.0, "missing dimension must never become a perfect score"


def test_present_dimensions_unaffected_by_the_fallback():
    omit = "attributability"
    result = dual_run(_corpus(), judge=_OmitsDimensionJudge(omit))
    by_dim = {s.dimension: s for s in result.signals}
    # Dimensions the judge DID emit keep their real value (here 1.0) — the
    # conservative default applies ONLY to the missing one.
    for d in JUDGE_DIMENSIONS:
        if d == omit:
            continue
        assert by_dim[d].score == 1.0


def test_every_missing_dimension_is_covered():
    # Whichever single dimension is dropped, it (and only it) collapses to 0.5.
    for omit in JUDGE_DIMENSIONS:
        result = dual_run(_corpus(), judge=_OmitsDimensionJudge(omit))
        by_dim = {s.dimension: s.score for s in result.signals}
        assert by_dim[omit] == MISSING_DIM_SCORE
        assert all(by_dim[d] == 1.0 for d in JUDGE_DIMENSIONS if d != omit)


# ── CAB_FORCE_MOCK_JUDGE (optional hardening; additive, zero default-change) ──

from cab.analysis import judge as _judge_mod


def test_force_mock_overrides_present_key(monkeypatch):
    """Flag truthy + key present -> MockJudge (deterministic local/CI switch)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-not-real")
    for val in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("CAB_FORCE_MOCK_JUDGE", val)
        assert isinstance(_judge_mod.default_judge(), _judge_mod.MockJudge), val


def test_default_behavior_unchanged_when_flag_unset(monkeypatch):
    """Key present + flag unset/falsy -> ClaudeJudge (no behavior change)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-not-real")
    monkeypatch.delenv("CAB_FORCE_MOCK_JUDGE", raising=False)
    assert isinstance(_judge_mod.default_judge(), _judge_mod.ClaudeJudge)
    monkeypatch.setenv("CAB_FORCE_MOCK_JUDGE", "0")  # falsy -> still live
    assert isinstance(_judge_mod.default_judge(), _judge_mod.ClaudeJudge)


def test_no_key_still_mock(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CAB_FORCE_MOCK_JUDGE", raising=False)
    assert isinstance(_judge_mod.default_judge(), _judge_mod.MockJudge)
