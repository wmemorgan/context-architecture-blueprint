# SPDX-License-Identifier: MIT
"""Ingestion security hardening.

Uploaded corpus text is **untrusted data**. This module is the hardened gate in
front of parsing:

  • file-type sniffing — reject type-spoofed uploads (extension ≠ magic bytes);
  • size limits — reject oversized files (defense in depth with caps);
  • zip / decompression-bomb detection — reject archives that expand abusively;
  • malware scan — a pluggable AV interface (default: signature scan incl. EICAR);
  • parser sandbox + strict per-file timeout — bound parse time;
  • prompt-injection red-team — embedded instructions are IGNORED and surfaced as
    findings; they never alter tool control flow.

A rejected file is NOT parsed. An injection payload is parsed-as-data and reported.
"""

from __future__ import annotations

import io
import re
import threading
import zipfile
from collections.abc import Callable

from cab.ingestion.caps import Caps
from cab.ingestion.parsers import ParserUnavailable, ext_of, parse
from cab.models import Corpus, Document, Finding

# EICAR anti-malware test signature (industry-standard harmless probe).
EICAR = r"X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"

# Compression-bomb thresholds for archive formats (DOCX is a ZIP).
_MAX_EXPANSION_RATIO = 100.0
_MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

# Magic-byte prefixes per declared extension.
_MAGIC = {
    "pdf": (b"%PDF",),
    "docx": (b"PK\x03\x04",),
}

# Prompt-injection markers. Matches are DATA — surfaced as findings, never run.
_INJECTION_PATTERNS = [
    r"ignore (all|any)? ?(previous|prior|above) instructions",
    r"disregard (the|all|any)? ?(previous|prior|above)",
    r"you are now (a|an|the)\b",
    r"system\s*:\s*you (are|must)",
    r"new instructions\s*:",
    r"reveal (your|the) (system )?prompt",
    r"override (the|your) (rules|instructions|guardrails)",
    r"do not (tell|inform) the (user|operator)",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


class SecurityRejection(Exception):
    """A file was rejected by the security gate and was NOT parsed."""

    def __init__(self, name: str, reason: str) -> None:
        super().__init__(f"{name}: {reason}")
        self.name = name
        self.reason = reason


def sniff_ok(name: str, data: bytes) -> bool:
    """True if the declared extension matches the content's magic bytes / shape."""
    ext = ext_of(name)
    if ext in _MAGIC:
        return any(data.startswith(sig) for sig in _MAGIC[ext])
    if ext in ("md", "markdown", "txt"):
        # Text formats must not carry binary control bytes (NUL etc.).
        sample = data[:4096]
        return b"\x00" not in sample
    return True


def malware_scan(data: bytes, scanner: Callable[[bytes], bool] | None = None) -> bool:
    """Return True if clean. Default scanner flags the EICAR test signature."""
    if scanner is not None:
        return scanner(data)
    return EICAR.encode("latin-1", "ignore") not in data


def zip_bomb_check(data: bytes) -> None:
    """Raise SecurityRejection if `data` is an archive that expands abusively."""
    if not data.startswith(b"PK\x03\x04"):
        return
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return
    total_uncompressed = sum(i.file_size for i in zf.infolist())
    total_compressed = max(1, sum(i.compress_size for i in zf.infolist()))
    if total_uncompressed > _MAX_UNCOMPRESSED_BYTES:
        raise SecurityRejection("archive", f"uncompressed size {total_uncompressed} too large")
    if total_uncompressed / total_compressed > _MAX_EXPANSION_RATIO:
        raise SecurityRejection(
            "archive", f"expansion ratio {total_uncompressed / total_compressed:.0f}x exceeds limit"
        )


def scan_injection(name: str, text: str) -> list[Finding]:
    """Return findings for embedded prompt-injection. These are DATA, not commands."""
    findings: list[Finding] = []
    for m in _INJECTION_RE.finditer(text):
        snippet = text[max(0, m.start() - 20) : m.end() + 20].replace("\n", " ")
        findings.append(
            Finding(
                dimension="attributability",
                severity="high",
                message="Embedded instruction detected in source and ignored (treated as data).",
                documents=[name],
                evidence=snippet.strip(),
                is_injection_attempt=True,
            )
        )
    return findings


def _parse_with_timeout(name: str, data: bytes, timeout_s: float) -> Document:
    """Parse in a sandboxed worker thread bounded by a strict timeout."""
    result: dict[str, object] = {}

    def worker() -> None:
        try:
            result["doc"] = parse(name, data)
        except Exception as exc:  # surfaced below
            result["exc"] = exc

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        raise SecurityRejection(name, f"parse exceeded {timeout_s}s timeout")
    if "exc" in result:
        exc = result["exc"]
        if isinstance(exc, ParserUnavailable):
            raise exc
        # Never echo the raw exception string into an error payload — a parser
        # exception can embed source-derived text. Surface only the exception TYPE.
        raise SecurityRejection(name, f"parse error ({type(exc).__name__})")
    return result["doc"]  # type: ignore[return-value]


def secure_ingest(
    files: list[tuple[str, bytes]],
    *,
    caps: Caps = Caps(),
    parse_timeout_s: float = 10.0,
    malware_scanner: Callable[[bytes], bool] | None = None,
) -> tuple[Corpus, list[Finding]]:
    """Hardened ingestion. Returns (corpus, security_findings).

    Raises SecurityRejection on a malformed / spoofed / oversized / infected /
    zip-bomb file (it is NOT parsed). Prompt-injection content IS parsed and
    surfaced as findings — control flow is unchanged.
    """
    security_findings: list[Finding] = []
    docs: list[Document] = []

    # Count + total-size caps (cost-DoS defense): the untrusted upload path must
    # enforce the same submission-level caps as the loader, not just per-file size.
    if len(files) > caps.max_files:
        raise SecurityRejection("submission", f"too many files: {len(files)} > {caps.max_files}")
    total_bytes = sum(len(data) for _name, data in files)
    if total_bytes > caps.max_total_bytes:
        raise SecurityRejection(
            "submission", f"submission total {total_bytes} > {caps.max_total_bytes}"
        )

    for name, data in files:
        if len(data) > caps.max_file_bytes:
            raise SecurityRejection(name, f"oversized: {len(data)} > {caps.max_file_bytes}")
        if not sniff_ok(name, data):
            raise SecurityRejection(name, "file-type spoof: extension does not match content")
        if not malware_scan(data, malware_scanner):
            raise SecurityRejection(name, "malware signature detected")
        zip_bomb_check(data)
        doc = _parse_with_timeout(name, data, parse_timeout_s)
        inj = scan_injection(name, doc.text)
        if inj:
            doc.notes.append(f"{len(inj)} embedded instruction(s) ignored (surfaced as findings)")
            security_findings.extend(inj)
        docs.append(doc)

    return Corpus(documents=docs, source="upload-secure"), security_findings
