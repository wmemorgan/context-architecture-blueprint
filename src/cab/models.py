# SPDX-License-Identifier: MIT
"""Core data models — plain dataclasses (no heavy dependencies).

These flow through the whole pipeline: ingestion produces a Corpus of Documents;
analysis produces Signals and DimensionScores; scoring produces a Report.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Document:
    """A single parsed source document in normalized form.

    `text` is the extracted plaintext. `raw_bytes_len` records the original size
    for caps/telemetry but the raw bytes themselves are never stored on the
    document (no-retention; see cab.ingestion.retention).
    """

    name: str
    ext: str
    text: str
    raw_bytes_len: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    parsed_ok: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def doc_id(self) -> str:
        return self.name


@dataclass
class Corpus:
    """A normalized set of documents plus its provenance (upload / demo / path)."""

    documents: list[Document] = field(default_factory=list)
    source: str = "unknown"

    def __len__(self) -> int:
        return len(self.documents)


@dataclass
class Finding:
    """A single concrete, corpus-specific observation tied to one or more docs."""

    dimension: str
    severity: str  # "high" | "medium" | "low" | "info"
    message: str
    documents: list[str] = field(default_factory=list)
    evidence: str | None = None
    is_injection_attempt: bool = False


@dataclass
class Signal:
    """One check's contribution to a dimension: a 0..1 score + supporting findings."""

    dimension: str
    name: str
    method: str  # "deterministic" | "judge"
    score: float  # 0.0 .. 1.0 (1.0 == healthy)
    confidence: float = 1.0
    findings: list[Finding] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class DimensionScore:
    """The combined, weighted score for one of the seven dimensions (0..100)."""

    dimension: str
    score: float  # 0..100
    confidence: float
    method: str  # "deterministic" | "judge" | "hybrid"
    findings: list[Finding] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Everything the analysis layer produced before scoring/banding."""

    signals: list[Signal] = field(default_factory=list)
    judge_divergence: dict[str, Any] = field(default_factory=dict)

    def by_dimension(self, dimension: str) -> list[Signal]:
        return [s for s in self.signals if s.dimension == dimension]
