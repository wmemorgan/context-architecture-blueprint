# SPDX-License-Identifier: MIT
"""Packaging guard: what ``pip install`` ships must match what the repository runs.

Fails in CI if:

  1. ``pyproject.toml`` and ``requirements.txt`` disagree on the core runtime dependencies;
  2. a sub-package under ``src/cab/`` is missing from the explicit package list (it would be
     left out of the wheel);
  3. a default config file or demo document would be left out of the wheel;
  4. the version differs between ``pyproject.toml``, ``cab.__version__``, ``CITATION.cff``,
     and the newest ``CHANGELOG.md`` entry.

The wheel itself is built and run from a clean directory by the CI packaging job.
"""

from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.10 only
    tomllib = pytest.importorskip("tomli")

import cab
from cab._bundled import config_path, demo_corpus_dir

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
SETUPTOOLS = PYPROJECT["tool"]["setuptools"]


def _requirement_lines(path: Path) -> list[str]:
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            lines.append(line)
    return lines


def test_runtime_dependencies_match_requirements_txt() -> None:
    declared = sorted(PYPROJECT["project"]["dependencies"])
    assert declared == sorted(_requirement_lines(ROOT / "requirements.txt"))


def test_every_subpackage_is_listed() -> None:
    on_disk = {
        ".".join(init.parent.relative_to(ROOT / "src").parts)
        for init in (ROOT / "src" / "cab").rglob("__init__.py")
    }
    missing = on_disk - set(SETUPTOOLS["packages"])
    assert not missing, f"add these packages to [tool.setuptools] packages: {sorted(missing)}"


@pytest.mark.parametrize("package", ["cab._config", "cab._demo"])
def test_bundled_data_is_packaged(package: str) -> None:
    source = ROOT / SETUPTOOLS["package-dir"][package]
    patterns = SETUPTOOLS["package-data"][package]
    files = [p for p in source.iterdir() if p.is_file()]
    assert files, f"{source} is empty"
    left_out = [p.name for p in files if not any(fnmatch.fnmatch(p.name, pat) for pat in patterns)]
    assert not left_out, f"files in {source} not shipped in the wheel: {left_out}"
    assert not [p for p in source.iterdir() if p.is_dir()], f"{source} has sub-directories"


def test_bundled_paths_resolve() -> None:
    assert Path(config_path("privacy.yaml")).is_file()
    assert Path(config_path("scoring_contract.yaml")).is_file()
    assert any(Path(demo_corpus_dir()).glob("*.md"))


def test_version_is_consistent() -> None:
    version = PYPROJECT["project"]["version"]
    assert cab.__version__ == version
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(rf"^version: {re.escape(version)}$", citation, re.M)
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    newest = re.search(r"^## \[(\d+\.\d+\.\d+)\]", changelog, re.M)
    assert newest and newest.group(1) == version
