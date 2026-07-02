# SPDX-License-Identifier: MIT
"""Email-capture interface (Brevo pluggable; LITMUS pattern).

The default `LocalEmailSink` records leads in memory so the engine + tests run
with no secrets. A production deployment injects a Brevo-backed implementation
through the same interface. No source-derived content is ever sent — only the
lead email + the report URL.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def valid_email(email: str | None) -> bool:
    return email is not None and bool(_EMAIL_RE.match(email.strip()))


class EmailSink(Protocol):
    def capture(self, email: str, report_url: str) -> None: ...


@dataclass
class LocalEmailSink:
    leads: list[tuple[str, str]] = field(default_factory=list)

    def capture(self, email: str, report_url: str) -> None:
        self.leads.append((email, report_url))


class BrevoEmailSink:  # pragma: no cover - requires a key + network
    """Brevo-backed lead capture (used only when a key is provisioned)."""

    def __init__(self, api_key: str, list_id: int | None = None) -> None:
        self.api_key = api_key
        self.list_id = list_id

    def capture(self, email: str, report_url: str) -> None:
        import httpx

        httpx.post(
            "https://api.brevo.com/v3/contacts",
            headers={"api-key": self.api_key, "content-type": "application/json"},
            json={
                "email": email,
                "attributes": {"REPORT_URL": report_url},
                "listIds": [self.list_id] if self.list_id else [],
            },
            timeout=10.0,
        )


DEFAULT_SINK = LocalEmailSink()
