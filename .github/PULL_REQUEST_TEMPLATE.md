<!-- SPDX-License-Identifier: MIT -->
## Summary

What does this change and why?

## Type of change

- [ ] Bug fix
- [ ] New feature (check, judge adapter, ...)
- [ ] Documentation
- [ ] Refactor / internal

## Checklist

- [ ] The full local gate is green: `black --check`, `ruff check`, `mypy`, `pytest -q`, and the
      reference-service example tests.
- [ ] Tests added/updated for the change.
- [ ] Public API is type-hinted and docstringed; new files carry the `SPDX-License-Identifier: MIT`
      header.
- [ ] The core stays deployment-neutral and provider-agnostic (the structural guard passes).
- [ ] Docs and `CHANGELOG.md` updated where behavior or the public API changed.
