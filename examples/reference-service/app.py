# SPDX-License-Identifier: MIT
"""Reference upload service (Starlette ASGI) — UNSUPPORTED EXAMPLE.

This is an illustrative way to wrap the Context Architecture Blueprint *library*
behind an upload surface — not a product and not the supported core. The
supported core is the Python library + CLI (`python -m cab.cli`). You supply
authentication, durable storage, secrets management, network controls, and any
data-retention policy appropriate to your environment.

Endpoints:
  GET  /healthz            — liveness.
  GET  /demo               — run the full analysis over the bundled sample corpus (no upload).
  POST /upload             — analyze an uploaded corpus. JSON body:
                               {"files": [{"name": "a.md", "content_b64": "..."}], "email": "..."}
                             Caps + cost-DoS guard are enforced; on breach the request
                             degrades gracefully to demo mode (no LLM spend).
  GET  /report/{report_id} — fetch a rendered report; EMAIL-GATED (see cab.report.email_gate).

Document parsing and the LLM judge are pluggable; the service carries no
operational coupling (email/pipeline/brand are interfaces).
"""

from __future__ import annotations

import base64

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from cab.cost.limits import CostGuard, Decision
from cab.ingestion.caps import CapExceeded, Caps, enforce

# One process-wide cost guard (per-IP/day rate limit + monthly spend ceiling).
COST_GUARD = CostGuard()
CAPS = Caps()


async def healthz(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "context-architecture-blueprint"})


async def demo(_request: Request) -> JSONResponse:
    from cab.pipeline import run_demo

    report = run_demo()
    return JSONResponse(_public_view(report))


async def upload(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "expected JSON body"}, status_code=400)

    raw_files = payload.get("files") or []
    files: list[tuple[str, bytes]] = []
    for item in raw_files:
        try:
            files.append((item["name"], base64.b64decode(item["content_b64"])))
        except Exception:
            return JSONResponse({"error": "invalid file entry"}, status_code=400)

    try:
        enforce(files, CAPS)
    except CapExceeded as exc:
        return JSONResponse({"error": f"caps exceeded: {exc}"}, status_code=413)

    client_ip = request.client.host if request.client else "unknown"
    decision = COST_GUARD.admit(client_ip, est_cost=float(len(files)))
    if decision == Decision.DEGRADE_TO_DEMO:
        from cab.pipeline import run_demo

        report = run_demo()
        body = _public_view(report)
        body["degraded"] = "rate-limit-or-spend-ceiling → demo mode"
        return JSONResponse(body, status_code=429)

    from cab.pipeline import run_on_files

    report = run_on_files(files, email=payload.get("email"))
    COST_GUARD.charge(float(len(files)))
    return JSONResponse(_public_view(report))


async def get_report(request: Request) -> JSONResponse:
    from cab.report.email_gate import fetch_gated

    report_id = request.path_params["report_id"]
    email = request.query_params.get("email")
    result, status = fetch_gated(report_id, email)
    return JSONResponse(result, status_code=status)


def _public_view(report: dict) -> dict:
    """Trim a report to its public, no-source view for an API response."""
    return {
        "report_url": report.get("report_url"),
        "band": report.get("band"),
        "confidence": report.get("confidence"),
        "dimension_scores": report.get("dimension_scores"),
        "manifest_summary": (report.get("manifest") or {}).get("summary"),
        "scope_disclaimer": report.get("scope_disclaimer"),
    }


routes = [
    Route("/healthz", healthz, methods=["GET"]),
    Route("/demo", demo, methods=["GET"]),
    Route("/upload", upload, methods=["POST"]),
    Route("/report/{report_id}", get_report, methods=["GET"]),
]

app = Starlette(routes=routes)
