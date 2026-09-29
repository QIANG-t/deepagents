"""Keep the decision preview deterministic and unable to invent order values."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inventree_procurement_plugin.decision_preview import make_decision_preview


def part(part_id, shortage):
    return {"part_id": part_id, "name": f"Part {part_id}", "units": "",
            "preliminary_shortage": {"value": shortage, "source": {"build_line_ids": [1, 2]},
                                     "warning": "Incoming supply is excluded"}}


def observed(value):
    return {"value": value, "evidence": value, "start": 0, "end": len(value)}


class DecisionPreviewTests(unittest.TestCase):
    def setUp(self):
        self.preview = {"parts": [part(2, "5.00000"), part(3, None)]}
        self.quote = {"supplier_part_id": 9, "part_id": 2, "snapshot_digest": "snapshot",
                      "source_sha256": "a" * 64,
                      "source_text": "Other Supplier / SKU X-9 / USD 12.50 per pack",
                      "checks": [{"field": "sku", "status": "match"}],  # stale cached result
                      "extracted": {"supplier_name": observed("Other Supplier"),
                                    "sku": observed("X-9"),
                                    "unit_price": observed("12.50"),
                                    "currency": observed("USD"),
                                    "price_unit": observed("pack"),
                                    "pack_quantity": None,
                                    "valid_until": None, "lead_time": None}}
        self.supplier = {"part_id": 2, "supplier_name": "Current Supplier", "sku": "Y-9",
                         "part_units": "", "pack_quantity_native": "5"}

    def test_each_part_has_own_quote_and_review_blockers(self):
        result = make_decision_preview("task-1", "snapshot", self.preview, self.quote, self.supplier)
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["quote_source_sha256"], "a" * 64)
        quoted, unquoted = result["rows"]
        self.assertEqual(quoted["preliminary_shortage"], "5.00000")
        self.assertEqual(quoted["supplier_part_id"], 9)
        self.assertEqual(quoted["quote_unit_price"], "12.50")
        self.assertIsNone(unquoted["supplier_part_id"])
        self.assertIsNone(unquoted["quote_unit_price"])
        codes = {item["code"] for item in quoted["blockers"]}
        self.assertIn("supplier_conflict", codes)
        self.assertIn("sku_conflict", codes)  # Fresh comparison overrides stale quote.checks.
        self.assertIn("incoming_unverified", codes)
        self.assertIn("unit_conversion_unverified", codes)
        self.assertIn("price_tier_unverified", codes)
        self.assertIn("quote_validity_unverified", codes)
        self.assertIn("missing_quote", {item["code"] for item in unquoted["blockers"]})
        self.assertIn("preliminary_shortage_unverified", {item["code"] for item in unquoted["blockers"]})
        for row in result["rows"]:
            self.assertIsNone(row["order_quantity"])
            self.assertIsNone(row["estimated_total"])

    def test_no_quote_does_not_require_supplier_snapshot(self):
        result = make_decision_preview("task-1", "snapshot", self.preview, {})
        self.assertIsNone(result["quote_source_sha256"])
        self.assertTrue(all(row["supplier_part_id"] is None for row in result["rows"]))
        self.assertTrue(all("missing_quote" in {item["code"] for item in row["blockers"]}
                            for row in result["rows"]))

    def test_quote_requires_current_supplier_snapshot(self):
        with self.assertRaises(ValueError):
            make_decision_preview("task-1", "snapshot", self.preview, self.quote)

    def test_zero_preliminary_shortage_and_nonpurchaseable_are_explicit_blockers(self):
        preview = {"parts": [{**part(2, "0.00000"), "purchaseable": False}]}
        row = make_decision_preview("task-1", "snapshot", preview, {})["rows"][0]
        codes = {item["code"] for item in row["blockers"]}
        self.assertEqual(row["preliminary_shortage"], "0.00000")
        self.assertIn("no_preliminary_shortage", codes)
        self.assertIn("part_not_purchaseable", codes)
        self.assertIsNone(row["order_quantity"])

    def test_legacy_or_relinked_quote_is_not_attached_to_another_part(self):
        legacy = {key: value for key, value in self.quote.items() if key != "part_id"}
        result = make_decision_preview("task-1", "snapshot", self.preview, legacy, self.supplier)
        self.assertIsNone(result["rows"][0]["supplier_part_id"])
        self.assertIn("quote_link_unverified",
                      {item["code"] for item in result["rows"][0]["blockers"]})
        self.assertIn("missing_quote", {item["code"] for item in result["rows"][1]["blockers"]})

        relinked = {**self.supplier, "part_id": 3}
        result = make_decision_preview("task-1", "snapshot", self.preview, self.quote, relinked)
        self.assertTrue(all(row["supplier_part_id"] is None for row in result["rows"]))
        self.assertTrue(all("quote_link_unverified" in {item["code"] for item in row["blockers"]}
                            for row in result["rows"]))

    def test_quote_with_missing_or_changed_snapshot_digest_is_not_attached(self):
        for quote in ({key: value for key, value in self.quote.items() if key != "snapshot_digest"},
                      {**self.quote, "snapshot_digest": "stale"}):
            with self.subTest(quote=quote.get("snapshot_digest")):
                result = make_decision_preview("task-1", "snapshot", self.preview,
                                               quote, self.supplier)
                linked_row = result["rows"][0]
                self.assertIsNone(linked_row["supplier_part_id"])
                self.assertIsNone(linked_row["quote_unit_price"])
                self.assertIn("quote_link_unverified",
                              {item["code"] for item in linked_row["blockers"]})


if __name__ == "__main__":
    unittest.main()
