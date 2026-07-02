<!-- SPDX-License-Identifier: MIT -->
# Contributing

Thanks for your interest in the Context Architecture Blueprint. Contributions of all kinds —
bug reports, docs, judge adapters, and features — are welcome.

## Ground rules

- Be respectful. This project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- Keep the core **deployment-neutral and provider-agnostic** (see the
  [architecture overview](docs/developer-guide.md#architecture-ports--adapters)). Provider and
  deployment concerns belong in an adapter or under `examples/`, never in the core.
- By contributing, you agree your contributions are licensed under the project's
  [MIT License](LICENSE).

## Development setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

## Before you open a pull request

Run the full local gate — CI runs the same checks and will block on any of them:

```bash
black --check src tests examples     # formatting (line length 100)
ruff check src tests examples        # linting
mypy                                  # typing
pytest -q                             # hermetic engine suite (no key needed)
pytest examples/reference-service/tests -q
```

Then:

- Add or update tests for any behavior change. Tests should read as documentation.
- Keep every shipped source file's `SPDX-License-Identifier: MIT` header intact, and add one to
  any new file.
- Type-hint and docstring any new public API (purpose / args / returns).
- No dead code, and no `TODO`/`FIXME` in shipped source.
- Update the docs and the [CHANGELOG](CHANGELOG.md) when behavior or the public API changes.

## Pull-request workflow

1. Fork and branch from `main`.
2. Make focused commits with clear messages.
3. Ensure the full local gate is green.
4. Open a PR describing the change and its motivation; fill in the PR template.
5. A maintainer reviews; CI must be green to merge.

## Adding a judge adapter

Targeting another LLM provider is a first-class contribution. See
[Adding a judge adapter](docs/developer-guide.md#adding-a-judge-adapter). Please include a note on
calibration provenance for the provider (see the
[provider reference](docs/provider-reference.md#calibration-provenance)).
