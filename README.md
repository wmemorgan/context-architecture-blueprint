<!-- SPDX-License-Identifier: MIT -->
# The Context Architecture Blueprint

> **Know what your AI can actually understand.**

The working instrument of **The Comprehension Standard** — the authored bar for whether a
knowledge corpus is ready for AI.

[![CI](https://github.com/wmemorgan/context-architecture-blueprint/actions/workflows/ci.yml/badge.svg)](https://github.com/wmemorgan/context-architecture-blueprint/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-134-brightgreen.svg)](#development--testing)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Lint: ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://github.com/astral-sh/ruff)

**The Comprehension Standard** asks a single, concrete question: *can an AI system comprehend
this corpus well enough to answer from it without making things up?* The Context Architecture
Blueprint is the runnable diagnostic you point at your own knowledge corpus.

## What this is

The Context Architecture Blueprint audits the readiness of your document corpus for AI systems
— RAG pipelines, agents, and any workflow whose quality depends on what the model can actually
comprehend. Rather than checking formatting or counting tokens, it applies a diagnostic
standard: it detects contradictions *across* documents, catches terminology that drifts between
sources, and grades your corpus against the Comprehension Standard — seven measured dimensions banded L1–L5 — then
tells you, in priority order, what to fix first. It runs locally against your own content, uses
a pluggable LLM judge (bring your own key), and produces a corpus-specific readiness manifest as
its primary deliverable.

You give it a sample of your own knowledge corpus; it returns:

1. **A corpus-specific Blueprint Manifest** — *the hero deliverable.* A buildable metadata
   schema, chunking approach, versioning policy, and glossary scaffold derived from **your**
   documents, not a template. This is the thing you take away and build from.
2. **A Context Readiness report** — a radar across the scored dimensions, an L1–L5 band,
   per-document findings, and prioritized remediation, rendered uncertainty-forward (structural
   readiness is **advisory** — never a guarantee your retrieval system will work).

## Quickstart

```bash
pip install -r requirements.txt
# Run the full analysis over the bundled sample corpus (no upload, no key):
python -m cab.cli demo
# Analyze your own folder of documents:
python -m cab.cli analyze ./my-corpus
```

`demo` runs in under a minute against the bundled sample corpus and prints the band plus the
report URL. With no API key present it uses the deterministic mock judge (see
[calibration provenance](#calibration-provenance) below).

## The L1–L5 Context Readiness bands

| Band | Name | What it means |
|------|------|---------------|
| **L1** | Raw | Documents exist but are not structured for machine comprehension. High contradiction / provenance risk. |
| **L2** | Organized | Consistent structure and extractable text, but metadata, provenance, and freshness are thin. |
| **L3** | Governed | Metadata and provenance present; cross-document consistency mostly holds; some terminology drift. |
| **L4** | Attributable | Claims are traceable to sources; contradictions are rare and surfaced; terminology is controlled. |
| **L5** | AI-Ready | The corpus is comprehensible, attributable, fresh, and internally consistent — ready to build retrieval on. |

> The band is **advisory**. It describes *structural* readiness. It does not certify that any
> particular retrieval or agent system built on the corpus will behave correctly.

## The seven dimensions

The Standard scores a corpus across seven dimensions. **Cross-Document Consistency** and
**Attributability** carry the heaviest weight — they are where corpora produce *confident-wrong*
answers in production, and they are the hardest to fix after the fact.

1. **Extractability & Structure** — can the text be cleanly extracted and is it sectioned?
2. **Metadata & Provenance** — are title/author/date/source present and trustworthy?
3. **Freshness & Versioning** — is the corpus current, dated, and versioned?
4. **Cross-Document Consistency** *(heaviest)* — do documents contradict each other?
5. **Attributability** *(heaviest)* — can a claim be traced to a specific source?
6. **Redundancy & Uniqueness** — is the corpus free of near-duplicate noise?
7. **Terminology Consistency** — is the same concept named the same way throughout?

See the [user guide](docs/user-guide.md) for how to read a manifest and interpret each
dimension and band.

## How analysis works (hybrid)

Each dimension is scored with a **hybrid** of *deterministic checks* (reliable, reproducible —
format detection, metadata-field presence, staleness, near-duplicate clustering, structure
heuristics, term-variant clustering) and an *LLM judge* (semantic judgment — cross-document
contradiction, attributability, terminology drift, the readiness narrative). The judge runs at
temperature 0.0, **dual-run**, with a defined disagreement-arbitration rule, so an identical
corpus replays to an identical band.

The scoring contract is **locked and reproducible**: explicit per-dimension formulas, fixed
default weights with minimum deltas, explicit L1–L5 cut-lines. See
[`config/scoring_contract.yaml`](config/scoring_contract.yaml).

## The LLM judge (bring your own key)

The three semantic dimensions are scored by a **pluggable LLM judge** behind a small port. Two
adapters ship in the box, and you can add your own:

- **`MockJudge`** (default) — deterministic, no key, no network. The full test suite and the
  `demo` command run on it.
- **`ClaudeJudge`** — the reference judge (Claude), used automatically when an `ANTHROPIC_API_KEY`
  is present in the environment. The model is configurable: pass `ClaudeJudge(model=...)`, or set
  `CAB_JUDGE_MODEL` to pin any model you have access to (explicit argument wins over the env var,
  which wins over the shipped default).
- **Your own adapter** — implement one method (`run(corpus) -> JudgePass`) to target any
  OpenAI-compatible or other provider. See the
  [developer guide](docs/developer-guide.md#adding-a-judge-adapter).

Bring your own key and provider; the engine ships none.

### Capability floor

The three semantic dimensions **ride on the judge model's comprehension**. A capable,
instruction-following frontier model is required to reliably detect a paraphrased cross-document
contradiction or a drifted term. **Below that capability floor** — small, heavily quantized, or
non-instruction-tuned models — the semantic judgments become unreliable and can silently miss
real defects or invent spurious ones. The deterministic dimensions are unaffected (they run
without a model), but the overall band should not be trusted when the judge sits below the
floor. The reference judge is Claude; other capable OpenAI-compatible frontier models are
reasonable, subject to the calibration note below.

### Calibration provenance

The L1–L5 band thresholds were **calibrated and validated against the reference Claude judge**.
A run on any other judge carries **unverified calibration** — the bands are indicative, and you
should run per-provider calibration before relying on the thresholds. The engine makes this
explicit: every report carries a `calibration` label, and the CLI prints it. Non-reference runs
are surfaced as **"community / unverified calibration"** (or, for the deterministic mock,
"not calibrated — illustrative"). See the
[provider & adapter reference](docs/provider-reference.md).

## Privacy & retention (self-hosted)

This engine parses documents in memory and discards them — it does not store source files, and
source text is kept out of logs, traces, and error payloads. Findings and the Blueprint Manifest
are derived analysis that reference documents by name and may quote short, capped spans to make a
finding legible.

**You are the operator.** Retention of the derived report is **configurable** (and can be
disabled entirely); the default is a short, conservative window — set it to match your
environment. Your choice of LLM provider and key is yours (the judge is a pluggable port), and
any disclosures to your users are yours to make. See
[`config/privacy.yaml`](config/privacy.yaml).

## Running the framework

The Context Architecture Blueprint ships as a **Python library and CLI** — that is the supported core.

- **CLI** — `python -m cab.cli demo` runs the bundled sample corpus; `python -m cab.cli analyze <dir>` runs your own folder.
- **Library** — call `cab.pipeline.run_on_files()` / `run_on_corpus()` from your own application and render with `build_render_contract()` or your own UI.

**Deployment is yours.** The framework makes no deployment assumptions and ships no hosting opinion. How you run it — batch, internal service, air-gapped, container, serverless — is your decision and your security and compliance posture to own.

A **reference HTTP service** (upload → analyze → report) is included under
[`examples/reference-service/`](examples/reference-service/) as an **unsupported example** of one way to wrap the library behind an upload surface. It is illustrative, not a product: you supply authentication, durable storage, secrets management, network controls, and any data-retention policy appropriate to your environment.

## Architecture overview

The engine is **ports & adapters** with the dependency rule pointing inward:

- **Core domain** (ingestion, deterministic checks, scoring/banding, manifest generation) depends
  on nothing outward — no provider SDK, no web framework, no deployment concern.
- **The judge is a port.** `MockJudge`, `ClaudeJudge`, and any adapter you add plug in behind it;
  no provider-specific type or string lives in the core.
- **The CLI is a thin adapter** over the library; the library never imports the CLI.
- **Deployment lives only in `examples/`.** The reference HTTP service is a self-contained,
  unsupported consumer of the library — the core is deployment-neutral.

A structural CI guard fails the build if a provider SDK is imported into the core or a deployment
artifact appears outside `examples/`. See the [developer guide](docs/developer-guide.md).

## Development & testing

The full test suite is **hermetic** — it runs with a deterministic `MockJudge` and needs no API
key or network: **134 tests** (122 engine-core + 12 reference-service), of which 5 live-judge
tests skip unless `ANTHROPIC_API_KEY` is present.

```bash
pip install -r requirements-dev.txt
pytest -q                          # hermetic run (mock judge)
pytest examples/reference-service/tests -q
```

Quality gates (all enforced in CI): `black`, `ruff`, `mypy`, the test suite, and the structural
architecture guard.

```bash
black --check src tests examples
ruff check src tests examples
mypy
```

If you have a key exported but want a deterministic, offline run, set `CAB_FORCE_MOCK_JUDGE=1`.

## Documentation

- [User guide](docs/user-guide.md) — install, run, read a manifest, interpret the bands and dimensions.
- [Developer guide](docs/developer-guide.md) — architecture, adding a judge adapter, running tests, the dependency rules.
- [Provider & adapter reference](docs/provider-reference.md) — BYO key, the capability floor, calibration provenance.
- [Contributing](CONTRIBUTING.md) · [Code of Conduct](CODE_OF_CONDUCT.md) · [Security policy](SECURITY.md) · [Changelog](CHANGELOG.md)

## Built on / Cites

The Comprehension Standard is the authored bar; it rests on, and cites, established public
foundations. These are *citations*, not the headline:

- **Context Engineering** — the practice of structuring inputs for LLM comprehension.
- **RAG evaluation vocabulary** — RAGAS, DeepEval, LangSmith (faithfulness, answer-relevance,
  context-precision/recall).
- **DAMA-DMBOK** — data-quality dimensions (completeness, consistency, timeliness, uniqueness).
- **Dublin Core / schema.org** — metadata vocabularies for provenance.
- **W3C PROV / C2PA** — provenance and content authenticity.
- **LangChain / LlamaIndex / GraphRAG** — chunking and retrieval patterns informing the
  Blueprint Manifest's recommendations.

## Authorship & license

Created and authored by **Wilfred Morgan**. © 2026 Wilfred Morgan.

Released under the [MIT License](LICENSE).
