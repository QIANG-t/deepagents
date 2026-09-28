"""Network-free behavior checks for planning and approval boundaries."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from procurement import (  # noqa: E402
    BuildNeed,
    PartSupply,
    ProcurementWorkflow,
    Quote,
    Snapshot,
    WorkflowError,
)


class FakeGateway:
    def __init__(self, snapshot: Snapshot):
        self.snapshot = snapshot
        self.orders: dict[str, str] = {}
        self.calls: list[tuple[int, str]] = []
        self.fail_after_write = False

    def read_snapshot(self, build_ids: tuple[int, ...]) -> Snapshot:
        assert build_ids == (10, 11)
        return self.snapshot

    def find_complete_pending_order(self, idempotency_key: str) -> str | None:
        return self.orders.get(idempotency_key)

    def create_pending_order(self, supplier_id: int, lines: tuple, idempotency_key: str) -> str:
        self.calls.append((supplier_id, idempotency_key))
        assert all(line.supplier_id == supplier_id for line in lines)
        order_id = f"PENDING-{supplier_id}"
        self.orders[idempotency_key] = order_id
        if self.fail_after_write:
            raise TimeoutError("response lost after write")
        return order_id


def fixture() -> Snapshot:
    return Snapshot(
        needs=(BuildNeed(10, 1, 7, Decimal("8")), BuildNeed(11, 2, 7, Decimal("7"))),
        supplies=(PartSupply(7, Decimal("3"), Decimal("2")),),
        quotes=(
            Quote(101, 21, 7, Decimal("5"), "USD", Decimal("1"), Decimal("6"), date(2030, 1, 1), "quote:A"),
            Quote(102, 22, 7, Decimal("10"), "USD", Decimal("2"), Decimal("1"), date(2030, 1, 1), "quote:B"),
        ),
    )


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gateway = FakeGateway(fixture())
        self.clock = lambda: date(2026, 9, 28)
        self.workflow = ProcurementWorkflow(self.gateway, (10, 11), self.clock)

    def test_shared_supply_and_packaging_choose_lowest_total(self) -> None:
        plan = self.workflow.analyze()
        self.assertEqual(plan.status, "awaiting_approval")
        self.assertEqual(len(plan.lines), 1)
        self.assertEqual(plan.lines[0].quantity, Decimal("5"))
        self.assertEqual(plan.lines[0].supplier_id, 22)
        self.assertEqual(plan.lines[0].build_line_ids, (1, 2))

    def test_approval_and_repeat_creation_are_idempotent(self) -> None:
        plan = self.workflow.analyze()
        with self.assertRaises(WorkflowError):
            self.workflow.create_drafts()
        self.workflow.approve(plan.digest, "buyer@example.test")
        self.assertEqual(self.workflow.create_drafts(), {22: "PENDING-22"})
        self.assertEqual(self.workflow.create_drafts(), {22: "PENDING-22"})
        self.assertEqual(len(self.gateway.calls), 1)

    def test_changed_snapshot_revokes_approval(self) -> None:
        plan = self.workflow.analyze()
        self.workflow.approve(plan.digest, "buyer")
        old = self.gateway.snapshot
        self.gateway.snapshot = Snapshot(old.needs, (PartSupply(7, Decimal("4"), Decimal("2")),), old.quotes)
        with self.assertRaisesRegex(WorkflowError, "changed"):
            self.workflow.create_drafts()
        self.assertIsNone(self.workflow.approval)
        self.assertEqual(self.gateway.calls, [])

    def test_uncertain_network_result_is_queried_before_retry(self) -> None:
        plan = self.workflow.analyze()
        self.workflow.approve(plan.digest, "buyer")
        self.gateway.fail_after_write = True
        self.assertEqual(self.workflow.create_drafts(), {22: "PENDING-22"})
        self.assertEqual(len(self.gateway.calls), 1)

    def test_missing_quote_requires_clarification(self) -> None:
        old = self.gateway.snapshot
        self.gateway.snapshot = Snapshot(old.needs, old.supplies, ())
        plan = self.workflow.analyze()
        self.assertEqual(plan.status, "needs_clarification")
        with self.assertRaises(WorkflowError):
            self.workflow.approve(plan.digest, "buyer")

    def test_mixed_currencies_require_clarification(self) -> None:
        old = self.gateway.snapshot
        quote = old.quotes[1]
        changed = Quote(quote.supplier_part_id, quote.supplier_id, quote.part_id,
                        quote.unit_price, "EUR", quote.stock_units_per_order_unit,
                        quote.order_multiple, quote.valid_until, quote.source)
        self.gateway.snapshot = Snapshot(old.needs, old.supplies, (old.quotes[0], changed))
        plan = self.workflow.analyze()
        self.assertEqual(plan.status, "needs_clarification")
        self.assertIn("different currencies", plan.questions[0])

    def test_sufficient_supply_creates_no_order(self) -> None:
        old = self.gateway.snapshot
        self.gateway.snapshot = Snapshot(old.needs, (PartSupply(7, Decimal("15"), Decimal("0")),), old.quotes)
        plan = self.workflow.analyze()
        self.assertEqual(plan.status, "no_purchase_needed")
        with self.assertRaises(WorkflowError):
            self.workflow.approve(plan.digest, "buyer")

    def test_quote_expiry_invalidates_approved_plan(self) -> None:
        current = [date(2026, 9, 28)]
        self.workflow.clock = lambda: current[0]
        old = self.gateway.snapshot
        quotes = tuple(Quote(q.supplier_part_id, q.supplier_id, q.part_id, q.unit_price,
                             q.currency, q.stock_units_per_order_unit, q.order_multiple,
                             date(2026, 9, 28), q.source) for q in old.quotes)
        self.gateway.snapshot = Snapshot(old.needs, old.supplies, quotes)
        plan = self.workflow.analyze()
        self.workflow.approve(plan.digest, "buyer")
        current[0] = date(2026, 9, 29)
        with self.assertRaisesRegex(WorkflowError, "changed"):
            self.workflow.create_drafts()


if __name__ == "__main__":
    unittest.main()
