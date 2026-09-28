"""Offline quantity, provenance, and shared-stock checks."""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inventree_procurement_plugin.facts import build_facts  # noqa: E402


@dataclass
class FakePart:
    pk: int = 7
    name: str = "Resistor"
    IPN: str = "R-7"
    units: str = "pcs"
    purchaseable: bool = True


@dataclass
class FakeBomItem:
    sub_part: FakePart


@dataclass
class FakeBuild:
    pk: int = 10
    reference: str = "BO-10"
    part_id: int = 99
    status: int = 10
    take_from_id: int | None = 42


@dataclass
class FakeLine:
    pk: int
    quantity: Decimal
    consumed: Decimal
    allocation: Decimal
    available_stock: Decimal | None
    bom_item: FakeBomItem

    def allocated_quantity(self) -> Decimal:
        return self.allocation


def line(pk: int, quantity: str, consumed: str, allocated: str, available: str | None) -> FakeLine:
    return FakeLine(pk, Decimal(quantity), Decimal(consumed), Decimal(allocated),
                    Decimal(available) if available is not None else None, FakeBomItem(FakePart()))


class PreviewFactsTests(unittest.TestCase):
    def test_same_part_stock_is_counted_once_with_traceable_lines(self) -> None:
        preview = build_facts(FakeBuild(), [line(2, "9", "1", "1", "5"), line(1, "8", "0", "1", "5")])
        self.assertEqual([row["build_line_id"] for row in preview["lines"]], [1, 2])
        self.assertEqual([row["outstanding"] for row in preview["lines"]], ["7", "7"])
        part = preview["parts"][0]
        self.assertEqual(part["selected_build_outstanding"], "14")
        self.assertEqual(part["available_stock"]["value"], "5")
        self.assertEqual(part["preliminary_shortage"]["value"], "9")
        self.assertEqual(part["available_stock"]["source"]["build_line_ids"], [1, 2])
        self.assertEqual(part["available_stock"]["location_assumption"]["build_take_from_id"], 42)

    def test_missing_or_conflicting_annotations_fail_closed(self) -> None:
        for second in (None, "6"):
            preview = build_facts(FakeBuild(), [line(1, "8", "0", "0", "5"), line(2, "7", "0", "0", second)])
            part = preview["parts"][0]
            self.assertIsNone(part["available_stock"]["value"])
            self.assertIsNone(part["preliminary_shortage"]["value"])
            self.assertIsNotNone(part["available_stock"]["warning"])

    def test_overallocated_line_clamps_outstanding_to_zero(self) -> None:
        preview = build_facts(FakeBuild(), [line(1, "3", "1", "3", "0")])
        self.assertEqual(preview["lines"][0]["outstanding"], "0")
        self.assertEqual(preview["parts"][0]["preliminary_shortage"]["value"], "0")


if __name__ == "__main__":
    unittest.main()
