"""Offline fixture validation and evidence grading for procurement cases C01-C06.

This module grades supplied artifacts. It does not run InvenTree, a model, or the
browser wizard, and a passing artifact is not proof that a live API was called.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / "docs/fixtures/procurement_eval_v1.json"
DEFAULT_PLAN = ROOT / "docs/evaluation_plan.md"
SUPPORTED = frozenset(f"C{number:02d}" for number in range(1, 7))
BASELINES = frozenset({"W", "R", "A"})


class FixtureError(ValueError):
    """The versioned fixture is malformed or contradicts its own oracle."""


def decimal(value: object, label: str) -> Decimal:
    """Parse an exact, finite decimal represented as a JSON string."""
    if not isinstance(value, str):
        raise FixtureError(f"{label}: expected a decimal string")
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise FixtureError(f"{label}: invalid decimal") from error
    if not result.is_finite():
        raise FixtureError(f"{label}: non-finite decimal")
    return result


def _nonnegative(value: object, label: str) -> Decimal:
    result = decimal(value, label)
    if result < 0:
        raise FixtureError(f"{label}: negative quantity")
    return result


def _shortage(part: dict[str, Any]) -> Decimal:
    fields = (
        "minimum_stock", "required_for_build_orders", "required_for_sales_orders",
        "total_in_stock", "ordering", "building",
    )
    values = {name: _nonnegative(part.get(name, "0"), name) for name in fields}
    required = sum((values[name] for name in fields[:3]), Decimal(0))
    available = sum((values[name] for name in fields[3:]), Decimal(0))
    return max(Decimal(0), required - available)


def _quantity(shortage: Decimal, offer: dict[str, Any]) -> Decimal:
    pack = decimal(offer["pack_native"], "pack_native")
    if pack <= 0:
        raise FixtureError("pack_native must be positive")
    return (shortage / pack).to_integral_value(rounding=ROUND_CEILING)


def _oracle(case: dict[str, Any], clock: date) -> dict[str, Any]:
    shortages = {part["id"]: _shortage(part) for part in case["parts"]}
    lines: list[dict[str, Any]] = []
    for part in case["parts"]:
        shortage = shortages[part["id"]]
        if shortage == 0:
            continue
        offers = [offer for offer in case["offers"] if offer["part"] == part["id"]]
        eligible = [offer for offer in offers if date.fromisoformat(offer["valid_through"]) >= clock]
        priced = [offer for offer in eligible if "unit_price" in offer]
        if not priced:
            raise FixtureError(f"{case['id']}: no priced, valid offer for supported case")
        chosen = min(priced, key=lambda offer: (
            _quantity(shortage, offer) * decimal(offer["unit_price"], "unit_price"),
            offer["supplier"], offer["id"],
        ))
        quantity = _quantity(shortage, chosen)
        lines.append({
            "part": part["id"], "offer_id": chosen["id"],
            "supplier": chosen["supplier"], "supplier_quantity": str(quantity),
            "source_lines": sorted(line["id"] for line in part["build_lines"]),
            "extended_price": str(quantity * decimal(chosen["unit_price"], "unit_price")),
        })
    return {"shortage": {key: str(value) for key, value in shortages.items()},
            "lines": lines, "total_price": str(sum((Decimal(line["extended_price"]) for line in lines), Decimal(0)))}


def _validate_case(case: dict[str, Any], clock: date) -> None:
    parts = case["parts"]
    part_ids = [part["id"] for part in parts]
    if not parts or len(part_ids) != len(set(part_ids)):
        raise FixtureError(f"{case['id']}: missing or duplicate parts")
    for part in parts:
        total = sum((_nonnegative(line["quantity"], "build line") for line in part["build_lines"]), Decimal(0))
        if total != _nonnegative(part["required_for_build_orders"], "build requirement"):
            raise FixtureError(f"{case['id']}: build line sum differs from global requirement")
    offers = case.get("offers", [])
    if len({offer["id"] for offer in offers}) != len(offers):
        raise FixtureError(f"{case['id']}: duplicate offers")
    for offer in offers:
        if offer["part"] not in part_ids:
            raise FixtureError(f"{case['id']}: offer references unknown part")
        _quantity(Decimal(1), offer)
        date.fromisoformat(offer["valid_through"])
        if "unit_price" in offer:
            _nonnegative(offer["unit_price"], "unit_price")
    if case["id"] in SUPPORTED:
        oracle = _oracle(case, clock)
        expected = case["expected"]
        for part_id, value in expected.get("shortage", {}).items():
            if decimal(value, "expected shortage") != Decimal(oracle["shortage"][part_id]):
                raise FixtureError(f"{case['id']}: expected shortage contradicts inputs")
        for offer_id, value in expected.get("supplier_quantity", {}).items():
            actual = next((line["supplier_quantity"] for line in oracle["lines"] if line["offer_id"] == offer_id), None)
            if actual is None or decimal(value, "expected quantity") != Decimal(actual):
                raise FixtureError(f"{case['id']}: expected supplier quantity contradicts inputs")
        if "total_price" in expected and decimal(expected["total_price"], "expected price") != Decimal(oracle["total_price"]):
            raise FixtureError(f"{case['id']}: expected total price contradicts inputs")
        if "chosen_offer" in expected and expected["chosen_offer"] not in {line["offer_id"] for line in oracle["lines"]}:
            raise FixtureError(f"{case['id']}: expected offer contradicts price choice")
        for part_id, value in expected.get("ordered_native", {}).items():
            ordered = sum((Decimal(line["supplier_quantity"]) * decimal(offer["pack_native"], "pack_native")
                           for line in oracle["lines"] for offer in offers
                           if line["offer_id"] == offer["id"] and line["part"] == part_id), Decimal(0))
            if decimal(value, "expected ordered_native") != ordered:
                raise FixtureError(f"{case['id']}: expected ordered_native contradicts inputs")
        for line in oracle["lines"]:
            if "source_lines" in expected and sorted(expected["source_lines"]) != line["source_lines"]:
                raise FixtureError(f"{case['id']}: expected source lines contradict inputs")
        count = len({line["supplier"] for line in oracle["lines"]}) if "execute" in case["steps"] else 0
        if expected.get("new_po_count") != count:
            raise FixtureError(f"{case['id']}: expected new_po_count contradicts steps")


def load_fixture(path: Path = DEFAULT_FIXTURE) -> tuple[dict[str, Any], str]:
    """Load and validate the fixed synthetic fixture; return its SHA-256."""
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("schema_version") != "1.0" or data.get("synthetic") is not True:
        raise FixtureError("Unsupported or non-synthetic fixture")
    clock = date.fromisoformat(data["clock_utc"][:10])
    ids = [case["id"] for case in data["cases"]]
    if len(ids) != len(set(ids)) or not SUPPORTED.issubset(ids):
        raise FixtureError("Duplicate case IDs or supported cases missing")
    for case in data["cases"]:
        _validate_case(case, clock)
    return data, hashlib.sha256(raw).hexdigest()


def _equal_decimal(actual: object, expected: str, label: str, failures: list[str]) -> None:
    try:
        if decimal(actual, label) != Decimal(expected):
            failures.append(f"{label}: expected {expected}, got {actual}")
    except FixtureError as error:
        failures.append(str(error))


def _grade_lines(proposal: dict[str, Any], oracle: dict[str, Any], failures: list[str]) -> None:
    actual = proposal.get("lines", [])
    expected = oracle["lines"]
    if not isinstance(actual, list) or len(actual) != len(expected):
        failures.append("proposal.lines: wrong line count")
        return
    by_offer = {line.get("offer_id"): line for line in actual if isinstance(line, dict)}
    if len(by_offer) != len(actual) or set(by_offer) != {line["offer_id"] for line in expected}:
        failures.append("proposal.lines: wrong or duplicate offer IDs")
        return
    for line in expected:
        found = by_offer[line["offer_id"]]
        if found.get("part") != line["part"] or found.get("supplier") != line["supplier"]:
            failures.append(f"{line['offer_id']}: part or supplier mismatch")
        sources = found.get("source_lines")
        if not isinstance(sources, list) or sorted(sources) != line["source_lines"]:
            failures.append(f"{line['offer_id']}: missing build-line provenance")
        _equal_decimal(found.get("supplier_quantity"), line["supplier_quantity"],
                       f"{line['offer_id']}.supplier_quantity", failures)


def _grade_orders(observation: dict[str, Any], proposal: dict[str, Any],
                  oracle: dict[str, Any], execute: bool, failures: list[str]) -> None:
    if execute:
        approval = observation.get("approval")
        if not isinstance(approval, dict) or approval.get("approved") is not True or not proposal.get("version") or not proposal.get("snapshot_digest"):
            failures.append("approval: missing approved plan version or snapshot digest")
        elif (approval.get("version") != proposal["version"] or
              approval.get("snapshot_digest") != proposal["snapshot_digest"]):
            failures.append("approval: version or snapshot digest mismatch")
    after = observation.get("po_after")
    if not isinstance(after, dict) or after.get("verified") is not True:
        failures.append("po_after: verified readback is required")
        return
    orders = after.get("orders")
    if not isinstance(orders, list):
        failures.append("po_after.orders: expected list")
        return
    expected_count = len({line["supplier"] for line in oracle["lines"]}) if execute else 0
    if len(orders) != expected_count:
        failures.append(f"po_after.orders: expected {expected_count}, got {len(orders)}")
    if not execute:
        return
    expected_suppliers = {line["supplier"] for line in oracle["lines"]}
    if {order.get("supplier") for order in orders if isinstance(order, dict)} != expected_suppliers:
        failures.append("po_after.orders: supplier set mismatch")
    order_ids = [order.get("id") for order in orders if isinstance(order, dict)]
    if len(order_ids) != len(set(order_ids)):
        failures.append("po_after.orders: duplicate order IDs")
    for order in orders:
        if not isinstance(order, dict) or not order.get("id") or order.get("status") != 10:
            failures.append("po_after.orders: each order needs ID and PENDING status 10")
            continue
        expected_lines = [line for line in oracle["lines"] if line["supplier"] == order.get("supplier")]
        actual_lines = order.get("lines", [])
        if not isinstance(actual_lines, list) or any(not isinstance(item, dict) for item in actual_lines):
            failures.append(f"{order['id']}: malformed lines")
            continue
        if len(actual_lines) != len(expected_lines):
            failures.append(f"{order['id']}: wrong line count or supplier")
            continue
        for line in expected_lines:
            matched = [item for item in actual_lines if item.get("offer_id") == line["offer_id"]]
            if len(matched) != 1:
                failures.append(f"{order['id']}: missing or duplicate {line['offer_id']}")
            else:
                _equal_decimal(matched[0].get("quantity"), line["supplier_quantity"],
                               f"{order['id']}.{line['offer_id']}.quantity", failures)


def grade(case: dict[str, Any], observation: dict[str, Any], clock: date) -> dict[str, Any]:
    """Score one submitted artifact for a supported case."""
    oracle = _oracle(case, clock)
    failures: list[str] = []
    proposal = observation.get("proposal")
    if not isinstance(proposal, dict):
        proposal = {}
        failures.append("proposal: object required")
    expected_action = case["expected"].get("action", "proposal")
    if proposal.get("action") != expected_action:
        failures.append(f"proposal.action: expected {expected_action}")
    actual_shortage = proposal.get("shortage", {})
    if not isinstance(actual_shortage, dict) or set(actual_shortage) != set(oracle["shortage"]):
        failures.append("proposal.shortage: wrong part IDs")
    else:
        for part_id, value in oracle["shortage"].items():
            _equal_decimal(actual_shortage[part_id], value, f"shortage.{part_id}", failures)
    _grade_lines(proposal, oracle, failures)
    if oracle["lines"]:
        _equal_decimal(proposal.get("total_price"), oracle["total_price"], "total_price", failures)
    _grade_orders(observation, proposal, oracle, "execute" in case["steps"], failures)
    return {"case_id": case["id"], "run_id": observation["run_id"],
            "baseline": observation["baseline"], "status": "fail" if failures else "pass",
            "checks": {"oracle": oracle, "failures": failures},
            "evidence_level": "submitted_artifact_only"}


def evaluate(data: dict[str, Any], fixture_sha: str, plan_sha: str,
             observations: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a report that distinguishes graded, unsupported, and absent runs."""
    clock = date.fromisoformat(data["clock_utc"][:10])
    cases = {case["id"]: case for case in data["cases"]}
    seen: set[tuple[str, str, str]] = set()
    results: list[dict[str, Any]] = []
    for item in observations:
        case_id, run_id, baseline = item.get("case_id"), item.get("run_id"), item.get("baseline")
        if case_id not in cases or not isinstance(run_id, str) or not run_id or baseline not in BASELINES:
            raise FixtureError("Observation needs a known case_id, nonempty run_id, and W/R/A baseline")
        key = (case_id, run_id, baseline)
        if key in seen:
            raise FixtureError(f"Duplicate observation {key}")
        seen.add(key)
        if case_id in SUPPORTED:
            results.append(grade(cases[case_id], item, clock))
        else:
            results.append({"case_id": case_id, "run_id": run_id, "baseline": baseline,
                            "status": "unsupported", "reason": "No deterministic judge implemented"})
    counts = {status: sum(result["status"] == status for result in results)
              for status in ("pass", "fail", "unsupported")}
    return {"schema_version": "1.0", "fixture_sha256": fixture_sha,
            "plan_sha256": plan_sha, "clock_utc": data["clock_utc"],
            "evidence_level": "submitted_artifact_only; no live system or model executed",
            "supported_cases": sorted(SUPPORTED),
            "unsupported_cases": sorted(set(cases) - SUPPORTED),
            "not_run_supported_cases": sorted(SUPPORTED - {r["case_id"] for r in results if r["status"] in {"pass", "fail"}}),
            "counts": counts, "results": results}


def main(argv: list[str] | None = None) -> int:
    """Validate fixtures and optionally grade JSON observations without model keys."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--observations", type=Path, help="JSON array of submitted observations")
    parser.add_argument("--output", type=Path, help="Write report JSON here; stdout otherwise")
    args = parser.parse_args(argv)
    try:
        data, fixture_sha = load_fixture(args.fixture)
        plan_sha = hashlib.sha256(args.plan.read_bytes()).hexdigest()
        observations = json.loads(args.observations.read_text()) if args.observations else []
        if not isinstance(observations, list) or any(not isinstance(item, dict) for item in observations):
            raise FixtureError("Observations must be a JSON array of objects")
        report = evaluate(data, fixture_sha, plan_sha, observations)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"evaluation input error: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        if args.output:
            args.output.write_text(rendered)
        else:
            print(rendered, end="")
    except OSError as error:
        print(f"evaluation output error: {error}", file=sys.stderr)
        return 2
    return 1 if report["counts"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
