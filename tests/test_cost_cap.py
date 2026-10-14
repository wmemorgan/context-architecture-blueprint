# SPDX-License-Identifier: MIT
"""Cost-DoS / abuse cap: per-IP/day rate limit + monthly spend ceiling,
degrading to demo mode on breach with no unbounded spend."""

from cab.cost.limits import CostGuard, Decision, RateLimiter, SpendLedger


def _fixed_day():
    return "2026-06-28"


def _fixed_month():
    return "2026-06"


def test_rate_limit_degrades_after_breach():
    guard = CostGuard(
        rate=RateLimiter(per_ip_per_day=3, day_key=_fixed_day),
        ledger=SpendLedger(monthly_ceiling=1e9, month_key=_fixed_month),
    )
    ip = "203.0.113.5"
    assert [guard.admit(ip) for _ in range(3)] == [Decision.OK] * 3
    # 4th request in the window breaches → degrade to demo mode.
    assert guard.admit(ip) == Decision.DEGRADE_TO_DEMO


def test_spend_ceiling_degrades_and_bounds_total():
    ledger = SpendLedger(monthly_ceiling=10.0, month_key=_fixed_month)
    guard = CostGuard(
        rate=RateLimiter(per_ip_per_day=1000, day_key=_fixed_day),
        ledger=ledger,
    )
    spent = 0.0
    degraded = 0
    for _ in range(50):
        if guard.admit("198.51.100.9", est_cost=1.0) == Decision.OK:
            guard.charge(1.0)
            spent += 1.0
        else:
            degraded += 1
    assert spent <= 10.0  # hard ceiling — no unbounded spend
    assert degraded > 0  # surface degraded once the ceiling was reached
    assert ledger.spent() <= ledger.monthly_ceiling
