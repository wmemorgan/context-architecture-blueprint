# SPDX-License-Identifier: MIT
"""No-retention core (process source ephemerally; persist only derived scores).

The guarantee: source documents are processed **ephemerally** and discarded.
Only the *derived* report (scores, band, bounded findings, manifest) persists,
keyed to a report URL — never source bytes, and never source-derived text in
logs, traces, error payloads, backups, or provider telemetry.

The no-retention guarantee extends beyond the filesystem to every side-channel. We model
those side-channels as an explicit `Sinks` registry that the whole pipeline
writes through, so a canary probe can assert no source text reached any of them.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

# The full no-retention scope. Each is a side-channel a canary must not reach.
NO_RETENTION_SCOPE = (
    "source-files",
    "derived-text",
    "logs",
    "traces",
    "error-payloads",
    "backups",
    "provider-telemetry",
)


@dataclass
class Sinks:
    """Every output side-channel the pipeline may write to, captured for auditing.

    The pipeline writes *only* derived, non-source content here. The canary probe
    treats any source text appearing in these as a retention leak (fails CI/deploy).
    """

    logs: list[str] = field(default_factory=list)
    traces: list[str] = field(default_factory=list)
    error_payloads: list[str] = field(default_factory=list)
    backups: dict[str, Any] = field(default_factory=dict)
    provider_telemetry: list[str] = field(default_factory=list)

    def log(self, msg: str) -> None:
        self.logs.append(msg)

    def trace(self, msg: str) -> None:
        self.traces.append(msg)

    def error(self, msg: str) -> None:
        self.error_payloads.append(msg)

    def telemetry(self, msg: str) -> None:
        self.provider_telemetry.append(msg)

    def all_strings(self) -> list[str]:
        out: list[str] = []
        out += self.logs + self.traces + self.error_payloads + self.provider_telemetry
        out += [str(v) for v in self.backups.values()]
        return out


class EphemeralWorkspace:
    """A scratch directory that is shredded on exit — no source bytes survive.

    Usage:
        with EphemeralWorkspace() as ws:
            ... write/parse source files under ws.path ...
        # ws.path no longer exists; source bytes are gone.
    """

    def __init__(self) -> None:
        self.path: str = ""

    def __enter__(self) -> EphemeralWorkspace:
        self.path = tempfile.mkdtemp(prefix="cab-ephemeral-")
        return self

    def __exit__(self, *exc: Any) -> None:
        self.shred()

    def shred(self) -> None:
        if self.path and os.path.isdir(self.path):
            # Overwrite then remove, so source bytes are not merely unlinked.
            for root, _dirs, files in os.walk(self.path):
                for fn in files:
                    fp = os.path.join(root, fn)
                    try:
                        size = os.path.getsize(fp)
                        with open(fp, "wb") as fh:
                            fh.write(b"\x00" * size)
                    except OSError:
                        pass
            shutil.rmtree(self.path, ignore_errors=True)
        self.path = ""


class RetentionStore:
    """Persists ONLY derived reports keyed to a report URL.

    Defensive: refuses obvious source-carrying keys ('raw', 'raw_bytes',
    'source_text', 'text') at the top level of a persisted report.
    """

    _FORBIDDEN_KEYS = {"raw", "raw_bytes", "source_text", "text", "source_bytes"}

    def __init__(self) -> None:
        self._db: dict[str, dict] = {}

    def persist(self, report_url: str, derived_report: dict) -> None:
        bad = self._FORBIDDEN_KEYS & set(derived_report)
        if bad:
            raise ValueError(f"refusing to persist source-carrying keys: {sorted(bad)}")
        self._db[report_url] = derived_report

    def get(self, report_url: str) -> dict | None:
        return self._db.get(report_url)

    def all_persisted_strings(self) -> list[str]:
        return [_flatten(v) for v in self._db.values()]


def _flatten(obj: Any) -> str:
    return repr(obj)


def scan_for_leak(
    canary: str,
    *,
    sinks: Sinks,
    store: RetentionStore,
    workspace: EphemeralWorkspace | None = None,
    extra: Iterable[str] = (),
) -> list[str]:
    """Return a list of side-channels where the canary leaked (empty == clean)."""
    leaks: list[str] = []
    for label, blob in (
        ("logs", "\n".join(sinks.logs)),
        ("traces", "\n".join(sinks.traces)),
        ("error-payloads", "\n".join(sinks.error_payloads)),
        ("provider-telemetry", "\n".join(sinks.provider_telemetry)),
        ("backups", "\n".join(str(v) for v in sinks.backups.values())),
    ):
        if canary in blob:
            leaks.append(label)
    if any(canary in s for s in store.all_persisted_strings()):
        leaks.append("derived-text")
    if workspace and workspace.path and os.path.isdir(workspace.path):
        # Workspace should be shredded; if it exists and holds the canary, that's a leak.
        for root, _dirs, files in os.walk(workspace.path):
            for fn in files:
                try:
                    with open(os.path.join(root, fn), errors="ignore") as fh:
                        if canary in fh.read():
                            leaks.append("source-files")
                            break
                except OSError:
                    pass
    for s in extra:
        if canary in s:
            leaks.append("extra")
    return leaks
