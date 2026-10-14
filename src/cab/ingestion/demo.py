# SPDX-License-Identifier: MIT
"""Demo-mode loader — runs the full analysis over a bundled sample corpus with
**no upload**. The sample corpus lives in corpora/demo/ and ships with
the repo, so the artifact is clickable for a reviewer with zero friction.
"""

from __future__ import annotations

import os

from cab.ingestion.loader import ingest_directory
from cab.models import Corpus


def demo_corpus_path() -> str:
    # repo_root/corpora/demo  (this file is src/cab/ingestion/demo.py)
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    return os.path.join(root, "corpora", "demo")


def load_demo_corpus() -> Corpus:
    """Load the bundled sample corpus from disk — no upload, no network."""
    path = demo_corpus_path()
    if not os.path.isdir(path):
        raise FileNotFoundError(f"bundled demo corpus missing at {path}")
    corpus = ingest_directory(path, source="demo")
    if len(corpus) == 0:
        raise FileNotFoundError(f"demo corpus at {path} contains no documents")
    return corpus
