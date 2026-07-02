# SPDX-License-Identifier: MIT
"""Upload caps — per-file size, total size, and file-count limits.

Stated on the upload surface and enforced server-side. These are the first line
of the cost-DoS defense (see cab.cost.limits and cab.ingestion.security).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Caps:
    max_files: int = 25
    max_file_bytes: int = 10 * 1024 * 1024  # 10 MB per file
    max_total_bytes: int = 50 * 1024 * 1024  # 50 MB per submission


class CapExceeded(ValueError):
    """An upload exceeded a stated cap; the submission is rejected (not processed)."""


def enforce(files: list[tuple[str, bytes]], caps: Caps = Caps()) -> None:
    """Raise CapExceeded if `files` (name, bytes) violates any cap."""
    if len(files) > caps.max_files:
        raise CapExceeded(f"too many files: {len(files)} > {caps.max_files}")
    total = 0
    for name, data in files:
        n = len(data)
        total += n
        if n > caps.max_file_bytes:
            raise CapExceeded(f"file '{name}' is {n} bytes > per-file cap {caps.max_file_bytes}")
    if total > caps.max_total_bytes:
        raise CapExceeded(f"submission total {total} bytes > total cap {caps.max_total_bytes}")
