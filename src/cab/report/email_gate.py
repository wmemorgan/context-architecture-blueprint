# SPDX-License-Identifier: MIT
"""Email gate + report retention.

The rendered report + branded PDF require an email before download. The gate
captures the lead via the pluggable email interface and persists ONLY the derived
report (no source bytes; capped findings/manifest per the persisted-report privacy constraint).

Retention is policy-neutral a persisted report carries an optional TTL
and self-expires; an **ephemeral** mode persists nothing at all. The engine sets
no hosted value — a deployment passes its own ``ttl_seconds``/``mode``.
"""

from __future__ import annotations

import time
from typing import Any

from cab.interfaces.email import DEFAULT_SINK, EmailSink, valid_email

# In-memory registry of derived reports keyed by report URL (no source bytes).
_REGISTRY: dict[str, dict[str, Any]] = {}
# Parallel retention metadata: report_url -> {"stored_at": float, "ttl_seconds": float|None}.
_META: dict[str, dict[str, Any]] = {}


def register_report(
    report_url: str,
    report: dict[str, Any],
    email: str | None = None,
    sink: EmailSink = DEFAULT_SINK,
    *,
    ttl_seconds: float | None = None,
    mode: str = "ttl",
    now: float | None = None,
) -> None:
    """Persist the derived report behind its gated URL; capture a lead if provided.

    mode="ephemeral" persists nothing (no-persist option); mode="ttl"
    persists with an optional self-expiry window. ``now`` is injectable for tests.
    """
    if mode == "ephemeral":
        if valid_email(email):
            sink.capture(email.strip(), report_url)  # type: ignore[union-attr]
        return
    _REGISTRY[report_url] = report
    _META[report_url] = {
        "stored_at": now if now is not None else time.time(),
        "ttl_seconds": ttl_seconds,
    }
    if valid_email(email):
        sink.capture(email.strip(), report_url)  # type: ignore[union-attr]


def _expired(report_url: str, now: float | None = None) -> bool:
    meta = _META.get(report_url)
    if not meta:
        return False
    ttl = meta.get("ttl_seconds")
    if ttl is None:
        return False
    return (now if now is not None else time.time()) >= meta["stored_at"] + ttl


def purge_expired(now: float | None = None) -> list[str]:
    """Delete every report past its TTL. Returns the purged report URLs."""
    dead = [u for u in list(_REGISTRY) if _expired(u, now)]
    for u in dead:
        _REGISTRY.pop(u, None)
        _META.pop(u, None)
    return dead


def _get(report_id: str, now: float | None = None) -> dict[str, Any] | None:
    """Fetch a persisted report, deleting it first if it is past its TTL."""
    if _expired(report_id, now):
        _REGISTRY.pop(report_id, None)
        _META.pop(report_id, None)
    return _REGISTRY.get(report_id)


def _teaser(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_url": report.get("report_url"),
        "band": report.get("band"),
        "gated": True,
        "message": "Enter your email to unlock the full report, the Blueprint Manifest, "
        "and the branded PDF.",
    }


def fetch_gated(
    report_id: str, email: str | None, sink: EmailSink = DEFAULT_SINK
) -> tuple[dict[str, Any], int]:
    """Return (payload, http_status). Email is REQUIRED for the full report."""
    report = _get(report_id)
    if report is None:
        return {"error": "report not found"}, 404
    if not valid_email(email):
        return _teaser(report), 403
    sink.capture(email.strip(), report_id)  # type: ignore[union-attr]
    return {**report, "gated": False, "pdf_available": True}, 200


def get_pdf(report_id: str, email: str | None) -> tuple[bytes | None, int]:
    """Return (pdf_bytes, status). Gated identically to the report."""
    report = _get(report_id)
    if report is None:
        return None, 404
    if not valid_email(email):
        return None, 403
    from cab.report.pdf import render_pdf

    return render_pdf(report), 200


def _clear() -> None:  # test helper
    _REGISTRY.clear()
    _META.clear()
