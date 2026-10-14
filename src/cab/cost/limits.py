# SPDX-License-Identifier: MIT
"""Cost-DoS / abuse cap.

Two independent ceilings guard the public per-run LLM surface:

  • a per-IP/day **rate limit** — bounds a single abuser, and
  • a hard **monthly LLM-spend ceiling** — bounds total cost across all callers.

On breach of either, the surface **degrades gracefully to demo mode** (the bundled
sample corpus, no LLM spend) rather than refusing outright or spending unbounded.

The clock is injectable (`day_key`) so the behavior is deterministic under test.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Decision(str, Enum):
    OK = "ok"
    DEGRADE_TO_DEMO = "degrade-to-demo"


def _today_key() -> str:
    return date.today().isoformat()


@dataclass
class RateLimiter:
    """Per-IP/day fixed-window counter."""

    per_ip_per_day: int = 20
    day_key: Callable[[], str] = _today_key
    _counts: dict[tuple[str, str], int] = field(default_factory=dict)

    def allow(self, ip: str) -> bool:
        key = (ip, self.day_key())
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key] <= self.per_ip_per_day

    def count(self, ip: str) -> int:
        return self._counts.get((ip, self.day_key()), 0)


@dataclass
class SpendLedger:
    """Tracks monthly LLM spend (abstract cost units) against a hard ceiling."""

    monthly_ceiling: float = 200.0  # cost units, not a currency figure
    month_key: Callable[[], str] = lambda: date.today().strftime("%Y-%m")
    _spent: dict[str, float] = field(default_factory=dict)

    def spent(self) -> float:
        return self._spent.get(self.month_key(), 0.0)

    def would_exceed(self, est_cost: float) -> bool:
        return self.spent() + est_cost > self.monthly_ceiling

    def record(self, cost: float) -> None:
        k = self.month_key()
        self._spent[k] = self._spent.get(k, 0.0) + cost


@dataclass
class CostGuard:
    """Combines the rate limit and the spend ceiling into one admission decision."""

    rate: RateLimiter = field(default_factory=RateLimiter)
    ledger: SpendLedger = field(default_factory=SpendLedger)

    def admit(self, ip: str, est_cost: float = 1.0) -> Decision:
        """Decide whether a paid (LLM) run is admitted, or must degrade to demo."""
        if not self.rate.allow(ip):
            return Decision.DEGRADE_TO_DEMO
        if self.ledger.would_exceed(est_cost):
            return Decision.DEGRADE_TO_DEMO
        return Decision.OK

    def charge(self, cost: float) -> None:
        self.ledger.record(cost)
