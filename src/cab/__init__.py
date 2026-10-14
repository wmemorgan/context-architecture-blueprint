# SPDX-License-Identifier: MIT
"""The Context Architecture Blueprint — a working instrument of The Comprehension Standard.

Scores how AI-ready a knowledge corpus is across seven dimensions and emits a
corpus-specific Blueprint Manifest (the hero deliverable) plus a Context Readiness
report. Clean-room build; public framework canon only.
"""

__version__ = "0.1.0"

# The seven dimensions of The Comprehension Standard. Cross-Document Consistency
# and Attributability carry the heaviest weight (see cab.scoring.contract).
DIMENSIONS = (
    "extractability_structure",
    "metadata_provenance",
    "freshness_versioning",
    "cross_document_consistency",
    "attributability",
    "redundancy_uniqueness",
    "terminology_consistency",
)

BANDS = ("L1", "L2", "L3", "L4", "L5")
