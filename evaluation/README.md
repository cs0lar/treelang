# Evaluation

Run the deterministic offline benchmark without credentials or network access:

```sh
uv run python evaluation/eval.py \
  --output evaluation-results/offline.json \
  --comparison-output evaluation-results/comparison.json
```

The command exits with status 0 only when every case passes. Its JSON output
records dataset version, parse/schema/execution/correctness status, required AST
construct usage, latency, token and cost placeholders, model/provider identity,
and categorized failures. Offline token counts and estimated cost are zero by
definition.

Datasets live under versioned directories in `evaluation/data/`. Add or change a
case by creating a new dataset version so benchmark results remain comparable.
The credentialed questions in `data/v1/live.jsonl` are excluded from normal CI.
Each case has a stable ID so results remain comparable across runs.

## Live evaluation

Run the credentialed benchmark locally with explicit pricing for the selected
model:

```sh
OPENAI_API_KEY=... uv run python evaluation/live_eval.py \
  --output evaluation-results/live.json \
  --model gpt-4o-2024-11-20 \
  --input-cost-per-million 0 \
  --output-cost-per-million 0
```

The prices are inputs rather than hard-coded values because provider pricing may
change. Set them to the current USD price per million tokens when cost evidence
is required. The result records the exact model, provider, dataset version,
case-level quality, latency, token usage, and estimated cost.

The `Live evaluation` GitHub Actions workflow runs only on manual dispatch. It
reads `OPENAI_API_KEY` from the protected `live-evaluation` environment, never
runs for pull requests, has a 30-minute timeout, and retains the machine-readable
result artifact for 90 days. Runs are restricted to the repository owner;
attempts by other actors are skipped before the environment or its secrets are
accessed. Configure environment approval rules if live spend requires an
additional review. Manual runs require model and pricing inputs; absent pricing
deliberately produces zero estimated cost rather than silently applying a stale
price.

Compare only artifacts with identical dataset version, ordered case IDs, model,
and provider. Use the metric definitions and explicit tolerances in
`baselines/v1/tolerances.json`; investigate quality decreases before accepting a
new result. Latency, tokens, and cost must be interpreted using the recorded model
and pricing inputs. Promote a live result as published evidence only after
reviewing every failed case and recording the workflow run URL with the result.

Benchmark and model-transport lifecycle events are emitted as structured JSON
logs. They contain metadata only by default: prompts, questions, ASTs, tool
arguments/results, model output, and error details are redacted before reaching
either logs or an optional `TraceSink`. Application integrations may construct
`Observability(allow_content=True)` explicitly, but credential fields and common
API-key/authorization patterns remain redacted even in that mode.

## Regression baselines

Normal CI compares the current offline result with
`baselines/v1/offline.json`, using the explicit limits in
`baselines/v1/tolerances.json`. Comparisons fail closed unless dataset version,
mode, model, and provider all match. Quality rates may not decrease under the v1
policy; latency allows an absolute noise budget plus a percentage increase;
offline tokens and cost must remain zero.

Replace a baseline only when an intentional benchmark or implementation change
has been reviewed. Generate the candidate result with the command above, inspect
the case-level changes, update the dataset version when cases change, and include
the old/new comparison evidence in the baseline PR. Never update a baseline only
to make an unexplained regression pass.
