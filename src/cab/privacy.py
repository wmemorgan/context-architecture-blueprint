# SPDX-License-Identifier: MIT
"""Engine-neutral privacy controls (the persisted-report privacy constraint) — span cap + retention policy.

Two load-bearing, POLICY-NEUTRAL mechanisms live here:

  • **Span cap (the minimal-span rule).** A finding/manifest references documents by NAME and may
    quote only a *minimal* span to make the finding legible. The live judge does
    not always obey that, so a deterministic **post-process scrub** guarantees the
    cap on everything persisted — belt-and-suspenders behind the prompt. Caps are
    config (``config/privacy.yaml``), never a hardcoded hosted value.

  • **Retention policy (the report self-expiry rule).** The persisted derived report self-expires; a
    conservative engine default (short TTL) **plus** an ephemeral/no-persist
    option. The engine imposes no hosted value (30/14 live in the deployment).

The scrub finds the maximal *verbatim* source run inside each persisted prose
string and, if it exceeds the cap, keeps only the leading minimal span + an
elision marker. Templated/paraphrased prose (no long verbatim run) is returned
byte-for-byte unchanged, so the scrub never mangles non-quoting text.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import yaml


@dataclass(frozen=True)
class SpanCap:
    max_words: int
    max_chars: int
    elision_marker: str = "[…]"


@dataclass(frozen=True)
class RetentionPolicy:
    mode: str  # "ttl" | "ephemeral"
    ttl_seconds: float | None  # None == no expiry (only meaningful for mode="ttl")

    @property
    def ephemeral(self) -> bool:
        return self.mode == "ephemeral"


@dataclass(frozen=True)
class PrivacyConfig:
    privacy_version: str
    span_cap: SpanCap
    retention: RetentionPolicy


def default_privacy_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", ".."))
    return os.path.join(root, "config", "privacy.yaml")


# A hosted retention value must never be baked into the engine (deployment config, not engine default).
_FORBIDDEN_HOSTED_TTL_SECONDS = {30 * 86400, 14 * 86400}


def load_privacy_config(path: str | None = None) -> PrivacyConfig:
    path = path or default_privacy_path()
    with open(path) as fh:
        raw = yaml.safe_load(fh)
    sc = raw.get("span_cap", {})
    rt = raw.get("retention", {})
    cap = SpanCap(
        max_words=int(sc.get("max_words", 15)),
        max_chars=int(sc.get("max_chars", 120)),
        elision_marker=str(sc.get("elision_marker", "[…]")),
    )
    ttl = rt.get("ttl_seconds")
    retention = RetentionPolicy(
        mode=str(rt.get("mode", "ttl")),
        ttl_seconds=(float(ttl) if ttl is not None else None),
    )
    cfg = PrivacyConfig(
        privacy_version=str(raw.get("privacy_version", "0")),
        span_cap=cap,
        retention=retention,
    )
    _validate(cfg)
    return cfg


def _validate(cfg: PrivacyConfig) -> None:
    if cfg.retention.mode not in ("ttl", "ephemeral"):
        raise ValueError(f"unknown retention mode: {cfg.retention.mode!r}")
    if cfg.span_cap.max_words < 1 or cfg.span_cap.max_chars < 1:
        raise ValueError("span cap must be >= 1 word / >= 1 char")
    # Privacy constraint: the engine is policy-neutral — a hosted TTL value
    # (30/14 days) must never be hardcoded as the engine default.
    if cfg.retention.ttl_seconds in _FORBIDDEN_HOSTED_TTL_SECONDS:
        raise ValueError(
            "engine retention.ttl_seconds must not hardcode a hosted policy value "
            "(30/14 days) — that is deployment config"
        )


# ── scrub ────────────────────────────────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def build_source_index(source_texts: Iterable[str]) -> str:
    """Whitespace-normalized, lowercased concatenation of all source documents."""
    return _norm("\n".join(source_texts))


def _cap_prefix(words: list[str], cap: SpanCap) -> str:
    kept = words[: cap.max_words]
    s = " ".join(kept)
    if len(s) > cap.max_chars:
        cut = s[: cap.max_chars]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        s = cut
    return s


def scrub_text(text: str, source_index: str, cap: SpanCap) -> str:
    """Cap any verbatim source span in ``text`` that exceeds the configured cap.

    Returns the text unchanged unless a maximal verbatim run > cap is found, in
    which case that run is replaced by its leading minimal span + elision marker.
    """
    if not text or not source_index:
        return text
    words = text.split()
    out: list[str] = []
    i = 0
    n = len(words)
    changed = False
    while i < n:
        # Greedily extend the maximal verbatim run starting at word i.
        end = i
        cur = ""
        while end < n:
            cand = words[end] if not cur else f"{cur} {words[end]}"
            if _norm(cand) in source_index:
                cur = cand
                end += 1
            else:
                break
        run = words[i:end]
        run_str = " ".join(run)
        if len(run) >= 2 and (len(run) > cap.max_words or len(run_str) > cap.max_chars):
            out.append(f"{_cap_prefix(run, cap)} {cap.elision_marker}")
            changed = True
            i = end
        else:
            out.append(words[i])
            i += 1
    return " ".join(out) if changed else text


def longest_verbatim_run(text: str, source_index: str) -> int:
    """Length (chars) of the longest contiguous verbatim source span in ``text``.

    Used by the span-cap eval/tests to assert the scrub holds even on over-quoting.
    """
    if not text or not source_index:
        return 0
    words = text.split()
    n = len(words)
    best = 0
    i = 0
    while i < n:
        end = i
        cur = ""
        while end < n:
            cand = words[end] if not cur else f"{cur} {words[end]}"
            if _norm(cand) in source_index:
                cur = cand
                end += 1
            else:
                break
        run_len = len(" ".join(words[i:end]))
        best = max(best, run_len)
        i = end if end > i else i + 1
    return best


# Doc-name / identifier fields are references, not quoted prose — never scrubbed.
_SKIP_KEYS = {
    "documents",
    "report_url",
    "band",
    "contract_version",
    "owner",
    "domain",
    "footer",
    "standard",
    "product",
    "cites",
    "dimension",
    "method",
    "route",
    "derived_from",
}


def scrub_report(report: Any, source_index: str, cap: SpanCap) -> Any:
    """Recursively cap verbatim source spans across every persisted prose leaf.

    Walks the derived report in place — findings[].message/evidence, the
    narrative, manifest items, and the render contract — leaving doc-name
    references and structured identifiers intact (no-file-retention + minimal-span rules).
    """
    if isinstance(report, dict):
        for k, v in report.items():
            if k in _SKIP_KEYS:
                continue
            report[k] = scrub_report(v, source_index, cap)
        return report
    if isinstance(report, list):
        return [scrub_report(v, source_index, cap) for v in report]
    if isinstance(report, str):
        return scrub_text(report, source_index, cap)
    return report
