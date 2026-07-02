# SPDX-License-Identifier: MIT
"""Downstream pipeline interface — routes a completed analysis into the next
engagement step. Pluggable: the default is a no-op recorder; a production
deployment injects the real routing. No source content crosses this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


def route_for_band(band: str) -> str:
    """'What's next' routing by readiness band."""
    return {
        "L1": "Technology Roadmap Design",
        "L2": "Technology Roadmap Design",
        "L3": "Product Design",
        "L4": "LITMUS Comprehension Audit",
        "L5": "LITMUS Comprehension Audit",
    }.get(band, "Technology Roadmap Design")


class PipelineSink(Protocol):
    def emit(self, report_url: str, band: str, route: str) -> None: ...


@dataclass
class LocalPipelineSink:
    events: list[tuple[str, str, str]] = field(default_factory=list)

    def emit(self, report_url: str, band: str, route: str) -> None:
        self.events.append((report_url, band, route))


DEFAULT_PIPELINE = LocalPipelineSink()
