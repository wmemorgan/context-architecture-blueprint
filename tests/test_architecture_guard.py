# SPDX-License-Identifier: MIT
"""Structural clean-architecture guard (ports & adapters / deployment-neutral core).

Fails in CI if the core engine takes on a dependency the architecture forbids:

  1. a provider SDK (``anthropic``, ``openai``, ...) imported anywhere in the core
     EXCEPT the single judge adapter that is *allowed* to bind to a provider — every
     other module must reach the judge only through the ``Judge`` port;
  2. an HTTP/web framework (``starlette``, ``fastapi``, ``uvicorn``, ...) imported
     anywhere in the core — the engine is deployment-neutral and the reference
     service owns the entire web surface;
  3. a deployment artifact (Dockerfile, compose, cloudbuild, ...) anywhere in the
     repository OUTSIDE ``examples/``.

Enforced structurally so an accidental ``import anthropic`` in the scoring core, or
a stray root ``Dockerfile``, breaks the build rather than shipping.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "src" / "cab"

# The ONE adapter allowed to bind to a concrete LLM provider.
JUDGE_ADAPTER = CORE / "analysis" / "judge.py"

PROVIDER_SDKS = {
    "anthropic",
    "openai",
    "cohere",
    "google",
    "mistralai",
    "ollama",
    "vertexai",
    "boto3",
}
WEB_FRAMEWORKS = {
    "starlette",
    "fastapi",
    "uvicorn",
    "flask",
    "django",
    "aiohttp",
    "sanic",
    "quart",
}


def _import_roots(path: Path) -> set[str]:
    """Return the top-level package name of every import in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _core_files() -> list[Path]:
    return sorted(CORE.rglob("*.py"))


def test_no_provider_sdk_in_core_except_judge_adapter() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _core_files():
        if path == JUDGE_ADAPTER:
            continue
        leaked = _import_roots(path) & PROVIDER_SDKS
        if leaked:
            offenders[str(path.relative_to(ROOT))] = sorted(leaked)
    assert not offenders, f"provider SDK imported in core (only the judge adapter may): {offenders}"


def test_no_web_framework_in_core() -> None:
    offenders: dict[str, list[str]] = {}
    for path in _core_files():
        leaked = _import_roots(path) & WEB_FRAMEWORKS
        if leaked:
            offenders[str(path.relative_to(ROOT))] = sorted(leaked)
    assert not offenders, f"web framework imported in the deployment-neutral core: {offenders}"


def test_no_deploy_artifacts_outside_examples() -> None:
    exact = {
        "docker-compose.yml",
        "docker-compose.yaml",
        "cloudbuild.yaml",
        "cloudbuild.yml",
        "skaffold.yaml",
        ".dockerignore",
        ".gcloudignore",
        "service.yaml",
        "service.yml",
        "procfile",
    }
    skip_dirs = {
        ".git",
        ".venv",
        "venv",
        "internal",
        ".worktrees",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "examples",
    }
    offenders: list[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            low = fn.lower()
            if low.startswith("dockerfile") or low in exact or "cloudbuild" in low:
                offenders.append(os.path.relpath(os.path.join(dirpath, fn), ROOT))
    assert not offenders, f"deploy artifact(s) found outside examples/: {offenders}"
