<!-- SPDX-License-Identifier: MIT -->
# Developer guide

## Architecture: ports & adapters

The engine follows a ports-&-adapters (hexagonal) layout with the dependency rule pointing
**inward** — the core domain depends on nothing outward.

```
                 ┌─────────────────────────────────────────┐
   CLI  ───────► │                                         │ ◄─────── reference service
 (adapter)       │   CORE DOMAIN (src/cab)                 │          (examples/, unsupported)
                 │   ingestion · deterministic checks ·    │
                 │   scoring/banding · manifest generator  │
                 │                                         │
   Judge  ◄──────┤   depends on: nothing outward           │
  (a PORT)       │   (no provider SDK, no web framework,   │
   MockJudge     │    no deployment concern)               │
   ClaudeJudge   └─────────────────────────────────────────┘
   your adapter
```

Key rules:

- **The core domain** (`cab.ingestion`, `cab.analysis.deterministic`, `cab.scoring`,
  `cab.manifest`, `cab.pipeline`, `cab.models`) imports no provider SDK, no HTTP framework, and
  no deployment machinery.
- **The judge is a port.** `cab.analysis.judge.Judge` is a `Protocol`. `MockJudge`,
  `ClaudeJudge`, and any adapter you add implement it. Provider knowledge is confined to the
  adapter — no provider-specific type or string appears in the core.
- **The CLI (`cab.cli`) is a thin adapter** over `cab.pipeline`; no library module imports the CLI.
- **Deployment lives only in `examples/`.** The reference HTTP service is a self-contained,
  unsupported consumer of the library. The core ships no `Dockerfile`, compose, or cloud config.

### The structural guard

`tests/test_architecture_guard.py` enforces the rules above in CI. It fails the build if:

1. a provider SDK (`anthropic`, `openai`, …) is imported anywhere in the core **except** the
   single judge adapter;
2. an HTTP/web framework (`starlette`, `fastapi`, `uvicorn`, …) is imported anywhere in the core;
3. a deployment artifact (`Dockerfile`, compose, cloudbuild, …) appears anywhere outside
   `examples/`.

If you add a dependency the architecture forbids, this test — not a reviewer — catches it.

## Repository layout

```
src/cab/            the engine (library); one package, importable with no CLI dependency
  analysis/         deterministic checks, embeddings, the judge port + adapters, the hybrid engine
  ingestion/        loaders, parsers, security (caps, upload hardening), demo corpus
  scoring/          the scoring contract, banding
  manifest/         the Blueprint Manifest generator (the hero deliverable)
  report/           render contract, PDF, email gate
  interfaces/       pluggable ports (brand, email, pipeline sink)
  cli.py            the thin CLI adapter
config/             scoring_contract.yaml, privacy.yaml (locked, versioned)
corpora/            bundled sample + calibration + fixture corpora
tests/              the hermetic test suite
examples/
  reference-service/  an unsupported HTTP wrapper — the ONLY place deployment lives
docs/               this documentation
```

## Adding a judge adapter

The judge port is one method. To target another provider (any OpenAI-compatible API, a local
model, etc.), implement it:

```python
from cab.analysis.judge import Judge, JudgePass
from cab.models import Corpus


class MyProviderJudge:
    """Adapter for <provider>. Bring your own key/client."""

    def run(self, corpus: Corpus) -> JudgePass:
        # 1. Build a prompt from corpus.documents (each has .name and .text).
        # 2. Call your provider at temperature 0.0, asking for the three semantic
        #    dimension scores + findings + a short narrative (see the ClaudeJudge
        #    prompt in cab/analysis/judge.py for the exact JSON schema).
        # 3. Parse the response into a JudgePass. A missing dimension score MUST
        #    default conservatively (never a perfect 1.0), or a parse gap can inflate
        #    the band.
        return JudgePass(
            scores={
                "cross_document_consistency": ...,
                "attributability": ...,
                "terminology_consistency": ...,
            },
            findings=[...],
            narrative="...",
        )
```

Inject it explicitly:

```python
from cab.pipeline import run_on_directory

report = run_on_directory("./my-corpus", judge=MyProviderJudge())
```

A run on any non-reference judge is automatically labeled **community / unverified calibration**
in the report — see [calibration provenance](provider-reference.md#calibration-provenance).
Reuse the schema and the tolerant parser in `cab.analysis.judge` as a starting point.

## Running the checks

```bash
pip install -r requirements-dev.txt

pytest -q                                   # hermetic engine suite (mock judge)
pytest examples/reference-service/tests -q  # reference-service example tests

black --check src tests examples            # formatting
ruff check src tests examples               # linting
mypy                                         # typing (config in pyproject.toml)
```

The suite is hermetic: it runs with the deterministic `MockJudge` and needs no key or network.
Live-judge tests (`tests/test_live_judge.py`) run only when `ANTHROPIC_API_KEY` is present and
skip otherwise. Set `CAB_FORCE_MOCK_JUDGE=1` to force the mock even with a key exported.

## Coding standards

- Formatting: `black` (line length 100). Linting: `ruff`. Typing: `mypy` (see `pyproject.toml`).
- Every shipped source file carries an `SPDX-License-Identifier: MIT` header.
- Public API is type-hinted and docstringed (purpose / args / returns).
- No dead code, no `TODO`/`FIXME` in shipped source.

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the pull-request workflow.
