# Offline procurement eval, first slice

For the implemented single-Build read-only plugin and DeepSeek explanation, use the separate [read-only explanation evaluation](README.readonly.md). The 18 cases below target the future quote, approval, and purchase-write workflow; they are not scores for the current plugin.

`offline.py` validates the 18-case synthetic fixture and grades **submitted observation artifacts for C01–C06 only**. It makes no InvenTree, browser, or model calls. C07–C18 are listed as `unsupported`; C01–C06 without submitted observations are `not_run`, never `pass`. A `pass` means the submitted JSON matches the fixture oracle and claimed readback shape. It does not authenticate the artifact or prove a real purchase order was created.

From this directory:

```sh
python3 offline.py > inventory.json
python3 offline.py --observations observations.json --output report.json
python3 -m unittest discover -s . -p 'test_*.py' -v
```

The first command produces an inventory with zero passes. The second accepts a JSON array, one object per `(case_id, run_id, baseline)`. `baseline` is `W`, `R`, or `A`. A submitted C05 artifact has this shape:

```json
[
  {
    "case_id": "C05", "run_id": "trial-1", "baseline": "R",
    "proposal": {
      "action": "proposal", "version": "v1", "snapshot_digest": "snapshot-1",
      "shortage": {"P1": "13"}, "total_price": "60",
      "lines": [{"part": "P1", "offer_id": "O1", "supplier": "S1", "supplier_quantity": "3", "source_lines": ["B1-L1"]}]
    },
    "approval": {"approved": true, "version": "v1", "snapshot_digest": "snapshot-1"},
    "po_after": {"verified": true, "orders": [{"id": "PO-1", "supplier": "S1", "status": 10, "lines": [{"offer_id": "O1", "quantity": "3"}]}]}
  }
]
```

For C01/C03, use `action: "no_order"`, empty proposal lines, and an empty verified `po_after.orders` list. For C04/C06, use `action: "proposal_only"` and an empty verified order list. C02/C05 require a matching approval artifact and PENDING order readback. All submitted cases must include a full `shortage` map; positive shortages require exact supplier quantity, price, and build-line provenance. The oracle computes shortage and quote choice from fixture inputs rather than copying `expected` values, and fixture validation rejects contradictory expected values.

The report contains fixture and plan SHA-256 hashes, supported and unsupported case lists, per-artifact checks, and counts of passes/failures. `offline.py` exits `0` when inputs parse and no submitted supported artifact fails, `1` for scored failures, and `2` for malformed inputs. No observations is a valid inventory operation, not a successful experiment.

Remaining work: connect W/R/A runners to the same snapshot, add authenticated and independently captured database readback, implement C07–C18 judges for document extraction, approval changes, permissions, idempotency, and fault recovery, then run repeated trials. The example's `procurement.py` is a separate prototype and does not implement all fixture semantics; this evaluator does not silently treat its unit tests as results for the 18 cases.
