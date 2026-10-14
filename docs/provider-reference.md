<!-- SPDX-License-Identifier: MIT -->
# Provider & adapter reference

The three semantic dimensions — Cross-Document Consistency, Attributability, and Terminology
Consistency — are scored by a **pluggable LLM judge** behind a small port. This page covers the
shipped adapters, bring-your-own-key configuration, the capability floor, and calibration
provenance.

## The judge port

```python
class Judge(Protocol):
    def run(self, corpus: Corpus) -> JudgePass: ...
```

`JudgePass` carries per-dimension `scores` (0..1), a list of `findings`, and a short `narrative`.
The engine calls the judge **dual-run** at temperature 0.0 and arbitrates conservatively, so an
identical corpus replays to an identical result.

## Shipped adapters

| Adapter | Key required | Used when |
|---------|:------------:|-----------|
| `MockJudge` | no | Default. Deterministic heuristic stand-in — the test suite and `demo` run on it. |
| `ClaudeJudge` | yes | The reference judge (Claude). Selected automatically when `ANTHROPIC_API_KEY` is set. |
| your adapter | your choice | Any OpenAI-compatible or other provider — see the [developer guide](developer-guide.md#adding-a-judge-adapter). |

### Selection

`cab.analysis.judge.default_judge()` picks the judge:

1. `CAB_FORCE_MOCK_JUDGE` truthy → `MockJudge` (force deterministic/offline, even with a key).
2. else `ANTHROPIC_API_KEY` present → `ClaudeJudge` (the reference judge).
3. else → `MockJudge`.

You can always inject a judge explicitly: `run_on_corpus(corpus, judge=MyJudge())`.

## Bring your own key

The engine ships **no key and no provider client configuration.** For the reference judge, set
the standard environment variable:

```bash
export ANTHROPIC_API_KEY=...      # your key; never commit it
python -m cab.cli analyze ./my-corpus
```

For your own adapter, manage credentials however your provider client expects (environment
variable, secrets manager, etc.) inside the adapter. The core never reads a provider key.

## Capability floor

The semantic dimensions **ride on the judge model's comprehension.** Detecting a *paraphrased*
cross-document contradiction, or a term that has drifted between documents, requires a capable,
instruction-following frontier model.

**Below the capability floor** — small, heavily quantized, or non-instruction-tuned models — the
semantic judgments become unreliable: the judge can silently miss real defects or invent
spurious ones, and the band it produces cannot be trusted. The deterministic dimensions
(extractability, metadata, freshness, redundancy, and the numeric-conflict floor) are unaffected
because they run without a model.

Recommendation: use a capable frontier model as the judge. The reference is Claude; other
capable OpenAI-compatible frontier models are reasonable, subject to calibration below.

## Calibration provenance

The L1–L5 band thresholds (the cut-lines in `config/scoring_contract.yaml`) were **calibrated and
validated against the reference Claude judge.** A run on any other judge carries **unverified
calibration**: the thresholds may not transfer, so the band is indicative until you run
per-provider calibration.

The engine makes this explicit. Every report includes a `calibration` object:

```json
{
  "judge": "ClaudeJudge",
  "status": "reference",
  "label": "Reference calibration — validated on the Claude judge."
}
```

| `status` | Judge | How to read the band |
|----------|-------|----------------------|
| `reference` | `ClaudeJudge` | Validated calibration; the band is trustworthy. |
| `unverified` | your adapter | **Community / unverified calibration** — validate before relying on the thresholds. |
| `unverified` | `MockJudge` | Not calibrated — illustrative only (offline/demo). |

The CLI prints the label, and the render contract surfaces it above the fold, so an unverified
run is never mistaken for the validated reference. If you add a provider adapter and want to
promote it to "reference-grade" for your environment, run the calibration corpora under
`corpora/calibration/` against it and validate the cut-lines.
