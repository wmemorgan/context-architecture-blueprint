# SPDX-License-Identifier: MIT
"""Brand interface — the WM.com brand applied to the report + PDF.

Pluggable: the engine emits a render contract and a branded PDF using this
profile; the site owns the live visual system. The authored standard headline is
fixed: The Comprehension Standard is foregrounded; public framework
canon appears only as citations.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BrandProfile:
    owner: str = "Wilfred Morgan"
    domain: str = "wilfredmorgan.com"
    product: str = "The Context Architecture Blueprint"
    standard: str = "The Comprehension Standard"
    primary_color: str = "#0B1F3A"
    accent_color: str = "#2F80ED"
    footer: str = "Wilfred Morgan · wilfredmorgan.com"
    # Public framework canon — cited foundations only, never the headline.
    cites: tuple[str, ...] = field(
        default_factory=lambda: (
            "Context Engineering",
            "RAGAS",
            "DeepEval",
            "DAMA-DMBOK",
            "Dublin Core",
            "schema.org",
            "W3C PROV",
            "C2PA",
            "LangChain",
            "LlamaIndex",
            "GraphRAG",
        )
    )

    def markers(self) -> tuple[str, ...]:
        """Brand markers that must appear on the branded surface (asserted by the brand-gate tests)."""
        return (self.owner, self.domain, self.standard)


DEFAULT_BRAND = BrandProfile()
