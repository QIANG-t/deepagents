"""Traceable, stock-safe facts for a single selected build."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Iterable, Protocol


class PartLike(Protocol):
    pk: int
    name: str
    IPN: str
    units: str
    purchaseable: bool


class BomItemLike(Protocol):
    sub_part: PartLike


class LineLike(Protocol):
    pk: int
    quantity: Decimal
    consumed: Decimal
    bom_item: BomItemLike
    available_stock: Decimal | None

    def allocated_quantity(self) -> Decimal: ...


class BuildLike(Protocol):
    pk: int
    reference: str
    part_id: int
    status: int
    take_from_id: int | None


def _amount(value: Decimal) -> str:
    return format(value, "f")


def _line_fact(line: LineLike, build_id: int) -> dict[str, object]:
    required = Decimal(line.quantity)
    consumed = Decimal(line.consumed)
    allocated = Decimal(line.allocated_quantity())
    if min(required, consumed, allocated) < 0:
        raise ValueError("Build line quantities must be nonnegative")
    outstanding = max(required - consumed - allocated, Decimal(0))
    return {
        "build_line_id": line.pk,
        "build_id": build_id,
        "part_id": line.bom_item.sub_part.pk,
        "required": _amount(required),
        "consumed": _amount(consumed),
        "allocated": _amount(allocated),
        "outstanding": _amount(outstanding),
        "source": {
            "model": "build.BuildLine",
            "pk": line.pk,
            "fields": ["quantity", "consumed", "allocations.quantity"],
            "formula": "max(quantity - consumed - allocated_quantity(), 0)",
        },
    }


def _scoped_stock(lines: list[LineLike]) -> tuple[Decimal | None, str | None]:
    """Accept one part-level annotation only if every line agrees."""
    values: list[Decimal] = []
    for line in lines:
        raw = getattr(line, "available_stock", None)
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            return None, "Build-context available_stock annotation is missing or invalid."
        if not value.is_finite() or value < 0:
            return None, "Build-context available_stock annotation is invalid."
        values.append(value)
    if not values or len(set(values)) != 1:
        return None, "Build-context stock annotations disagree for this Part."
    return values[0], None


def _part_fact(
    part: PartLike, rows: list[dict[str, object]], lines: list[LineLike], build: BuildLike
) -> dict[str, object]:
    total = sum((Decimal(str(row["outstanding"])) for row in rows), Decimal(0))
    available, uncertainty = _scoped_stock(lines)
    location = ("take_from location and descendants" if build.take_from_id is not None else
                "all eligible stock locations")
    stock_source = ({"model": "build.BuildLine", "field": "available_stock",
                     "build_context_id": build.pk, "build_line_ids": [line.pk for line in lines]}
                    if available is not None else None)
    shortage = max(total - available, Decimal(0)) if available is not None else None
    return {
        "part_id": part.pk,
        "name": part.name,
        "ipn": part.IPN,
        "units": part.units,
        "purchaseable": part.purchaseable,
        "source": {"model": "part.Part", "pk": part.pk},
        "build_line_ids": [row["build_line_id"] for row in rows],
        "selected_build_outstanding": _amount(total),
        "available_stock": {
            "value": _amount(available) if available is not None else None,
            "source": stock_source,
            "location_assumption": {"build_take_from_id": build.take_from_id, "scope": location},
            "allocation_assumption": "InvenTree annotation subtracts sales and build allocations.",
            "warning": uncertainty,
        },
        "preliminary_shortage": {
            "value": _amount(shortage) if shortage is not None else None,
            "source": ({"formula": "max(sum(selected line outstanding) - one scoped available_stock, 0)",
                        "build_line_ids": [line.pk for line in lines]} if shortage is not None else None),
            "warning": ("Not a purchase recommendation: incoming supply, substitutes, and optional/consumable policy are excluded."
                        if shortage is not None else "Cannot subtract an unverified scoped stock quantity."),
        },
    }


def build_facts(build: BuildLike, lines: Iterable[LineLike]) -> dict[str, object]:
    """Return traceable facts with only verified, build-scoped stock annotations."""
    line_objects = sorted(lines, key=lambda line: line.pk)
    line_facts = [_line_fact(line, build.pk) for line in line_objects]
    parts = {line.bom_item.sub_part.pk: line.bom_item.sub_part for line in line_objects}
    part_facts = [
        _part_fact(part, [row for row in line_facts if row["part_id"] == part_id],
                   [line for line in line_objects if line.bom_item.sub_part.pk == part_id], build)
        for part_id, part in sorted(parts.items())
    ]
    return {
        "schema_version": 1,
        "build": {
            "build_id": build.pk,
            "reference": build.reference,
            "part_id": build.part_id,
            "status": int(build.status),
            "take_from_id": build.take_from_id,
            "source": {"model": "build.Build", "pk": build.pk},
        },
        "lines": line_facts,
        "parts": part_facts,
        "warnings": [
            "Scoped stock is read from BuildLineSerializer.annotate_queryset(..., build=selected_build); it is counted once per Part.",
            "Preliminary shortage excludes incoming supply, substitutes, and optional/consumable policy.",
        ],
    }
