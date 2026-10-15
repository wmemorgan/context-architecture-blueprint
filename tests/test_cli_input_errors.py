# SPDX-License-Identifier: MIT
"""The engine refuses to score nothing: a missing folder, an empty folder, or a folder with no
supported documents is an input error (exit code 2), never a readiness band."""

from __future__ import annotations

from pathlib import Path

import pytest

from cab.cli import main
from cab.ingestion.loader import ingest_files
from cab.pipeline import EmptyCorpus, run_on_corpus


def test_empty_corpus_is_refused() -> None:
    with pytest.raises(EmptyCorpus):
        run_on_corpus(ingest_files([], source="test"))


def test_analyze_missing_directory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["analyze", str(tmp_path / "missing")]) == 2
    out = capsys.readouterr()
    assert "not a directory" in out.err
    assert "Band:" not in out.out


def test_analyze_empty_directory(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["analyze", str(tmp_path)]) == 2
    out = capsys.readouterr()
    assert "no supported documents" in out.err
    assert "Band:" not in out.out


def test_analyze_only_unsupported_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n")
    assert main(["analyze", str(tmp_path)]) == 2
    assert "no supported documents" in capsys.readouterr().err


def test_analyze_prints_completion_after_the_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "a.md").write_text("# Refunds\nRefunds are issued within 30 days.\n")
    assert main(["analyze", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert out.index("Analysis complete.") < out.index("Band:")
