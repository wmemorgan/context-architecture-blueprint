# SPDX-License-Identifier: MIT
"""ClaudeJudge temperature forward-compatibility.

Some newer models deprecate the ``temperature`` parameter and reject a request that
sets it with a 400. These hermetic tests (no key, no network — the Anthropic client
is a stand-in) assert that:

  • a model that accepts ``temperature`` still receives ``temperature=0.0`` (unchanged,
    so the reference calibration is preserved);
  • a model that 400s on ``temperature`` is transparently retried WITHOUT it and succeeds;
  • an unrelated API error is NOT swallowed — it propagates.
"""

import pytest

from cab.analysis.judge import ClaudeJudge
from cab.models import Corpus, Document

_OK_RESPONSE = (
    '{"scores": {"cross_document_consistency": 1.0, "attributability": 1.0, '
    '"terminology_consistency": 1.0}, "findings": [], "narrative": "clean"}'
)


def _corpus() -> Corpus:
    return Corpus(
        documents=[Document(name="a.md", ext="md", text="All data is encrypted at rest.")],
        source="test",
    )


class _Block:
    def __init__(self, text: str) -> None:
        self.text = text


class _Message:
    def __init__(self, text: str) -> None:
        self.content = [_Block(text)]


class _TemperatureDeprecatedError(Exception):
    """Mimics the SDK's 400 for a model that no longer accepts ``temperature``."""

    status_code = 400

    def __init__(self) -> None:
        super().__init__("temperature is deprecated for this model")
        self.message = "temperature is deprecated for this model"


class _UnrelatedError(Exception):
    """A different 400 that must NOT trigger the temperature retry."""

    status_code = 400

    def __init__(self) -> None:
        super().__init__("invalid_request_error: max_tokens too large")
        self.message = "invalid_request_error: max_tokens too large"


class _Messages:
    def __init__(self, behavior):
        self.calls: list[dict] = []
        self._behavior = behavior

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._behavior(kwargs)


class _Client:
    def __init__(self, behavior):
        self.messages = _Messages(behavior)


def test_sends_temperature_when_model_accepts_it():
    """A model that accepts temperature still gets temperature=0.0 (behavior unchanged)."""
    client = _Client(lambda _kwargs: _Message(_OK_RESPONSE))
    judge = ClaudeJudge(client=client)

    result = judge.run(_corpus())

    assert len(client.messages.calls) == 1
    assert client.messages.calls[0]["temperature"] == 0.0
    assert result.scores["cross_document_consistency"] == 1.0


def test_retries_without_temperature_when_deprecated():
    """A model that 400s on temperature is retried WITHOUT it and succeeds."""

    def behavior(kwargs):
        if "temperature" in kwargs:
            raise _TemperatureDeprecatedError()
        return _Message(_OK_RESPONSE)

    client = _Client(behavior)
    judge = ClaudeJudge(client=client)

    result = judge.run(_corpus())

    assert len(client.messages.calls) == 2
    assert "temperature" in client.messages.calls[0]  # first attempt sets it
    assert "temperature" not in client.messages.calls[1]  # retry drops it
    assert result.scores["attributability"] == 1.0


def test_unrelated_error_is_not_swallowed():
    """An unrelated 400 propagates — the retry is narrow to the temperature case."""

    def behavior(_kwargs):
        raise _UnrelatedError()

    client = _Client(behavior)
    judge = ClaudeJudge(client=client)

    with pytest.raises(_UnrelatedError):
        judge.run(_corpus())

    assert len(client.messages.calls) == 1  # no retry
