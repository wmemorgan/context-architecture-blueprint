<!-- SPDX-License-Identifier: MIT -->
# User guide

This guide walks you from install to reading a Blueprint Manifest and interpreting a Context
Readiness band. If you just want to run it, see the [Quickstart](../README.md#quickstart).

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The core engine is dependency-light and needs no API key. The three semantic dimensions use a
pluggable LLM judge; with no key present the engine uses a deterministic mock judge (see
[Calibration provenance](#calibration-provenance)).

## Run

Two entry points, one library:

```bash
# Bundled sample corpus — the fastest way to see a full run:
python -m cab.cli demo

# Your own folder of documents (Markdown, text, and — with optional parsers — PDF/DOCX):
python -m cab.cli analyze ./my-corpus
```

Or call the library directly:

```python
from cab.pipeline import run_on_directory

report = run_on_directory("./my-corpus")
print(report["band"], report["overall_score"])
print(report["calibration"]["label"])       # calibration provenance
manifest = report["manifest"]                # the hero deliverable
```

## Read the Blueprint Manifest (the hero deliverable)

The manifest is the thing you take away and build from. It is derived entirely from **your**
documents — never a template. It contains:

| Section | What it gives you |
|---------|-------------------|
| `summary` | A one-paragraph readout centered on your own top vocabulary and band. |
| `metadata_schema` | Per-field presence rates (title/author/date/source/version) with Dublin-Core-aligned recommendations for the gaps. |
| `chunking` | A corpus-responsive chunking strategy sized to your documents' real length distribution and measured header ratio — not a fixed default. |
| `versioning` | A versioning/freshness policy based on how many of your documents already carry versions and dates. |
| `glossary` | A glossary scaffold built from the terms that actually appear, plus any terminology drift to resolve. |
| `remediation_priorities` | The weakest dimensions first, each with a concrete, buildable action. |

## Interpret the L1–L5 band

The band is the corpus-level readout of comprehension readiness. It is **advisory**: it
describes *structural* readiness, not the behavior of any retrieval or agent system you build on
the corpus.

| Band | Name | Read it as |
|------|------|-----------|
| **L1** | Raw | Not structured for machine comprehension; high contradiction/provenance risk. |
| **L2** | Organized | Structured and extractable, but metadata/provenance/freshness are thin. |
| **L3** | Governed | Metadata present; cross-document consistency mostly holds; some drift. |
| **L4** | Attributable | Claims traceable; contradictions rare and surfaced; terminology controlled. |
| **L5** | AI-Ready | Comprehensible, attributable, fresh, and internally consistent. |

The band is computed from a weighted average of the dimension scores against fixed cut-lines
(L5 ≥ 85, L4 ≥ 70, L3 ≥ 55, L2 ≥ 40, else L1). The exact formulas, weights, and cut-lines live
in [`config/scoring_contract.yaml`](../config/scoring_contract.yaml) and are locked so an
identical corpus always replays to an identical band.

## The comprehension dimensions

The Standard grades a corpus across seven scored dimensions. Two of them —
**Cross-Document Consistency** and **Attributability** — carry the heaviest weight because they
are where a corpus produces *confident-wrong* answers in production:

| Dimension | Weight | What it asks |
|-----------|-------:|--------------|
| Cross-Document Consistency *(heaviest)* | 0.22 | Do documents contradict each other? |
| Attributability *(heaviest)* | 0.22 | Can a claim be traced to a specific source? |
| Extractability & Structure | 0.12 | Can text be cleanly extracted, and is it sectioned? |
| Metadata & Provenance | 0.12 | Are title/author/date/source present and trustworthy? |
| Freshness & Versioning | 0.11 | Is the corpus current, dated, and versioned? |
| Terminology Consistency | 0.11 | Is the same concept named the same way throughout? |
| Redundancy & Uniqueness | 0.10 | Is the corpus free of near-duplicate noise? |

Each dimension is scored by a hybrid of deterministic checks and the LLM judge; both contribute,
and the judge runs dual-run at temperature 0.0 so results are reproducible.

## Calibration provenance

Every report carries a `calibration` label describing how much to trust the band:

- **Reference calibration** — the run used the reference Claude judge; band thresholds were
  validated against it.
- **Community / unverified calibration** — the run used another provider adapter; treat the band
  as indicative and run per-provider calibration before relying on the thresholds.
- **Not calibrated (illustrative)** — the run used the deterministic mock judge (no key); useful
  for smoke-testing and offline demos, not for a verdict.

The `demo` command with no key prints the "not calibrated" label; that is expected. See the
[provider & adapter reference](provider-reference.md) for details and the capability floor.

## Privacy

The engine parses documents in memory and discards them; it stores no source files and keeps
source text out of logs and traces. Retention of the derived report is configurable (and can be
disabled). You are the operator — see [`config/privacy.yaml`](../config/privacy.yaml).
