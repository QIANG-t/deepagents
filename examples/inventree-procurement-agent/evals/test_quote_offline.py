"""Regression tests for the quote fixture and submitted-artifact judge."""

import copy
import hashlib
import json
import unittest

from quote_offline import (
    FixtureError, _expected_tool_hash, _price_unit_value, grade, load_fixture, run, validate_case,
)
from inventree_procurement_plugin.quote import _parse_extraction


def artifact(case):
    source = case["source_text"]
    return {
        "supplier_part_id": case["supplier_part"]["supplier_part_id"],
        "source_text": source,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "model": "deepseek-flash",
        "extracted": copy.deepcopy(case["expected"]["extracted"]),
        "checks": [{"field": field, "status": status, "message": "synthetic"}
                   for field, status in case["expected"]["checks"].items()],
        "tool_calls": [{"name": "read_quote_snapshot", "status": "success",
                        "tool_call_id": "submitted-trace", "result_sha256": _expected_tool_hash(case)}],
    }


class QuoteOfflineTests(unittest.TestCase):
    def test_inventory_does_not_claim_model_passes(self):
        cases, fixture_hash = load_fixture()
        report = run()
        self.assertEqual(len(cases), 7)
        self.assertEqual(len(fixture_hash), 64)
        self.assertEqual(report["observation_count"], 0)
        self.assertEqual(report["pass_count"], 0)
        self.assertEqual(len(report["not_run_case_ids"]), 7)
        self.assertEqual(report["live_model_calls"], 0)

    def test_judge_accepts_well_formed_synthetic_artifacts(self):
        cases, _ = load_fixture()
        for case in cases:
            with self.subTest(case=case["id"]):
                result = grade(case, artifact(case))
                self.assertEqual(result["status"], "pass")
                self.assertTrue(result["manual_review_required"])

    def test_wrong_source_span_and_invented_value_fail(self):
        cases, _ = load_fixture()
        changed = artifact(cases[1])
        changed["extracted"]["sku"]["end"] -= 1
        self.assertIn("source_span_mismatch", grade(cases[1], changed)["failures"])
        changed = artifact(cases[4])
        source = cases[4]["source_text"]
        start = source.index("0.01")
        changed["extracted"]["unit_price"] = {
            "value": "0.01", "evidence": "0.01", "start": start, "end": start + 4,
        }
        self.assertIn("unit_price: expected 1.50", grade(cases[4], changed)["failures"])

    def test_only_price_unit_allows_per_prefix_equivalence(self):
        cases, _ = load_fixture()
        case = cases[0]
        changed = artifact(case)
        changed["extracted"]["price_unit"]["value"] = "per pack"
        self.assertEqual(grade(case, changed)["status"], "pass")
        self.assertEqual(_price_unit_value(" PER   Pack "), "pack")
        self.assertNotEqual(_price_unit_value("each"), _price_unit_value("pack"))
        start = case["source_text"].index("USD")
        changed["extracted"]["price_unit"] = {
            "value": "USD", "evidence": "USD", "start": start, "end": start + 3,
        }
        self.assertIn("price_unit: expected pack", grade(case, changed)["failures"])
        changed = artifact(case)
        changed["extracted"]["unit_price"]["value"] = "12.5"
        self.assertEqual(grade(case, changed)["status"], "pass")
        changed = artifact(case)
        changed["extracted"]["sku"]["value"] = "ns-220"
        self.assertIn("sku: expected NS-220", grade(case, changed)["failures"])

    def test_chinese_price_unit_yuan_per_piece_equivalence_is_narrow(self):
        cases, _ = load_fixture()
        case = cases[1]
        changed = artifact(case)
        changed["extracted"]["price_unit"]["value"] = "元/件"
        self.assertEqual(grade(case, changed)["status"], "pass")
        self.assertEqual(_price_unit_value("元/件"), "件")
        self.assertNotEqual(_price_unit_value("元/箱"), "件")
        self.assertNotEqual(_price_unit_value("美元/件"), "件")
        changed["extracted"]["price_unit"]["start"] += 1
        self.assertIn("source_span_mismatch", grade(case, changed)["failures"])

    def test_api_artifact_offsets_must_be_exact_even_if_model_parser_repairs_them(self):
        cases, _ = load_fixture()
        case = cases[1]
        changed = artifact(case)
        changed["extracted"]["sku"]["start"] += 1
        changed["extracted"]["sku"]["end"] += 1
        repaired = _parse_extraction(json.dumps(changed["extracted"], ensure_ascii=False),
                                     case["source_text"])
        self.assertEqual(repaired["sku"], case["expected"]["extracted"]["sku"])
        result = grade(case, changed)
        self.assertEqual(result["status"], "fail")
        self.assertIn("source_span_mismatch", result["failures"])

    def test_parser_filter_does_not_erase_submitted_tier_price_or_moq(self):
        cases, _ = load_fixture()
        tier_case = cases[5]
        tier_quote = artifact(tier_case)
        tier_source = tier_case["source_text"]
        start = tier_source.index("USD 8.00")
        tier_quote["extracted"]["unit_price"] = {
            "value": "8.00", "evidence": "USD 8.00", "start": start, "end": start + len("USD 8.00"),
        }
        self.assertIsNone(_parse_extraction(json.dumps(tier_quote["extracted"]),
                                             tier_source)["unit_price"])
        self.assertIn("unit_price: expected unknown", grade(tier_case, tier_quote)["failures"])

        moq_case = cases[6]
        moq_quote = artifact(moq_case)
        moq_source = moq_case["source_text"]
        start = moq_source.index("50 units")
        moq_quote["extracted"]["pack_quantity"] = {
            "value": "50", "evidence": "50 units", "start": start, "end": start + len("50 units"),
        }
        self.assertIsNone(_parse_extraction(json.dumps(moq_quote["extracted"]),
                                             moq_source)["pack_quantity"])
        self.assertIn("pack_quantity: expected unknown", grade(moq_case, moq_quote)["failures"])

    def test_missing_quote_fields_cannot_be_filled_from_supplier_snapshot(self):
        cases, _ = load_fixture()
        changed = artifact(cases[6])
        source = cases[6]["source_text"]
        changed["extracted"]["supplier_name"] = {
            "value": "Hidden Supplier", "evidence": source[:5], "start": 0, "end": 5,
        }
        self.assertIn("extraction_contract_failed", grade(cases[6], changed)["failures"])

    def test_comparison_and_trace_are_separate_contracts(self):
        cases, _ = load_fixture()
        changed = artifact(cases[3])
        for check in changed["checks"]:
            if check["field"] == "sku":
                check["status"] = "match"
        self.assertIn("comparison_status_mismatch", grade(cases[3], changed)["failures"])
        changed = artifact(cases[0])
        changed["tool_calls"][0]["result_sha256"] = "0" * 64
        self.assertIn("tool_trace_mismatch", grade(cases[0], changed)["failures"])

    def test_fixture_rejects_forged_oracle_span_and_status(self):
        cases, _ = load_fixture()
        changed = copy.deepcopy(cases[1])
        changed["expected"]["extracted"]["sku"]["start"] += 1
        with self.assertRaises(FixtureError):
            validate_case(changed)
        changed = copy.deepcopy(cases[3])
        changed["expected"]["checks"]["sku"] = "match"
        with self.assertRaises(FixtureError):
            validate_case(changed)

    def test_duplicate_submissions_are_rejected(self):
        cases, _ = load_fixture()
        observation = {"case_id": "Q01", "run_id": "trial-1", "quote": artifact(cases[0])}
        with self.assertRaises(ValueError):
            run([observation, observation])


if __name__ == "__main__":
    unittest.main()
