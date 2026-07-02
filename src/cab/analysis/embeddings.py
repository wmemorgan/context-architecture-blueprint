# SPDX-License-Identifier: MIT
"""Pluggable embedding interface for near-duplicate + terminology clustering.

The embedding provider is a swappable dependency (a known limitation, low severity):
pinned at intake, exposed here as an interface so the public engine carries no
operational coupling. The default `HashingEmbedder` is dependency-free and
deterministic (a hashed bag-of-words vector), so the engine + tests run
hermetically. A production deployment can inject a real embedding provider.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Deterministic hashed bag-of-words → L2-normalized vector."""

    def __init__(self, dims: int = 512) -> None:
        self.dims = dims

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for tok in tokenize(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % self.dims
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))
