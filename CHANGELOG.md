<!-- SPDX-License-Identifier: MIT -->
# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.2] — Packaging fix

### Fixed

- `pip install` now installs the runtime dependencies (`pyyaml`, `pydantic`, `httpx`). Before
  this fix, an install from the git URL left them out and `cab` failed on import.
- The default config (`config/`) and the demo corpus (`corpora/demo/`) now ship inside the
  package, so `cab demo` and `cab analyze` work from any directory after `pip install`, not only
  from a clone.
- The Quickstart now installs the package (`pip install -e .`). Before this fix,
  `python -m cab.cli` failed in a fresh clone because the code lives under `src/`.
- `__version__` and `CITATION.cff` now report the release version.

### Added

- A packaging guard test, and a CI job that builds the wheel, installs it into a clean
  environment, and runs `cab demo` and `cab analyze` from outside the repository.

## [0.1.1] — Judge compatibility

### Changed

- The LLM judge now tolerates models that deprecate the `temperature` parameter: when a provider
  rejects the request because `temperature` is no longer accepted, the judge detects that specific
  failure and retries once without the parameter, so a report still completes on newer models.

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
  (`run_on_files`, `run_on_corpus`, `run_on_directory` in `cab.pipeline`;
  `build_render_contract` in `cab.report.render`).
- Locked, reproducible scoring contract (`config/scoring_contract.yaml`) and a configurable,
  policy-neutral privacy/retention contract (`config/privacy.yaml`).
- **Capability-floor** and **calibration-provenance** labeling: every report records which judge
  produced it, and non-reference runs are surfaced as "community / unverified calibration".
- A reference HTTP service under `examples/reference-service/` as an unsupported, deployment-neutral
  example of wrapping the library behind an upload surface.
- Hermetic test suite and a structural clean-architecture guard enforced in CI, along
  with `black`, `ruff`, and `mypy` gates.

[0.1.2]: https://github.com/wmemorgan/context-architecture-blueprint/releases/tag/v0.1.2
[0.1.1]: https://github.com/wmemorgan/context-architecture-blueprint/releases/tag/v0.1.1
[0.1.0]: https://github.com/wmemorgan/context-architecture-blueprint/releases/tag/v0.1.0
