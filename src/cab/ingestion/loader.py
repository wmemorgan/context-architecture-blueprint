# SPDX-License-Identifier: MIT
"""Turn raw (name, bytes) inputs into a normalized Corpus.

Used by the upload path, the demo loader, and local directory analysis. Caps are
enforced before parsing; security hardening (cab.ingestion.security) wraps this
for the untrusted upload path.
"""

from __future__ import annotations

import os

from cab.ingestion.caps import Caps, enforce
from cab.ingestion.parsers import ParserUnavailable, parse
from cab.models import Corpus, Document


def ingest_files(
    files: list[tuple[str, bytes]], *, source: str, caps: Caps = Caps(), enforce_caps: bool = True
) -> Corpus:
    """Parse a list of (filename, bytes) into a Corpus. Raises CapExceeded on caps."""
    if enforce_caps:
        enforce(files, caps)
    docs: list[Document] = []
    for name, data in files:
        try:
            docs.append(parse(name, data))
        except ParserUnavailable as exc:
            docs.append(
                Document(
                    name=name,
                    ext=name.rsplit(".", 1)[-1].lower(),
                    text="",
                    raw_bytes_len=len(data),
                    parsed_ok=False,
                    notes=[f"parser unavailable: {exc}"],
                )
            )
    return Corpus(documents=docs, source=source)


def ingest_directory(path: str, *, source: str | None = None, enforce_caps: bool = False) -> Corpus:
    """Read every supported file under a directory into a Corpus (local, no upload)."""
    from cab.ingestion.parsers import SUPPORTED_EXTS

    files: list[tuple[str, bytes]] = []
    for root, _dirs, names in sorted(os.walk(path)):
        for fn in sorted(names):
            ext = fn.rsplit(".", 1)[-1].lower() if "." in fn else ""
            if ext in SUPPORTED_EXTS:
                with open(os.path.join(root, fn), "rb") as fh:
                    files.append((fn, fh.read()))
    return ingest_files(files, source=source or f"dir:{path}", enforce_caps=enforce_caps)
