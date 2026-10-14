# SPDX-License-Identifier: MIT
"""ClaudeJudge model is configurable — explicit arg > CAB_JUDGE_MODEL env > shipped default.

Constructing a ``ClaudeJudge`` performs no network I/O (the API call happens in
``run``), so these checks are fully hermetic and need no API key.
"""

from cab.analysis.judge import ClaudeJudge


def test_defaults_to_shipped_model_when_unconfigured(monkeypatch):
    monkeypatch.delenv("CAB_JUDGE_MODEL", raising=False)
    assert ClaudeJudge().model == ClaudeJudge.MODEL


def test_env_var_overrides_shipped_default(monkeypatch):
    monkeypatch.setenv("CAB_JUDGE_MODEL", "some-newer-sonnet")
    assert ClaudeJudge().model == "some-newer-sonnet"


def test_explicit_argument_wins_over_env_var(monkeypatch):
    monkeypatch.setenv("CAB_JUDGE_MODEL", "from-env")
    assert ClaudeJudge(model="from-arg").model == "from-arg"


def test_explicit_argument_wins_when_env_unset(monkeypatch):
    monkeypatch.delenv("CAB_JUDGE_MODEL", raising=False)
    assert ClaudeJudge(model="explicit").model == "explicit"


def test_blank_env_var_falls_through_to_default(monkeypatch):
    # An empty string is falsy, so resolution falls through to the shipped default
    # rather than pinning the judge to an unusable empty model id.
    monkeypatch.setenv("CAB_JUDGE_MODEL", "")
    assert ClaudeJudge().model == ClaudeJudge.MODEL
