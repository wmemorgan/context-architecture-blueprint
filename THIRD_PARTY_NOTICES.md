<!-- SPDX-License-Identifier: MIT -->
# Third-party notices

The Context Architecture Blueprint depends on the following third-party packages. All are under
permissive, MIT-compatible licenses; there are **no copyleft (GPL/AGPL/LGPL) runtime
dependencies**. Each package remains under its own license and copyright.

## Runtime dependencies (core)

| Package | License |
|---------|---------|
| pydantic | MIT |
| PyYAML | MIT |
| httpx | BSD-3-Clause |

## Optional, lazy-imported (document parsers)

| Package | License |
|---------|---------|
| pypdf | BSD-3-Clause |
| python-docx | MIT |

## Reference-service example only (not part of the core)

| Package | License |
|---------|---------|
| starlette | BSD-3-Clause |
| uvicorn | BSD-3-Clause |

## Development / CI

| Package | License |
|---------|---------|
| pytest | MIT |
| ruff | MIT |
| black | MIT |
| mypy | MIT |

## LLM provider clients

The reference judge uses the `anthropic` SDK (MIT), which is **lazy-imported only when a live
judge is selected** and is not a hard dependency of the engine. Provider clients you add for your
own judge adapter remain under their own licenses.

---

*Licenses were verified against installed package metadata. If you redistribute this software with
any of these dependencies bundled, retain their respective license and copyright notices.*
