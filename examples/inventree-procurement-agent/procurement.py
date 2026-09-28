"""Deterministic, offline-verifiable procurement workflow contracts.

Amounts are already normalized by an adapter to the part's stock unit. This module
never assumes that InvenTree's per-build availability can be summed across builds.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, ROUND_CEILING
from typing import Callable, Protocol


@dataclass(frozen=True)
class BuildNeed:
    build_id: int
    line_id: int
    part_id: int
    outstanding: Decimal  # Requirement after allocation and work in progress.


@dataclass(frozen=True)
class PartSupply:
    part_id: int
    free_stock: Decimal  # Shared stock available to the selected builds, counted once.
    incoming: Decimal  # Confirmed supply available to the selected builds, counted once.


@dataclass(frozen=True)
class Quote:
    supplier_part_id: int
    supplier_id: int
    part_id: int
    unit_price: Decimal  # Price per supplier order unit.
    currency: str
    stock_units_per_order_unit: Decimal  # E.g. pack_quantity_native, verified by adapter.
    order_multiple: Decimal  # Quoted ordering multiple in supplier order units.
    valid_until: date
    source: str


@dataclass(frozen=True)
class Snapshot:
    needs: tuple[BuildNeed, ...]
    supplies: tuple[PartSupply, ...]
    quotes: tuple[Quote, ...]


@dataclass(frozen=True)
class PlanLine:
    part_id: int
    supplier_part_id: int
    supplier_id: int
    quantity: Decimal  # Supplier order units; maps to po-line.quantity.
    unit_price: Decimal
    currency: str
    source: str
    build_line_ids: tuple[int, ...]


@dataclass(frozen=True)
class Plan:
    digest: str
    snapshot_digest: str
    status: str  # awaiting_approval, needs_clarification, or no_purchase_needed
    lines: tuple[PlanLine, ...]
    questions: tuple[str, ...]


@dataclass(frozen=True)
class Approval:
    plan_digest: str
    approver: str


class ProcurementGateway(Protocol):
    """Adapter boundary; production implementations must enforce user permissions."""

    def read_snapshot(self, build_ids: tuple[int, ...]) -> Snapshot: ...

    def find_complete_pending_order(self, idempotency_key: str) -> str | None:
        """Return an order only after verifying status and every approved line."""
        ...

    def create_pending_order(
        self, supplier_id: int, lines: tuple[PlanLine, ...], idempotency_key: str
    ) -> str: ...


class WorkflowError(ValueError):
    """An approval, input, or state precondition was not met."""


def _digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _validated_snapshot(snapshot: Snapshot) -> None:
    line_ids = [line.line_id for line in snapshot.needs]
    supply_ids = [supply.part_id for supply in snapshot.supplies]
    if len(line_ids) != len(set(line_ids)) or len(supply_ids) != len(set(supply_ids)):
        raise WorkflowError("Duplicate build line or part supply")
    if any(line.outstanding < 0 for line in snapshot.needs):
        raise WorkflowError("Outstanding need cannot be negative")
    if any(item.free_stock < 0 or item.incoming < 0 for item in snapshot.supplies):
        raise WorkflowError("Shared supply cannot be negative")
    if any(q.unit_price < 0 or q.stock_units_per_order_unit <= 0 or q.order_multiple <= 0 or
           not q.currency or not q.source for q in snapshot.quotes):
        raise WorkflowError("Quote price, conversion, multiple, currency, or provenance is invalid")
    quote_ids = [quote.supplier_part_id for quote in snapshot.quotes]
    if len(quote_ids) != len(set(quote_ids)):
        raise WorkflowError("Duplicate supplier part quote")


def make_plan(snapshot: Snapshot, today: date) -> Plan:
    """Aggregate selected build needs and price eligible quotes deterministically."""
    _validated_snapshot(snapshot)
    supply = {item.part_id: item for item in snapshot.supplies}
    needs: dict[int, Decimal] = {}
    origins: dict[int, list[int]] = {}
    for line in snapshot.needs:
        needs[line.part_id] = needs.get(line.part_id, Decimal(0)) + line.outstanding
        origins.setdefault(line.part_id, []).append(line.line_id)
    lines: list[PlanLine] = []
    questions: list[str] = []
    for part_id, total in sorted(needs.items()):
        item = supply.get(part_id)
        if item is None:
            questions.append(f"Part {part_id}: shared supply is missing")
            continue
        shortage = max(Decimal(0), total - item.free_stock - item.incoming)
        if shortage == 0:
            continue
        quotes = [q for q in snapshot.quotes if q.part_id == part_id and q.valid_until >= today]
        if not quotes:
            questions.append(f"Part {part_id}: no current quote with provenance")
            continue
        if len({q.currency for q in quotes}) != 1:
            questions.append(f"Part {part_id}: quotes use different currencies; confirm conversion")
            continue
        priced = []
        for quote in quotes:
            raw_order_units = shortage / quote.stock_units_per_order_unit
            quantity = (raw_order_units / quote.order_multiple).to_integral_value(rounding=ROUND_CEILING) * quote.order_multiple
            priced.append((quantity * quote.unit_price, quote.supplier_id, quote.supplier_part_id, quantity, quote))
        _, _, _, quantity, quote = min(priced)
        lines.append(PlanLine(part_id, quote.supplier_part_id, quote.supplier_id, quantity,
                              quote.unit_price, quote.currency, quote.source, tuple(sorted(origins[part_id]))))
    snapshot_digest = _digest(asdict(snapshot))
    status = "needs_clarification" if questions else ("awaiting_approval" if lines else "no_purchase_needed")
    content = {"snapshot": snapshot_digest, "status": status, "lines": [asdict(line) for line in lines], "questions": questions}
    return Plan(_digest(content), snapshot_digest, status, tuple(lines), tuple(questions))


class ProcurementWorkflow:
    """Task-local state machine; production storage must persist plans and approvals."""

    def __init__(self, gateway: ProcurementGateway, build_ids: tuple[int, ...], clock: Callable[[], date] = date.today):
        if not build_ids or len(build_ids) != len(set(build_ids)):
            raise WorkflowError("Select unique build IDs")
        self.gateway = gateway
        self.build_ids = build_ids
        self.clock = clock
        self.plan: Plan | None = None
        self.approval: Approval | None = None
        self.orders: dict[int, str] = {}

    def analyze(self) -> Plan:
        self.plan = make_plan(self.gateway.read_snapshot(self.build_ids), self.clock())
        self.approval = None
        self.orders = {}
        return self.plan

    def approve(self, plan_digest: str, approver: str) -> Approval:
        """Called by an authenticated host action, never by the model."""
        if self.plan is None or self.plan.status != "awaiting_approval" or not self.plan.lines:
            raise WorkflowError("A complete, nonempty plan is required")
        if self.plan.digest != plan_digest or not approver.strip():
            raise WorkflowError("Approval must name the current plan and approver")
        self.approval = Approval(plan_digest, approver)
        return self.approval

    def create_drafts(self) -> dict[int, str]:
        """Create PENDING orders only after approval and a fresh snapshot match."""
        plan = self.plan
        if plan is None or self.approval is None or self.approval.plan_digest != plan.digest:
            raise WorkflowError("Current plan has no valid approval")
        fresh = make_plan(self.gateway.read_snapshot(self.build_ids), self.clock())
        if fresh.digest != plan.digest:
            self.approval = None
            raise WorkflowError("Source data changed; analyze and approve a new plan")
        for supplier_id in sorted({line.supplier_id for line in plan.lines}):
            lines = tuple(line for line in plan.lines if line.supplier_id == supplier_id)
            key = _digest({"plan": plan.digest, "supplier": supplier_id})
            order_id = self.gateway.find_complete_pending_order(key)
            if order_id is None:
                try:
                    order_id = self.gateway.create_pending_order(supplier_id, lines, key)
                except Exception:
                    order_id = self.gateway.find_complete_pending_order(key)
                    if order_id is None:
                        raise
            self.orders[supplier_id] = order_id
        return dict(self.orders)
