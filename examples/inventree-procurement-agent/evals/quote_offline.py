"""Offline, synthetic judge for the pasted quote extraction contract.

This grades submitted API artifacts. It never calls DeepSeek or InvenTree, and
an artifact can be fabricated: a passing result is not proof of a live run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs/fixtures/quote_eval_v1.json"
sys.path.insert(0, str(ROOT / "plugin/backend"))

from inventree_procurement_plugin.quote import (  # noqa: E402
    FIELDS, MAX_QUOTE_BYTES, QuoteFailed, _parse_extraction, compare_quote,
)

CHECK_FIELDS = (*FIELDS, "price_break")


class FixtureError(ValueError):
    """The fixed synthetic cases are malformed or contradict their oracle."""


def _exact_source_spans(extracted: object, source: str) -> bool:
    """Check stored API offsets without the model parser's repair behavior."""
    if not isinstance(extracted, dict) or set(extracted) != set(FIELDS):
        return False
    for item in extracted.values():
        if item is None:
            continue
        if not isinstance(item, dict):
            return False
        evidence, start, end = (item.get(key) for key in ("evidence", "start", "end"))
        if (not isinstance(evidence, str) or not evidence or type(start) is not int or
                type(end) is not int or not 0 <= start < end <= len(source) or
                source[start:end] != evidence):
            return False
    return True


def _price_unit_value(value: str) -> str:
    """Apply two narrow, source-backed price-unit equivalences."""
    normalized = value.strip().casefold()
    normalized = re.sub(r"^per\s+", "", normalized).strip()
    return "件" if normalized == "元/件" else normalized


def _same_field_value(field: str, observed: str, expected: str) -> bool:
    if field == "price_unit":
        return _price_unit_value(observed) == _price_unit_value(expected)
    if field in {"unit_price", "pack_quantity"}:
        # The parser already proved these are positive, source-backed decimals.
        return Decimal(observed) == Decimal(expected)
    return observed == expected


def _statuses(checks: object) -> dict[str, str]:
    if not isinstance(checks, list) or any(not isinstance(item, dict) for item in checks):
        raise FixtureError("checks must be an array of objects")
    names = [item.get("field") for item in checks]
    if any(not isinstance(name, str) for name in names):
        raise FixtureError("checks contain an invalid field")
    if len(names) != len(set(names)) or set(names) != set(CHECK_FIELDS):
        raise FixtureError("checks must contain exactly one row per quote field")
    statuses = {item["field"]: item.get("status") for item in checks}
    if any(value not in {"match", "conflict", "unverified"} for value in statuses.values()):
        raise FixtureError("checks contain an unknown status")
    return statuses


def validate_case(case: dict[str, Any]) -> None:
    """Validate hand-authored spans, field values, and comparison statuses."""
    source = case.get("source_text")
    snapshot = case.get("supplier_part")
    expected = case.get("expected")
    if not isinstance(source, str) or not source.strip() or len(source.encode("utf-8")) > MAX_QUOTE_BYTES:
        raise FixtureError(f"{case.get('id')}: invalid source text")
    if (not isinstance(snapshot, dict) or type(snapshot.get("supplier_part_id")) is not int or
            snapshot["supplier_part_id"] <= 0 or not isinstance(snapshot.get("supplier_name"), str) or
            not isinstance(snapshot.get("sku"), str)):
        raise FixtureError(f"{case.get('id')}: invalid SupplierPart snapshot")
    if not isinstance(expected, dict):
        raise FixtureError(f"{case.get('id')}: missing expected oracle")
    if not _exact_source_spans(expected.get("extracted"), source):
        raise FixtureError(f"{case.get('id')}: expected source spans are not exact")
    try:
        extracted = _parse_extraction(json.dumps(expected["extracted"], ensure_ascii=False), source)
        declared = expected["checks"]
        actual = _statuses(compare_quote(extracted, snapshot))
    except (KeyError, QuoteFailed) as error:
        raise FixtureError(f"{case.get('id')}: invalid extraction oracle") from error
    if not isinstance(declared, dict) or set(declared) != set(CHECK_FIELDS) or declared != actual:
        raise FixtureError(f"{case.get('id')}: comparison oracle contradicts inputs")


def load_fixture(path: Path = FIXTURE) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_bytes()
    data = json.loads(raw)
    if data.get("schema_version") != 1 or data.get("synthetic") is not True:
        raise FixtureError("Unsupported or non-synthetic fixture")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise FixtureError("Fixture has no cases")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if len(ids) != len(cases) or ids != [f"Q{number:02d}" for number in range(1, len(cases) + 1)]:
        raise FixtureError("Case IDs must be consecutive, starting at Q01")
    for case in cases:
        validate_case(case)
    return cases, hashlib.sha256(raw).hexdigest()


def _expected_tool_hash(case: dict[str, Any]) -> str:
    snapshot = json.dumps(
        {"source_text": case["source_text"], "supplier_part": case["supplier_part"]},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    )
    return hashlib.sha256(snapshot.encode("utf-8")).hexdigest()


def grade(case: dict[str, Any], quote: object) -> dict[str, Any]:
    """Grade a submitted quote response; source association still needs review."""
    failures: list[str] = []
    if not isinstance(quote, dict):
        return {"status": "fail", "failures": ["quote response must be an object"],
                "evidence_level": "submitted_artifact_only", "manual_review_required": True}
    source = case["source_text"]
    if quote.get("source_text") != source:
        failures.append("source_text_mismatch")
    if quote.get("supplier_part_id") != case["supplier_part"]["supplier_part_id"]:
        failures.append("supplier_part_id_mismatch")
    if quote.get("source_sha256") != hashlib.sha256(source.encode("utf-8")).hexdigest():
        failures.append("source_sha256_mismatch")
    if quote.get("model") != "deepseek-flash":
        failures.append("model_mismatch")
    calls = quote.get("tool_calls")
    if (not isinstance(calls, list) or len(calls) != 1 or not isinstance(calls[0], dict) or
            calls[0].get("name") != "read_quote_snapshot" or calls[0].get("status") != "success" or
            not isinstance(calls[0].get("tool_call_id"), str) or not calls[0]["tool_call_id"] or
            calls[0].get("result_sha256") != _expected_tool_hash(case)):
        failures.append("tool_trace_mismatch")
    extracted = quote.get("extracted")
    if not _exact_source_spans(extracted, source):
        failures.append("source_span_mismatch")
    try:
        _parse_extraction(json.dumps(extracted, ensure_ascii=False), source)
    except (TypeError, QuoteFailed):
        failures.append("extraction_contract_failed")
    else:
        # Grade the submitted API artifact, not the parser's repaired/filtered copy.
        # Otherwise an old Q06 tier price or Q07 MOQ can turn into None and pass.
        for field in FIELDS:
            wanted = case["expected"]["extracted"][field]
            observed = extracted[field]
            if wanted is None and observed is not None:
                failures.append(f"{field}: expected unknown")
            elif wanted is not None:
                if observed is None:
                    failures.append(f"{field}: expected {wanted['value']}")
                elif not _same_field_value(field, observed["value"], wanted["value"]):
                    failures.append(f"{field}: expected {wanted['value']}")
    try:
        actual_statuses = _statuses(quote.get("checks"))
    except FixtureError:
        failures.append("checks_contract_failed")
    else:
        if actual_statuses != case["expected"]["checks"]:
            failures.append("comparison_status_mismatch")
    return {"status": "fail" if failures else "pass", "failures": failures,
            "evidence_level": "submitted_artifact_only", "manual_review_required": True}


def run(observations: list[dict[str, Any]] | None = None, path: Path = FIXTURE) -> dict[str, Any]:
    cases, fixture_hash = load_fixture(path)
    by_id = {case["id"]: case for case in cases}
    rows = []
    seen = set()
    for item in observations or []:
        if not isinstance(item, dict) or item.get("case_id") not in by_id or not isinstance(item.get("run_id"), str) or not item["run_id"]:
            raise ValueError("Each observation needs a known case_id and nonempty run_id")
        identity = (item["case_id"], item["run_id"])
        if identity in seen:
            raise ValueError(f"Duplicate observation: {identity}")
        seen.add(identity)
        rows.append({"case_id": item["case_id"], "run_id": item["run_id"],
                     "grade": grade(by_id[item["case_id"]], item.get("quote"))})
    return {"schema_version": 1, "fixture_sha256": fixture_hash, "case_count": len(cases),
            "case_ids": list(by_id), "observation_count": len(rows),
            "pass_count": sum(row["grade"]["status"] == "pass" for row in rows),
            "fail_count": sum(row["grade"]["status"] == "fail" for row in rows),
            "not_run_case_ids": [case_id for case_id in by_id
                                 if not any(row["case_id"] == case_id for row in rows)],
            "observations": rows, "evidence_level": "submitted_artifact_only",
            "live_model_calls": 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, help="Submitted quote API artifacts")
    parser.add_argument("--output", type=Path, help="Write report to this JSON file")
    args = parser.parse_args(argv)
    try:
        observations = None
        if args.observations:
            observations = json.loads(args.observations.read_text(encoding="utf-8"))
            if not isinstance(observations, list):
                raise ValueError("Observations must be a JSON array")
        report = run(observations)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"Quote evaluation input error: {error}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 1 if report["fail_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
