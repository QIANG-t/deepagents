"""Network-free checks for fixture integrity and offline result grading."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from offline import SUPPORTED, FixtureError, evaluate, load_fixture


def observation_for_c05() -> dict:
    """A submitted artifact with a rounded pack quantity and PENDING readback."""
    return {
        "case_id": "C05", "run_id": "trial-1", "baseline": "R",
        "proposal": {
            "action": "proposal", "version": "v1", "snapshot_digest": "snapshot-1",
            "shortage": {"P1": "13"}, "total_price": "60",
            "lines": [{"part": "P1", "offer_id": "O1", "supplier": "S1",
                       "supplier_quantity": "3", "source_lines": ["B1-L1"]}],
        },
        "approval": {"approved": True, "version": "v1", "snapshot_digest": "snapshot-1"},
        "po_after": {"verified": True, "orders": [{"id": "PO-1", "supplier": "S1",
                      "status": 10, "lines": [{"offer_id": "O1", "quantity": "3"}]}]},
    }


class OfflineEvalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data, self.fixture_sha = load_fixture()

    def report(self, observations: list[dict]) -> dict:
        return evaluate(self.data, self.fixture_sha, "plan-hash", observations)

    def test_fixture_inventory_does_not_claim_execution(self) -> None:
        report = self.report([])
        self.assertEqual(len(self.data["cases"]), 18)
        self.assertEqual(len(SUPPORTED), 6)
        self.assertEqual(report["counts"], {"pass": 0, "fail": 0, "unsupported": 0})
        self.assertEqual(report["not_run_supported_cases"], sorted(SUPPORTED))
        self.assertEqual(len(report["unsupported_cases"]), 12)

    def test_pack_quantity_and_pending_readback_pass(self) -> None:
        result = self.report([observation_for_c05()])["results"][0]
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["checks"]["oracle"]["total_price"], "60")

    def test_cross_build_shortage_counts_shared_stock_once(self) -> None:
        artifact = observation_for_c05()
        artifact["case_id"] = "C02"
        artifact["proposal"]["shortage"] = {"P1": "15"}
        artifact["proposal"]["total_price"] = "150"
        artifact["proposal"]["lines"][0]["supplier_quantity"] = "15"
        artifact["proposal"]["lines"][0]["source_lines"] = ["B1-L1", "B2-L1"]
        artifact["po_after"]["orders"][0]["lines"][0]["quantity"] = "15"
        result = self.report([artifact])["results"][0]
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["checks"]["oracle"]["shortage"]["P1"], "15")

    def test_cheaper_offer_required(self) -> None:
        artifact = observation_for_c05()
        artifact["case_id"] = "C06"
        artifact["proposal"].update({"action": "proposal_only", "shortage": {"P1": "10"}, "total_price": "100"})
        artifact["proposal"]["lines"] = [{"part": "P1", "offer_id": "O1", "supplier": "S1",
                                          "supplier_quantity": "10", "source_lines": ["B1-L1"]}]
        artifact["po_after"]["orders"] = []
        result = self.report([artifact])["results"][0]
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("offer IDs" in item for item in result["checks"]["failures"]))

    def test_wrong_pack_quantity_and_placed_order_fail(self) -> None:
        artifact = observation_for_c05()
        artifact["proposal"]["lines"][0]["supplier_quantity"] = "13"
        artifact["po_after"]["orders"][0]["status"] = 20
        result = self.report([artifact])["results"][0]
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("supplier_quantity" in item for item in result["checks"]["failures"]))
        self.assertTrue(any("PENDING" in item for item in result["checks"]["failures"]))

    def test_missing_approval_and_readback_fail(self) -> None:
        artifact = observation_for_c05()
        artifact.pop("approval")
        artifact.pop("po_after")
        result = self.report([artifact])["results"][0]
        self.assertEqual(result["status"], "fail")
        self.assertIn("po_after: verified readback is required", result["checks"]["failures"])
        self.assertTrue(any("approval" in item for item in result["checks"]["failures"]))

    def test_wrong_supplier_cannot_pass_with_empty_order(self) -> None:
        artifact = observation_for_c05()
        artifact["po_after"]["orders"][0]["supplier"] = "S2"
        artifact["po_after"]["orders"][0]["lines"] = []
        result = self.report([artifact])["results"][0]
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("supplier set" in item for item in result["checks"]["failures"]))

    def test_missing_proposal_returns_failure_not_exception(self) -> None:
        artifact = observation_for_c05()
        artifact.pop("proposal")
        result = self.report([artifact])["results"][0]
        self.assertEqual(result["status"], "fail")
        self.assertIn("proposal: object required", result["checks"]["failures"])

    def test_unsupported_case_is_not_scored(self) -> None:
        result = self.report([{"case_id": "C13", "run_id": "trial-1", "baseline": "A"}])["results"][0]
        self.assertEqual(result["status"], "unsupported")
        self.assertNotIn("checks", result)

    def test_duplicate_observation_rejected(self) -> None:
        artifact = observation_for_c05()
        with self.assertRaisesRegex(FixtureError, "Duplicate observation"):
            self.report([artifact, copy.deepcopy(artifact)])

    def test_fixture_mismatched_build_demand_rejected(self) -> None:
        data = copy.deepcopy(self.data)
        data["cases"][1]["parts"][0]["build_lines"][0]["quantity"] = "13"
        path = Path(__file__).parent / "_invalid_fixture_test.json"
        try:
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(FixtureError, "build line sum"):
                load_fixture(path)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
