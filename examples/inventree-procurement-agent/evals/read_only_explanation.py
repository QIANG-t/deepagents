"""Versioned, synthetic regression runner for the current read-only agent."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from time import monotonic
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "plugin/backend"
FIXTURE = ROOT / "docs/fixtures/readonly_explanation_eval_v1.json"
sys.path.insert(0, str(BACKEND))

from inventree_procurement_plugin.facts import build_facts  # noqa: E402 - load example plugin source first


class FixtureError(ValueError):
    """The fixed synthetic case is malformed or its oracle is inconsistent."""


@dataclass
class Part:
    pk: int
    name: str
    IPN: str
    units: str
    purchaseable: bool


@dataclass
class Build:
    pk: int
    reference: str
    part_id: int
    status: int
    take_from_id: int | None


@dataclass
class BomItem:
    sub_part: Part


@dataclass
class Line:
    pk: int
    quantity: Decimal
    consumed: Decimal
    allocated: Decimal
    available_stock: Decimal | None
    bom_item: BomItem

    def allocated_quantity(self) -> Decimal:
        return self.allocated


def amount(value: object, label: str) -> Decimal:
    """Parse one finite, nonnegative decimal encoded as a string."""
    if not isinstance(value, str):
        raise FixtureError(f"{label}: expected a decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise FixtureError(f"{label}: invalid decimal") from error
    if not number.is_finite() or number < 0:
        raise FixtureError(f"{label}: expected a finite nonnegative decimal")
    return number


def load_fixture(path: Path = FIXTURE) -> tuple[list[dict[str, Any]], str]:
    """Read a fixed fixture and reject duplicate or missing case IDs."""
    raw = path.read_bytes()
    data = json.loads(raw)
    cases = data.get("cases")
    if data.get("schema_version") != 1 or data.get("synthetic") is not True:
        raise FixtureError("Unsupported or non-synthetic fixture")
    if not isinstance(cases, list) or len(cases) != 8:
        raise FixtureError("Expected exactly eight cases")
    ids = [case.get("id") for case in cases]
    if ids != [f"R{number:02d}" for number in range(1, 9)]:
        raise FixtureError("Expected R01 through R08 in order")
    for case in cases:
        preview_for_case(case)
    return cases, hashlib.sha256(raw).hexdigest()


def preview_for_case(case: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Build the plugin's real fact preview from one synthetic ORM-like case."""
    source = case["build"]
    build = Build(
        pk=int(source["id"]), reference=source["reference"],
        part_id=int(source["part_id"]), status=int(source["status"]),
        take_from_id=(None if source["take_from_id"] is None else int(source["take_from_id"])),
    )
    lines: list[Line] = []
    for record in case["parts"]:
        part = Part(
            pk=int(record["id"]), name=record["name"], IPN=record["ipn"],
            units=record["units"], purchaseable=record["purchaseable"],
        )
        for item in record["lines"]:
            stock = item["available_stock"]
            lines.append(Line(
                pk=int(item["id"]), quantity=amount(item["required"], "required"),
                consumed=amount(item["consumed"], "consumed"),
                allocated=amount(item["allocated"], "allocated"),
                available_stock=None if stock is None else amount(stock, "available_stock"),
                bom_item=BomItem(part),
            ))
    if len({line.pk for line in lines}) != len(lines):
        raise FixtureError(f"{case['id']}: duplicate BuildLine ID")
    preview = build_facts(build, lines)
    validate_oracle(case, preview)
    payload = json.dumps(preview, sort_keys=True, separators=(",", ":"))
    return preview, hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_oracle(case: dict[str, Any], preview: dict[str, Any]) -> None:
    """Compare plugin facts and hand-authored expected values to an independent oracle."""
    expected = case["expected"]
    lines = {str(line["build_line_id"]): line for line in preview["lines"]}
    if set(lines) != set(expected["outstanding_by_line"]):
        raise FixtureError(f"{case['id']}: BuildLine IDs differ from expected")
    parts = {str(part["part_id"]): part for part in preview["parts"]}
    if set(parts) != set(expected["parts"]):
        raise FixtureError(f"{case['id']}: Part IDs differ from expected")
    for record in case["parts"]:
        part_id = str(record["id"])
        outstanding = Decimal(0)
        stocks: list[Decimal | None] = []
        for item in record["lines"]:
            line_id = str(item["id"])
            required = amount(item["required"], "required")
            consumed = amount(item["consumed"], "consumed")
            allocated = amount(item["allocated"], "allocated")
            value = max(required - consumed - allocated, Decimal(0))
            if amount(expected["outstanding_by_line"][line_id], "expected outstanding") != value:
                raise FixtureError(f"{case['id']}: expected outstanding contradicts input")
            if Decimal(lines[line_id]["outstanding"]) != value:
                raise FixtureError(f"{case['id']}: plugin outstanding differs from oracle")
            outstanding += value
            stock = item["available_stock"]
            stocks.append(None if stock is None else amount(stock, "available_stock"))
        stock_value = stocks[0] if stocks and None not in stocks and len(set(stocks)) == 1 else None
        shortage = max(outstanding - stock_value, Decimal(0)) if stock_value is not None else None
        expected_part = expected["parts"][part_id]
        if amount(expected_part["total"], "expected total") != outstanding:
            raise FixtureError(f"{case['id']}: expected total contradicts input")
        for label, value in (("stock", stock_value), ("shortage", shortage)):
            declared = expected_part[label]
            if (declared is None) != (value is None):
                raise FixtureError(f"{case['id']}: expected {label} nullability contradicts input")
            if value is not None and amount(declared, f"expected {label}") != value:
                raise FixtureError(f"{case['id']}: expected {label} contradicts input")
        part = parts[part_id]
        actual_stock = part["available_stock"]["value"]
        actual_shortage = part["preliminary_shortage"]["value"]
        if actual_stock != (None if stock_value is None else format(stock_value, "f")):
            raise FixtureError(f"{case['id']}: plugin stock differs from oracle")
        if actual_shortage != (None if shortage is None else format(shortage, "f")):
            raise FixtureError(f"{case['id']}: plugin shortage differs from oracle")
    warnings = json.dumps(preview, ensure_ascii=False)
    for fragment in expected.get("required_warnings", []):
        if fragment not in warnings:
            raise FixtureError(f"{case['id']}: required warning is absent: {fragment}")


def template_explanation(preview: dict[str, Any], digest: str) -> dict[str, Any]:
    """Provide a deterministic no-model baseline over the same fact snapshot."""
    build = preview["build"]
    lines = [
        f"BuildLine ID {row['build_line_id']}、Part ID {row['part_id']}：未满足需求 {row['outstanding']}。"
        for row in preview["lines"]
    ]
    parts = []
    for part in preview["parts"]:
        stock = part["available_stock"]["value"]
        shortage = part["preliminary_shortage"]["value"]
        scope = part["available_stock"]["location_assumption"]["scope"]
        parts.append(
            f"Part ID {part['part_id']}（{part['ipn']}）：需求 {part['selected_build_outstanding']}，"
            + (f"可用库存 {stock}、初步缺口 {shortage}。" if stock is not None
               else "可用库存未核实，初步缺口不能计算。")
            + f"库存范围：{scope}；同一 Part 的库存只计一次。"
        )
    text = "\n".join([
        "## 已核实事实", f"Build {build['reference']}（ID {build['build_id']}）。",
        *(lines or ["没有 BuildLine；不能推断物料需求。"]), *parts,
        "## 来源", f"快照摘要 {digest}；build.Build、build.BuildLine、part.Part。",
        "## 未核实事项", "报价、交期、在途供应、替代料及可选或消耗性物料策略未核实。",
        "初步缺口不是采购建议；快照未提供审批或采购单状态证据，本评测模板不执行审批或建单。",
    ])
    return {"text": text, "model": "deterministic-template", "snapshot_digest": digest,
            "tool_calls": []}


def coverage_hints(text: str, preview: dict[str, Any], digest: str) -> dict[str, bool]:
    """Return surface cues for human review, never a semantic accuracy score."""
    ids = [str(row["build_line_id"]) for row in preview["lines"]]
    id_cues = all(re.search(rf"(?<!\d){re.escape(value)}(?!\d)", text) for value in ids)
    part_cues = all(part["ipn"] in text for part in preview["parts"])
    return {
        "build_reference": preview["build"]["reference"] in text,
        "snapshot_digest": digest in text,
        "build_line_ids": id_cues,
        "part_ipns": part_cues,
        "source_section": "来源" in text,
        "uncertainty_section": "未核实" in text,
    }


def grade_result(result: dict[str, Any], preview: dict[str, Any], digest: str,
                 provider: str) -> dict[str, Any]:
    """Grade hard tool-contract evidence separately from weak text coverage hints."""
    text = result.get("text")
    hard: list[str] = []
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        hard.append("text_missing_or_oversize")
    if result.get("snapshot_digest") != digest:
        hard.append("snapshot_digest_mismatch")
    if provider == "deepseek":
        if result.get("model") != "deepseek-flash":
            hard.append("model_mismatch")
        calls = result.get("tool_calls")
        snapshot = json.dumps({"snapshot_digest": digest, "preview": preview},
                              ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        expected_hash = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
        if (not isinstance(calls, list) or len(calls) != 1 or
                not isinstance(calls[0], dict) or
                calls[0].get("name") != "read_task_snapshot" or
                calls[0].get("status") != "success" or
                not calls[0].get("tool_call_id") or
                calls[0].get("result_sha256") != expected_hash):
            hard.append("snapshot_tool_evidence_mismatch")
    else:
        if result.get("model") != "deterministic-template" or result.get("tool_calls") != []:
            hard.append("template_contract_mismatch")
    hints = coverage_hints(text if isinstance(text, str) else "", preview, digest)
    return {"hard_pass": not hard, "hard_failures": hard, "coverage_hints": hints,
            "coverage_complete": all(hints.values()), "manual_review_required": True}


def judge_hash() -> str:
    """Hash only the oracle and grading code used to compare two reports."""
    code = "\n".join(inspect.getsource(function) for function in (
        amount, validate_oracle, coverage_hints, grade_result,
    ))
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def case_metrics(observations: list[dict[str, Any]], repeats: int) -> dict[str, dict[str, int]]:
    """Keep case-level counts so improvements cannot hide another case's regression."""
    metrics: dict[str, dict[str, int]] = {}
    seen: set[tuple[str, int]] = set()
    for row in observations:
        case_id, trial = row["case_id"], row["trial"]
        if case_id not in {f"R{number:02d}" for number in range(1, 9)}:
            raise ValueError(f"Unknown case ID: {case_id}")
        if not isinstance(trial, int) or not 1 <= trial <= repeats or (case_id, trial) in seen:
            raise ValueError(f"Missing or duplicate trial: {case_id} {trial}")
        seen.add((case_id, trial))
        metric = metrics.setdefault(case_id, {"trials": 0, "hard_pass": 0, "coverage_complete": 0})
        metric["trials"] += 1
        metric["hard_pass"] += bool(row["grade"]["hard_pass"])
        metric["coverage_complete"] += bool(row["grade"]["coverage_complete"])
    if len(metrics) != 8 or any(metric["trials"] != repeats for metric in metrics.values()):
        raise ValueError("Report is missing case trials")
    return dict(sorted(metrics.items()))


def run_case(case: dict[str, Any], provider: str, trial: int) -> dict[str, Any]:
    """Execute one synthetic case without touching InvenTree business objects."""
    preview, digest = preview_for_case(case)
    started = monotonic()
    try:
        if provider == "deepseek":
            from inventree_procurement_plugin.explanation import generate_explanation
            result = generate_explanation(preview, digest)
        else:
            result = template_explanation(preview, digest)
        grade = grade_result(result, preview, digest, provider)
        error = None
    except Exception as failure:
        result = None
        grade = {"hard_pass": False, "hard_failures": ["generation_failed"],
                 "coverage_hints": {}, "coverage_complete": False,
                 "manual_review_required": True}
        error = type(failure).__name__
    return {"case_id": case["id"], "trial": trial, "snapshot_digest": digest,
            "elapsed_seconds": round(monotonic() - started, 3),
            "result": result, "grade": grade, "error_type": error}


def run(provider: str, repeats: int, output: Path) -> dict[str, Any]:
    """Run fixed cases and write an inspectable report with no credentials."""
    if repeats < 1 or repeats > 10:
        raise ValueError("repeats must be between 1 and 10")
    if provider == "deepseek" and output.resolve().is_relative_to(ROOT):
        raise ValueError("Live model responses must be stored outside the repository")
    cases, fixture_hash = load_fixture()
    source = BACKEND / "inventree_procurement_plugin/explanation.py"
    observations = [run_case(case, provider, trial)
                    for case in cases for trial in range(1, repeats + 1)]
    durations = [row["elapsed_seconds"] for row in observations]
    metrics = case_metrics(observations, repeats)
    report = {
        "schema_version": 1, "provider": provider,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "fixture_sha256": fixture_hash,
        "explanation_source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "judge_sha256": judge_hash(),
        "repeats_per_case": repeats, "case_count": len(cases),
        "hard_pass_count": sum(row["hard_pass"] for row in metrics.values()),
        "coverage_complete_count": sum(row["coverage_complete"] for row in metrics.values()),
        "run_count": len(observations),
        "case_metrics": metrics,
        "median_elapsed_seconds": statistics.median(durations),
        "usage_cost": "unavailable", "semantic_accuracy": "requires_human_review",
        "observations": observations,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def rescore_report(report: dict[str, Any]) -> dict[str, Any]:
    """Regrade saved synthetic responses after a judge change, without API calls."""
    cases, fixture_hash = load_fixture()
    if report.get("fixture_sha256") != fixture_hash:
        raise ValueError("Saved responses use a different fixture")
    provider = report["provider"]
    by_id = {case["id"]: case for case in cases}
    for row in report["observations"]:
        preview, digest = preview_for_case(by_id[row["case_id"]])
        if row["snapshot_digest"] != digest:
            raise ValueError("Saved response snapshot differs from fixture")
        result = row["result"]
        row["grade"] = (grade_result(result, preview, digest, provider) if isinstance(result, dict)
                        else {"hard_pass": False, "hard_failures": ["generation_failed"],
                              "coverage_hints": {}, "coverage_complete": False,
                              "manual_review_required": True})
    metrics = case_metrics(report["observations"], report["repeats_per_case"])
    report["case_metrics"] = metrics
    report["judge_sha256"] = judge_hash()
    report["hard_pass_count"] = sum(row["hard_pass"] for row in metrics.values())
    report["coverage_complete_count"] = sum(row["coverage_complete"] for row in metrics.values())
    report["rescored_from_saved_responses"] = True
    return report


def compare_reports(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    """Flag a changed technical result or surface cue on the same fixed fixture."""
    for field in ("provider", "fixture_sha256", "case_count", "repeats_per_case", "run_count"):
        if baseline.get(field) != candidate.get(field):
            raise ValueError(f"Cannot compare reports with different {field}")
    if baseline.get("judge_sha256") != candidate.get("judge_sha256"):
        raise ValueError("Scoring code differs; rescore saved responses or rebuild baseline")
    for field in ("hard_pass_count", "coverage_complete_count"):
        if not all(isinstance(report.get(field), int) for report in (baseline, candidate)):
            raise ValueError(f"Missing count: {field}")
    for report in (baseline, candidate):
        if report.get("schema_version") != 1 or report["run_count"] != (
                report["case_count"] * report["repeats_per_case"]):
            raise ValueError("Invalid report schema or run count")
        metrics = report.get("case_metrics")
        if not isinstance(metrics, dict) or len(metrics) != report["case_count"]:
            raise ValueError("Missing case-level metrics")
        if any(row["trials"] != report["repeats_per_case"] or
               any(not 0 <= row[field] <= row["trials"]
                   for field in ("hard_pass", "coverage_complete"))
               for row in metrics.values()):
            raise ValueError("Invalid case-level counts")
        for field, metric_field in (("hard_pass_count", "hard_pass"),
                                    ("coverage_complete_count", "coverage_complete")):
            if sum(row[metric_field] for row in metrics.values()) != report[field]:
                raise ValueError(f"Case-level {metric_field} differs from total")
        if "observations" in report and case_metrics(
                report["observations"], report["repeats_per_case"]) != metrics:
            raise ValueError("Case-level metrics differ from observations")
    if set(baseline["case_metrics"]) != set(candidate["case_metrics"]):
        raise ValueError("Case IDs differ between reports")
    hard_delta = candidate["hard_pass_count"] - baseline["hard_pass_count"]
    coverage_delta = candidate["coverage_complete_count"] - baseline["coverage_complete_count"]
    case_drops = [case_id for case_id, row in candidate["case_metrics"].items()
                  if any(row[field] < baseline["case_metrics"][case_id][field]
                         for field in ("hard_pass", "coverage_complete"))]
    return {
        "provider": candidate["provider"], "fixture_sha256": candidate["fixture_sha256"],
        "technical_pass_delta": hard_delta, "coverage_hint_delta": coverage_delta,
        "candidate_hard_pass": candidate["hard_pass_count"],
        "candidate_coverage_complete": candidate["coverage_complete_count"],
        "case_drops": case_drops,
        "review_required": bool(case_drops),
        "note": "Coverage hints are formatting cues, not semantic accuracy.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="validate fixture and plugin fact calculations")
    runner = commands.add_parser("run", help="run template or explicit paid DeepSeek trials")
    runner.add_argument("--provider", choices=("template", "deepseek"), default="template")
    runner.add_argument("--repeats", type=int, default=1)
    runner.add_argument("--output", type=Path, required=True)
    comparison = commands.add_parser("compare", help="compare a new report to a pinned baseline")
    comparison.add_argument("--baseline", type=Path, required=True)
    comparison.add_argument("--candidate", type=Path, required=True)
    rescoring = commands.add_parser("rescore", help="regrade saved synthetic responses, no API calls")
    rescoring.add_argument("--input", type=Path, required=True)
    rescoring.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "validate":
        cases, digest = load_fixture()
        print(json.dumps({"case_count": len(cases), "fixture_sha256": digest}))
        return 0
    if args.command == "compare":
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
        candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
        result = compare_reports(baseline, candidate)
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result["review_required"] else 0
    if args.command == "rescore":
        if args.output.resolve().is_relative_to(ROOT):
            raise ValueError("Response artifacts must remain outside the repository")
        report = rescore_report(json.loads(args.input.read_text(encoding="utf-8")))
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
        print(json.dumps({"run_count": report["run_count"],
                          "hard_pass_count": report["hard_pass_count"],
                          "coverage_complete_count": report["coverage_complete_count"],
                          "judge_sha256": report["judge_sha256"]}))
        return 0
    report = run(args.provider, args.repeats, args.output)
    print(json.dumps({key: report[key] for key in (
        "provider", "case_count", "run_count", "hard_pass_count",
        "coverage_complete_count", "median_elapsed_seconds",
    )}, ensure_ascii=False))
    return 0 if report["hard_pass_count"] == report["run_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
