# SPDX-License-Identifier: MIT
"""Demo-mode loader — runs the full analysis over a bundled sample corpus with
**no upload**. The sample corpus lives in corpora/demo/ and ships with
the repo and inside the installed package, so the demo runs with zero setup.
"""

from __future__ import annotations

import os

from cab._bundled import demo_corpus_dir
from cab.ingestion.loader import ingest_directory
from cab.models import Corpus


def demo_corpus_path() -> str:
    return demo_corpus_dir()


def load_demo_corpus() -> Corpus:
    """Load the bundled sample corpus from disk — no upload, no network."""
    path = demo_corpus_path()
    if not os.path.isdir(path):
        raise FileNotFoundError(f"bundled demo corpus missing at {path}")
    corpus = ingest_directory(path, source="demo")
    if len(corpus) == 0:
        raise FileNotFoundError(f"demo corpus at {path} contains no documents")
    return corpus
