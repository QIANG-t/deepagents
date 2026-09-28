# Pasted quote evaluation v1

This fixed, synthetic set tests the **read-only quote extraction contract**. It is separate from the earlier Build explanation and future purchase order workflow evaluations.

The seven cases cover a complete English quote, Chinese Unicode offsets, absent fields, supplier and SKU conflicts, an instruction embedded in quote text, ambiguous tiered prices, and missing supplier/SKU despite a selected SupplierPart. The fixture stores exact source spans and expected values. It expects `unverified` for quote price versus SupplierPriceBreak, lead time, and pack quantities with units: the MVP has not proved quantity and price unit conversions.

[`quote_eval_v2.json`](../docs/fixtures/quote_eval_v2.json) keeps Q01–Q07 unchanged and adds eight explicitly synthetic cases, Q08–Q15. They exercise repeated price and SKU evidence, Chinese tiered prices, MOQ alongside a separate pack quantity, supplier/SKU conflicts, unknown lead time and validity, an embedded instruction, and the one direct pack-number comparison allowed by the backend. The v1 file and its hash are frozen so the historical seven-case observations remain comparable only to v1.

From this directory:

```sh
python3 quote_offline.py > quote-inventory.json
python3 quote_offline.py --observations quote-observations.json --output quote-report.json
python3 -m unittest test_quote_offline.py -v
python3 quote_offline.py --fixture ../docs/fixtures/quote_eval_v2.json > quote-v2-inventory.json
python3 quote_offline.py --fixture ../docs/fixtures/quote_eval_v2.json --observations quote-v2-observations.json --output quote-v2-report.json
```

The first command validates the fixture and reports seven `not_run` cases, zero observations, and zero passes. The second grades submitted artifacts. An observation is a JSON array item with `case_id`, `run_id`, and a `quote` object in the plugin API response shape:

```json
[
  {
    "case_id": "Q01",
    "run_id": "trial-1",
    "quote": {
      "supplier_part_id": 101,
      "source_text": "...",
      "source_sha256": "...",
      "model": "deepseek-flash",
      "extracted": {"supplier_name": null, "sku": null, "unit_price": null, "currency": null, "price_unit": null, "pack_quantity": null, "valid_until": null, "lead_time": null},
      "checks": [],
      "tool_calls": []
    }
  }
]
```

With `--fixture` omitted, the judge always uses frozen v1. The v2 inventory reports 15 `not_run` cases when no observations are submitted. Grade the v2 observation files only with the v2 fixture; the v1 and v2 percentages have different denominators.

Use the exact source text and selected SupplierPart snapshot from [`quote_eval_v1.json`](../docs/fixtures/quote_eval_v1.json). The `quote` example above shows the object shape, not a passing result. The judge checks source hash, selected SupplierPart ID, exact **stored** `start`/`end` source offsets for every non-null field, expected field values/nulls, comparison statuses, and the submitted tool result hash. The backend may repair a model's offset before storing the quote; the judge does not repair an API artifact. It allows different valid evidence spans for the same value. Thus it cannot prove that a value was associated with the right label in a complicated document; the report marks every artifact for manual review.

During the first three live trial runs, before freezing the first quote baseline, Q01 returned `per pack` for `price_unit` where the oracle says `pack`. Both forms are supported by the source phrase `per pack`. The judge now removes only a leading `per ` from `price_unit` when comparing values, ignoring case and extra spaces. Other fields still use exact value comparison; the fixture text and oracle are unchanged. Record the judge revision with future baselines so a score change cannot be confused with a model improvement.

The same three trials exposed a second equivalent form in Q02: `price_unit` was `元/件` once, while the oracle says `件`. Before the first baseline was frozen, the judge added only the exact mapping `元/件` → `件`; it does not strip arbitrary currency/unit prefixes. Exact stored source spans are still required. Q06 and Q07 oracle values remain unchanged because their observed differences were model errors, not equivalent wording.

For the new Q10 Chinese tier case, `元/包` and `包` both describe the price unit in the cited source line. Before freezing the first v2 baseline, the judge added only the exact mapping `元/包` → `包`. It still rejects other prefixes such as `人民币/包`, and still checks the stored source span. The frozen v1 case set and its previously observed results are unchanged.

The judge passes a submitted extraction through the backend parser to check its format and source support, then compares the **original API fields** with the fixture oracle. It does not grade the parser's repaired or filtered copy: an old response claiming Q06's tier price or Q07's MOQ as a pack quantity must fail even though the current parser would suppress those values. Positive numeric values compare as decimals; nonnumeric fields remain exact except the enumerated `price_unit` equivalences above.

The offline judge makes **no** DeepSeek, InvenTree, Docker, or browser calls. A submitted artifact and tool trace can be fabricated, so even a passing row proves only that the supplied JSON satisfies these checks. The separate [isolated live runner](../plugin/integration/run_quote_eval.py) produced the checked-in synthetic observations in `baselines/quote_deepseek_v1_observations.json` through `quote_deepseek_v4_observations.json`. Regrade one version with `python3 quote_offline.py --observations baselines/quote_deepseek_v4_observations.json`; exit status 1 is expected while any cases fail. The [milestone 4 report](../docs/milestone4_quote_eval_v1_report.zh-CN.md) records the four repeated-run summaries and limitations. The final version passed 18/21 synthetic observations, with three `QuoteFailed` results and no purchase writes. No provider cost estimate was recorded, and these seven cases do not establish production accuracy.

Later isolated runs are stored in `baselines/quote_deepseek_v5_observations.json` (v1 fixture) and `baselines/quote_deepseek_v2set_observations.json` / `quote_deepseek_v2set_fixed_observations.json` (v2 fixture). The [milestone 5 report](../docs/milestone5_quote_eval_v2_report.zh-CN.md) records the 21/21 v1 retest, 39/45 first v2 run, and 44/45 final v2 run with one safely rejected result. These small synthetic sets do not establish production accuracy.
