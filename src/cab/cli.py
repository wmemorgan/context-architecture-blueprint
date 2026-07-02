# SPDX-License-Identifier: MIT
"""Command-line entry point for the Context Architecture Blueprint.

    python -m cab.cli demo          # run the full analysis over the bundled sample corpus
    python -m cab.cli analyze DIR   # analyze a local directory of documents (no upload)

This is a thin adapter over :mod:`cab.pipeline`; all analysis lives in the library.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Any


def _print_summary(report: dict[str, Any]) -> None:
    """Print the headline band, report URL, and calibration provenance of a run."""
    print(f"Band: {report['band']}  Report URL: {report['report_url']}")
    label = (report.get("calibration") or {}).get("label")
    if label:
        print(f"Calibration: {label}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI over ``argv`` (defaults to ``sys.argv``); return a process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = args[0]
    if cmd == "demo":
        from cab.pipeline import run_demo

        print("Demo analysis complete.")
        _print_summary(run_demo())
        return 0
    if cmd == "analyze":
        if len(args) < 2:
            print("usage: analyze DIR", file=sys.stderr)
            return 2
        from cab.pipeline import run_on_directory

        print("Analysis complete.")
        _print_summary(run_on_directory(args[1]))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
