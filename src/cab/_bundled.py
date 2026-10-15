# SPDX-License-Identifier: MIT
"""Locate the data files that ship with the engine (default config + demo corpus).

The canonical copies live at the repository root (``config/`` and ``corpora/demo/``) so they
are easy to read and edit in a checkout. A wheel install carries the same files inside the
package (``cab/_config/`` and ``cab/_demo/``, mapped in ``pyproject.toml``). Each lookup
prefers the installed copy and falls back to the checkout copy, so the engine finds its
defaults whether it runs from a clone, an editable install, or ``pip install``.
"""

from __future__ import annotations

import os

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_PACKAGE_DIR, "..", ".."))


def _resolve(installed: str, checkout: str) -> str:
    return installed if os.path.exists(installed) else checkout


def config_path(name: str) -> str:
    """Path of a default config file, e.g. ``config_path("privacy.yaml")``."""
    return _resolve(
        os.path.join(_PACKAGE_DIR, "_config", name),
        os.path.join(_REPO_ROOT, "config", name),
    )


def demo_corpus_dir() -> str:
    """Directory of the bundled sample corpus used by ``cab demo``."""
    return _resolve(
        os.path.join(_PACKAGE_DIR, "_demo"),
        os.path.join(_REPO_ROOT, "corpora", "demo"),
    )
