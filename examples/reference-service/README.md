# Reference upload service (unsupported example)

This is an **illustrative, unsupported example** of one way to wrap the Context
Architecture Blueprint **library** behind an HTTP upload surface
(`upload → analyze → report`). It is **not a product** and **not the supported
core** — the supported core is the Python library + CLI (see the repository
[README](../../README.md)).

**Deployment is yours.** The framework makes no deployment assumptions and ships
no hosting opinion. If you stand this service up, **you** supply authentication,
durable storage, secrets management, network controls, and any data-retention
policy appropriate to your environment.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET`  | `/healthz`        | Liveness. |
| `GET`  | `/demo`           | Run the full analysis over the bundled sample corpus (no upload). |
| `POST` | `/upload`         | Analyze an uploaded corpus (caps + cost guard enforced). |
| `GET`  | `/report/{id}`    | Fetch a rendered report (email-gated). |

## Run it locally

From the repository root (the engine resolves from `src/`):

```bash
pip install -r requirements.txt
PYTHONPATH=src uvicorn examples.reference-service.app:app --port 8080
# or, from this directory:
#   PYTHONPATH=../../src uvicorn app:app --port 8080
```

## Build the container

Build from the **repository root** so the engine package, sample corpus, and
config are included. The container honors `$PORT`.

```bash
docker build -f examples/reference-service/Dockerfile -t cab-reference-service .
docker run --rm -p 8080:8080 cab-reference-service
```

## Tests

The upload-surface security tests (type-spoof, oversized, zip-bomb, EICAR,
parser-timeout, prompt-injection) and the service smoke test live in
[`tests/`](tests/) and run from the repository root:

```bash
python -m pytest examples/reference-service/tests -q
```
