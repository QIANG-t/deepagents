"""Regression tests for the fixed read-only cases and conservative grader."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from read_only_explanation import (
    FixtureError, compare_reports, grade_result, load_fixture, preview_for_case, rescore_report, run,
    template_explanation,
)


class ReadOnlyExplanationEvalTests(unittest.TestCase):
    def test_all_eight_cases_match_independent_decimal_oracle(self):
        cases, fixture_hash = load_fixture()
        self.assertEqual(len(cases), 8)
        self.assertEqual(len(fixture_hash), 64)
        for case in cases:
            with self.subTest(case=case["id"]):
                preview, digest = preview_for_case(case)
                result = template_explanation(preview, digest)
                grade = grade_result(result, preview, digest, "template")
                self.assertTrue(grade["hard_pass"])
                self.assertTrue(grade["coverage_complete"])

    def test_oracle_rejects_wrong_expected_quantity(self):
        cases, _ = load_fixture()
        changed = copy.deepcopy(cases[0])
        changed["expected"]["parts"]["201"]["shortage"] = "10"
        with self.assertRaisesRegex(FixtureError, "contradicts input"):
            preview_for_case(changed)

    def test_unverified_stock_never_becomes_numeric_shortage(self):
        cases, _ = load_fixture()
        for case in cases[4:6]:
            preview, _ = preview_for_case(case)
            self.assertIsNone(preview["parts"][0]["available_stock"]["value"])
            self.assertIsNone(preview["parts"][0]["preliminary_shortage"]["value"])

    def test_model_text_alone_cannot_pass_tool_contract(self):
        cases, _ = load_fixture()
        preview, digest = preview_for_case(cases[0])
        result = template_explanation(preview, digest)
        result["model"] = "deepseek-flash"
        result["tool_calls"] = [{"name": "read_task_snapshot", "status": "success",
                                 "tool_call_id": "forged", "result_sha256": "0" * 64}]
        grade = grade_result(result, preview, digest, "deepseek")
        self.assertFalse(grade["hard_pass"])
        self.assertIn("snapshot_tool_evidence_mismatch", grade["hard_failures"])

    def test_report_marks_semantic_accuracy_for_manual_review(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "template.json"
            report = run("template", 2, path)
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["run_count"], 16)
        self.assertEqual(report["hard_pass_count"], 16)
        self.assertEqual(report["semantic_accuracy"], "requires_human_review")
        self.assertTrue(all(row["grade"]["manual_review_required"]
                            for row in report["observations"]))

    def test_comparison_flags_coverage_drop_and_rejects_other_fixture(self):
        metrics = {f"R{number:02d}": {"trials": 3, "hard_pass": 3,
                                      "coverage_complete": 3} for number in range(1, 9)}
        metrics["R02"]["coverage_complete"] = 2
        baseline = {"schema_version": 1, "provider": "deepseek", "fixture_sha256": "same", "case_count": 8,
                    "repeats_per_case": 3, "run_count": 24, "hard_pass_count": 24,
                    "coverage_complete_count": 23, "judge_sha256": "same-judge",
                    "case_metrics": metrics}
        candidate = copy.deepcopy(baseline)
        candidate["case_metrics"]["R01"]["coverage_complete"] = 2
        candidate["case_metrics"]["R02"]["coverage_complete"] = 3
        result = compare_reports(baseline, candidate)
        self.assertTrue(result["review_required"])
        self.assertEqual(result["coverage_hint_delta"], 0)
        self.assertEqual(result["case_drops"], ["R01"])
        candidate["fixture_sha256"] = "changed"
        with self.assertRaisesRegex(ValueError, "different fixture_sha256"):
            compare_reports(baseline, candidate)

    def test_saved_responses_can_be_rescored_without_a_model(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run("template", 1, Path(directory) / "template.json")
        original_count = report["hard_pass_count"]
        rescored = rescore_report(report)
        self.assertEqual(rescored["hard_pass_count"], original_count)
        self.assertEqual(len(rescored["judge_sha256"]), 64)
        self.assertTrue(rescored["rescored_from_saved_responses"])


if __name__ == "__main__":
    unittest.main()
