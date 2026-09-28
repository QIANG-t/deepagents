# Read-only explanation evaluation and regression

This is the evaluation for the **current plugin**: one Build, a deterministic factual preview, and an optional DeepSeek explanation that must call `read_task_snapshot`. It is separate from the future [18-case purchasing workflow evaluation](README.md), which includes quotes, approvals, and purchase-order writes that this plugin does not yet perform.

The fixed, anonymous [eight-case fixture](../docs/fixtures/readonly_explanation_eval_v1.json) covers shared stock counted once, sufficient stock, consumed/allocated demand, two Parts, conflicting stock annotations, missing stock annotation, no BuildLines, and over-allocation clamped to zero. `read_only_explanation.py` constructs real `build_facts` previews from synthetic ORM-like objects and cross-checks them against an independent `Decimal` oracle and the hand-written expected values. A contradictory fixture fails before any model call.

## Network-free regression

From the example directory:

```sh
python3.11 -m unittest discover -s evals -p 'test_read_only_explanation.py' -v
python3.11 evals/read_only_explanation.py validate
python3.11 evals/read_only_explanation.py run --provider template --repeats 3 \
  --output /tmp/readonly-template-eval-v1.json
```

The template baseline receives the same preview and digest, produces a fixed explanation, and makes no model call. It shows what a rules-only explanation can already cover. The report records the fixture hash, explanation source hash, per-case result and duration. These checks do **not** prove live InvenTree behavior; that requires a separately seeded isolated instance.

## Explicit DeepSeek trials

With the optional AI dependencies and `DEEPSEEK_API_KEY` present in the process environment, run:

```sh
python3.11 evals/read_only_explanation.py run --provider deepseek --repeats 3 \
  --output /tmp/readonly-deepseek-eval-v1.json
```

The command makes 24 paid requests (8 cases × 3 independent trials). It does not write purchase objects or contact an InvenTree server. Model responses must be stored **outside this repository**; the runner rejects a repository output path. The report contains synthetic responses, model and tool metadata, durations and failure categories, but no API key. It does not currently include provider token usage or billing cost.

After a new run, compare it with the [pinned v1 summary](baselines/readonly_deepseek_v1_summary.json):

```sh
python3.11 evals/read_only_explanation.py compare \
  --baseline evals/baselines/readonly_deepseek_v1_summary.json \
  --candidate /tmp/readonly-deepseek-eval-v1.json
```

The comparison rejects different fixtures, providers, trial counts, or scoring code. It checks each case separately so one case's gain cannot hide another's loss. A flagged coverage change is not automatically a semantic regression. If only the grader changes, use `rescore --input old-report.json --output /tmp/rescored-report.json` to regrade saved synthetic responses without a new API call, then rebuild the baseline under the same grader. The committed summary has no model response text or credentials. The full v1 run is documented in the [v1 report](../docs/readonly_explanation_eval_v1_report.zh-CN.md).

The machine grades two distinct things:

1. **Factual preview oracle:** exact `Decimal` quantities, per-Part scoped stock and null handling, checked against fixture inputs before calls.
2. **Explanation technical contract:** nonempty bounded text, matching snapshot digest, one recorded `read_task_snapshot` call with matching result SHA-256. Keyword and ID coverage are recorded only as **hints**. An ID appearing somewhere in a paragraph does not prove that the model attached it to the right quantity.

Every explanation still requires human review for factual phrasing, unsupported purchasing advice, and clarity. Report technical pass rate and coverage hints separately; do not label either one “semantic accuracy.” A free-form model answer can vary across runs, so regression does not compare the whole text byte-for-byte. To compare two versions, keep the fixture unchanged and save separate reports; check the fixture and source hashes, per-case failures, repeat counts and durations.

The plugin HTTP/browser authorization, CSRF, durable cache and zero-purchase-order checks remain separate integration regression tests in [milestone 3](../docs/milestone3_deepseek_integration_validation.md). The synthetic runner alone does not verify those controls.
