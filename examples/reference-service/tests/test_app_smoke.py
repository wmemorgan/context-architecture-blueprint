# SPDX-License-Identifier: MIT
"""Smoke test for the reference upload service — it serves health, demo
(no upload), upload, and the email-gated report route (unsupported example)."""

import base64

from app import app
from starlette.testclient import TestClient

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_demo_route_runs_without_upload():
    r = client.get("/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["band"] in ("L1", "L2", "L3", "L4", "L5")
    assert body["report_url"].startswith("sha256:")


def test_upload_then_gated_report():
    doc = b"---\ntitle: T\nauthor: a\ndate: 2026-05-01\nsource: s\n---\n# T\n\nWorkspaces and connectors.\n"
    payload = {"files": [{"name": "a.md", "content_b64": base64.b64encode(doc).decode()}]}
    r = client.post("/upload", json=payload)
    assert r.status_code == 200
    url = r.json()["report_url"]
    # The report route is email-gated.
    gated = client.get(f"/report/{url}")
    assert gated.status_code == 403
    unlocked = client.get(f"/report/{url}", params={"email": "lead@example.com"})
    assert unlocked.status_code == 200


def test_caps_reject_oversized_upload():
    big = base64.b64encode(b"x" * (11 * 1024 * 1024)).decode()
    payload = {"files": [{"name": "big.md", "content_b64": big}]}
    r = client.post("/upload", json=payload)
    assert r.status_code == 413
