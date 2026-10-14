<!-- SPDX-License-Identifier: MIT -->
# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — Initial public release

### Added

- The Context Architecture Blueprint engine: a hybrid (deterministic + LLM-judge) diagnostic that
  scores a document corpus across seven comprehension dimensions and lands it on an L1–L5 Context
  Readiness band.
- The corpus-specific **Blueprint Manifest** — a buildable metadata schema, corpus-responsive
  chunking recommendation, versioning policy, and glossary scaffold derived from your documents.
- Pluggable **LLM judge** port with two shipped adapters: a deterministic `MockJudge` (default,
  no key) and a reference `ClaudeJudge` (bring your own key).
- `python -m cab.cli` with `demo` and `analyze` commands; a library API
  (`run_on_files`, `run_on_corpus`, `run_on_directory`, `build_render_contract`).
- Locked, reproducible scoring contract (`config/scoring_contract.yaml`) and a configurable,
  policy-neutral privacy/retention contract (`config/privacy.yaml`).
- **Capability-floor** and **calibration-provenance** labeling: every report records which judge
  produced it, and non-reference runs are surfaced as "community / unverified calibration".
- A reference HTTP service under `examples/reference-service/` as an unsupported, deployment-neutral
  example of wrapping the library behind an upload surface.
- Hermetic test suite (134 tests) and a structural clean-architecture guard enforced in CI, along
  with `black`, `ruff`, and `mypy` gates.

[0.1.0]: https://github.com/wmemorgan/context-architecture-blueprint/releases/tag/v0.1.0
