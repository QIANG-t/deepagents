"""Mock-HTTP checks for the read adapter and disabled write boundary."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inventree_adapter import (  # noqa: E402
    AdapterError,
    InvenTreeReadAdapter,
    PermissionDenied,
    TransportFailure,
    UrllibJsonTransport,
    WriteDisabled,
    format_draft_requests,
)
from procurement import PartSupply, ProcurementWorkflow, Quote, make_plan  # noqa: E402


BASE = "https://inventory.example.test"


class MockTransport:
    def __init__(self, pages: dict[str, object]):
        self.pages = pages
        self.calls: list[str] = []

    def get_json(self, url: str) -> object:
        self.calls.append(url)
        value = self.pages[url]
        if isinstance(value, Exception):
            raise value
        return value


def line(pk: int, build: int, quantity: str) -> dict[str, object]:
    return {"pk": pk, "build": build, "part": 7, "quantity": quantity,
            "consumed": "0", "allocated": "0", "available_stock": "100"}


def pages() -> dict[str, object]:
    return {
        f"{BASE}/api/build/10/": {"pk": 10},
        f"{BASE}/api/build/11/": {"pk": 11},
        f"{BASE}/api/build/line/?build=10": {
            "results": [line(1, 10, "8")], "next": f"{BASE}/api/build/line/?build=10&page=2"
        },
        f"{BASE}/api/build/line/?build=10&page=2": {"results": [], "next": None},
        f"{BASE}/api/build/line/?build=11": [line(2, 11, "7")],
        f"{BASE}/api/part/7/": {"pk": 7, "total_in_stock": "3"},
        f"{BASE}/api/part/7/requirements/": {"unallocated_stock": "3"},
        f"{BASE}/api/stock/?part=7&include_variants=false": [
            {"pk": 100, "part": 7, "quantity": "3", "allocated": "0"}
        ],
        f"{BASE}/api/company/part/?part=7&active=true&supplier_active=true": [
            {"pk": 101, "part": 7, "supplier": 21, "pack_quantity_native": "2"}
        ],
        f"{BASE}/api/company/price-break/?part=101": [
            {"pk": 301, "part": 101, "quantity": "1", "price": "10", "price_currency": "USD"}
        ],
    }


def supply_resolver(part_id, detail, requirements, stock, needs):
    assert detail["pk"] == part_id
    assert len(stock) == 1
    assert len(needs) == 2
    # Test policy only: a production policy must verify allocations and locations.
    return PartSupply(part_id, Decimal(str(requirements["unallocated_stock"])), Decimal("2"))


def quote_resolver(supplier_part, breaks, shortage):
    assert len(breaks) == 1
    assert shortage == Decimal("10") or shortage == Decimal("7")
    quote = breaks[0]
    return Quote(
        supplier_part_id=int(supplier_part["pk"]),
        supplier_id=int(supplier_part["supplier"]),
        part_id=int(supplier_part["part"]),
        unit_price=Decimal(str(quote["price"])),
        currency=str(quote["price_currency"]),
        stock_units_per_order_unit=Decimal(str(supplier_part["pack_quantity_native"])),
        order_multiple=Decimal("1"),  # External, verified quotation in this fixture.
        valid_until=date(2030, 1, 1),
        source="synthetic:quote-301",
    )


class AdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = MockTransport(pages())
        self.adapter = InvenTreeReadAdapter(BASE, self.transport, supply_resolver, quote_resolver)

    def test_pagination_mapping_and_supplier_unit_conversion(self) -> None:
        snapshot = self.adapter.read_snapshot((10, 11))
        self.assertEqual(tuple(need.outstanding for need in snapshot.needs), (Decimal("8"), Decimal("7")))
        self.assertEqual(snapshot.supplies[0].free_stock, Decimal("3"))
        self.assertEqual(snapshot.quotes[0].stock_units_per_order_unit, Decimal("2"))
        plan = make_plan(snapshot, date(2026, 9, 28))
        self.assertEqual(plan.lines[0].quantity, Decimal("5"))
        self.assertIn("include_variants=false", " ".join(self.transport.calls))
        self.assertEqual(len(self.transport.calls), 10)

    def test_line_allocation_is_deducted_once(self) -> None:
        self.transport.pages[f"{BASE}/api/build/line/?build=10"]["results"][0]["allocated"] = "3"
        snapshot = self.adapter.read_snapshot((10, 11))
        self.assertEqual(snapshot.needs[0].outstanding, Decimal("5"))
        self.assertEqual(snapshot.supplies[0].free_stock, Decimal("3"))

    def test_permission_denial_is_not_masked(self) -> None:
        self.transport.pages[f"{BASE}/api/part/7/"] = PermissionDenied("403")
        with self.assertRaises(PermissionDenied):
            self.adapter.read_snapshot((10, 11))

    def test_unknown_read_result_has_no_automatic_retry(self) -> None:
        self.transport.pages[f"{BASE}/api/build/line/?build=10"] = TransportFailure("timeout")
        with self.assertRaises(TransportFailure):
            self.adapter.read_snapshot((10, 11))
        self.assertEqual(self.transport.calls, [f"{BASE}/api/build/10/", f"{BASE}/api/build/line/?build=10"])

    def test_pagination_cannot_leave_origin(self) -> None:
        self.transport.pages[f"{BASE}/api/build/line/?build=10"]["next"] = "https://other.test/api/build/line/?page=2"
        with self.assertRaisesRegex(AdapterError, "Pagination target"):
            self.adapter.read_snapshot((10, 11))

    def test_pagination_cannot_drop_build_filter(self) -> None:
        self.transport.pages[f"{BASE}/api/build/line/?build=10"]["next"] = "/api/build/line/?page=2"
        with self.assertRaisesRegex(AdapterError, "requested filters"):
            self.adapter.read_snapshot((10, 11))

    def test_quote_pack_mismatch_is_rejected(self) -> None:
        def wrong_quote(supplier_part, breaks, shortage):
            quote = quote_resolver(supplier_part, breaks, shortage)
            return Quote(quote.supplier_part_id, quote.supplier_id, quote.part_id, quote.unit_price,
                         quote.currency, Decimal("1"), quote.order_multiple, quote.valid_until, quote.source)

        adapter = InvenTreeReadAdapter(BASE, self.transport, supply_resolver, wrong_quote)
        with self.assertRaisesRegex(AdapterError, "pack conversion"):
            adapter.read_snapshot((10, 11))

    def test_quote_price_must_match_rest_price_break(self) -> None:
        def wrong_quote(supplier_part, breaks, shortage):
            quote = quote_resolver(supplier_part, breaks, shortage)
            return Quote(quote.supplier_part_id, quote.supplier_id, quote.part_id, Decimal("1"),
                         quote.currency, quote.stock_units_per_order_unit, quote.order_multiple,
                         quote.valid_until, quote.source)

        adapter = InvenTreeReadAdapter(BASE, self.transport, supply_resolver, wrong_quote)
        with self.assertRaisesRegex(AdapterError, "price and currency"):
            adapter.read_snapshot((10, 11))

    def test_draft_contract_formats_supplier_part_and_disables_write(self) -> None:
        plan = make_plan(self.adapter.read_snapshot((10, 11)), date(2026, 9, 28))
        request = format_draft_requests("PO-EXAMPLE", 21, plan.lines)
        self.assertEqual(request.order, {"reference": "PO-EXAMPLE", "supplier": 21})
        self.assertEqual(request.lines[0]["part"], 101)
        self.assertEqual(request.lines[0]["quantity"], "5")
        self.assertIs(request.lines[0]["merge_items"], False)
        with self.assertRaises(WriteDisabled):
            self.adapter.find_complete_pending_order("key")
        with self.assertRaises(WriteDisabled):
            self.adapter.create_pending_order(21, plan.lines, "key")

    def test_approved_workflow_still_cannot_write_through_rest_adapter(self) -> None:
        workflow = ProcurementWorkflow(self.adapter, (10, 11), lambda: date(2026, 9, 28))
        plan = workflow.analyze()
        workflow.approve(plan.digest, "buyer")
        with self.assertRaises(WriteDisabled):
            workflow.create_drafts()
        self.assertTrue(all(url.startswith(BASE + "/api/") for url in self.transport.calls))

    def test_http_403_and_timeout_are_typed(self) -> None:
        client = UrllibJsonTransport("test-token")
        with patch("inventree_adapter.urlopen", side_effect=HTTPError(BASE, 403, "forbidden", {}, None)):
            with self.assertRaises(PermissionDenied):
                client.get_json(f"{BASE}/api/part/7/")
        with patch("inventree_adapter.urlopen", side_effect=TimeoutError("timeout")):
            with self.assertRaises(TransportFailure):
                client.get_json(f"{BASE}/api/part/7/")


if __name__ == "__main__":
    unittest.main()
