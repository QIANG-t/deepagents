"""Offline checks for exact quote citations and the read-only tool gate."""

import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inventree_procurement_plugin.quote import (
    QuoteFailed, QuoteUnavailable, _parse_extraction, compare_quote, extract_quote,
)


FIELDS = ("supplier_name", "sku", "unit_price", "currency", "price_unit",
          "pack_quantity", "valid_until", "lead_time")


def field(source, value, evidence):
    start = source.index(evidence)
    return {"value": value, "evidence": evidence, "start": start, "end": start + len(evidence)}


class AIMessage:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class ToolMessage:
    def __init__(self, content, tool_call_id, name, status="success"):
        self.content = content
        self.tool_call_id = tool_call_id
        self.name = name
        self.status = status


class FakeProfile:
    def __init__(self, excluded_tools, general_purpose_subagent):
        self.excluded_tools = excluded_tools
        self.general_purpose_subagent = general_purpose_subagent


class FakeSubagent:
    def __init__(self, enabled):
        self.enabled = enabled


class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.source = "供应商：星辰\nSKU: X-2\n单价：USD 2.50 / 件\n包装：10 件\n有效期：2026-12-31"
        self.values = {key: None for key in FIELDS}
        self.values.update({
            "supplier_name": field(self.source, "星辰", "星辰"),
            "sku": field(self.source, "X-2", "X-2"),
            "unit_price": field(self.source, "2.50", "2.50"),
            "currency": field(self.source, "USD", "USD"),
            "pack_quantity": field(self.source, "10", "10 件"),
            "valid_until": field(self.source, "2026-12-31", "2026-12-31"),
        })

    def test_exact_unicode_spans_and_numeric_values(self):
        result = _parse_extraction(json.dumps(self.values), self.source)
        self.assertEqual(result["supplier_name"]["start"], 4)
        self.assertEqual(result["unit_price"]["value"], "2.50")

    def test_unique_evidence_corrects_model_offset_but_repeats_need_exact_index(self):
        shifted = json.loads(json.dumps(self.values))
        shifted["sku"]["start"] = 999
        shifted["sku"]["end"] = 1002
        result = _parse_extraction(json.dumps(shifted), self.source)
        self.assertEqual(result["sku"]["start"], self.source.index("X-2"))
        repeated = "SKU X-2; alternate X-2"
        rows = {key: None for key in FIELDS}
        rows["sku"] = {"value": "X-2", "evidence": "X-2", "start": 0, "end": 3}
        with self.assertRaises(QuoteFailed):
            _parse_extraction(json.dumps(rows), repeated)
        rows["sku"]["start"] = repeated.rindex("X-2")
        rows["sku"]["end"] = rows["sku"]["start"] + 3
        self.assertEqual(_parse_extraction(json.dumps(rows), repeated)["sku"]["start"],
                         repeated.rindex("X-2"))

    def test_rejects_nonexistent_evidence_and_unsupported_values(self):
        forged = json.loads(json.dumps(self.values))
        forged["sku"]["evidence"] = "not-in-source"
        with self.assertRaises(QuoteFailed):
            _parse_extraction(json.dumps(forged), self.source)
        forged = json.loads(json.dumps(self.values))
        forged["unit_price"]["value"] = "999"
        with self.assertRaises(QuoteFailed):
            _parse_extraction(json.dumps(forged), self.source)
        forged = json.loads(json.dumps(self.values))
        forged["sku"]["value"] = "invented"
        with self.assertRaises(QuoteFailed):
            _parse_extraction(json.dumps(forged), self.source)

    def test_missing_fields_must_be_null_and_no_extra_keys(self):
        bad = dict(self.values)
        bad["lead_time"] = {"value": "7 days"}
        with self.assertRaises(QuoteFailed):
            _parse_extraction(json.dumps(bad), self.source)
        bad = dict(self.values)
        bad["purchase_order"] = "create"
        with self.assertRaises(QuoteFailed):
            _parse_extraction(json.dumps(bad), self.source)

    def test_supplier_match_conflict_and_unverified_pricing(self):
        snapshot = {"supplier_name": "星辰", "sku": "OTHER",
                    "pack_quantity_native": "10", "part_units": ""}
        checks = {item["field"]: item["status"] for item in compare_quote(self.values, snapshot)}
        self.assertEqual(checks["supplier_name"], "match")
        self.assertEqual(checks["sku"], "conflict")
        self.assertEqual(checks["unit_price"], "unverified")

    def test_q01_single_english_price_and_pack_remain_cited(self):
        source = ("Supplier: Northstar Components\nSKU: NS-220\n"
                  "Unit price: USD 12.50 per pack\nPack quantity: 5 pcs\nLead time: 14 days")
        rows = {key: None for key in FIELDS}
        rows["unit_price"] = field(source, "12.50", "USD 12.50 per pack")
        rows["currency"] = field(source, "USD", "USD 12.50")
        rows["price_unit"] = field(source, "pack", "per pack")
        rows["pack_quantity"] = field(source, "5", "5 pcs")
        rows["lead_time"] = field(source, "14 days", "14 days")
        result = _parse_extraction(json.dumps(rows), source)
        self.assertEqual(result["unit_price"]["value"], "12.50")
        self.assertEqual(result["pack_quantity"]["value"], "5")
        self.assertEqual(result["lead_time"]["value"], "14 days")

    def test_q02_single_chinese_price_and_pack_remain_cited(self):
        source = "供应商：星辰电子\n料号：XC-7\n单价：人民币 8.80 元/件\n包装：10 件"
        rows = {key: None for key in FIELDS}
        rows["unit_price"] = field(source, "8.80", "8.80 元/件")
        rows["currency"] = field(source, "人民币", "人民币 8.80")
        rows["price_unit"] = field(source, "件", "元/件")
        rows["pack_quantity"] = field(source, "10", "10 件")
        result = _parse_extraction(json.dumps(rows, ensure_ascii=False), source)
        self.assertEqual(result["unit_price"]["value"], "8.80")
        self.assertEqual(result["pack_quantity"]["value"], "10")

    def test_q06_ambiguous_price_tiers_clear_only_unselected_price(self):
        source = ("Supplier: Tiered Supply\nSKU: T-1\n"
                  "1-9 packs: USD 8.00 per pack\n10+ packs: USD 7.00 per pack\nLead time: TBD")
        rows = {key: None for key in FIELDS}
        rows["sku"] = field(source, "T-1", "T-1")
        rows["unit_price"] = field(source, "8.00", "USD 8.00")
        rows["currency"] = field(source, "USD", "USD 8.00")
        rows["price_unit"] = field(source, "pack", "per pack")
        rows["lead_time"] = field(source, "TBD", "TBD")
        result = _parse_extraction(json.dumps(rows), source)
        self.assertEqual(result["sku"]["value"], "T-1")
        self.assertIsNone(result["unit_price"])
        self.assertEqual(result["currency"]["value"], "USD")
        self.assertEqual(result["price_unit"]["value"], "pack")
        self.assertIsNone(result["lead_time"])

    def test_explicit_unknown_lead_time_markers_are_not_facts(self):
        for marker in (" tBd ", "TBA", "To   Be   Determined", "待定", "未确定"):
            source = f"Lead time: {marker}"
            rows = {key: None for key in FIELDS}
            rows["lead_time"] = field(source, marker, marker)
            with self.subTest(marker=marker):
                self.assertIsNone(_parse_extraction(json.dumps(rows, ensure_ascii=False), source)["lead_time"])

    def test_q07_moq_is_not_pack_quantity(self):
        source = "Offer valid until 2026-12-31. MOQ 50 units. USD 4.20 per item."
        rows = {key: None for key in FIELDS}
        rows["pack_quantity"] = field(source, "50", "50 units")
        rows["unit_price"] = field(source, "4.20", "USD 4.20 per item")
        rows["currency"] = field(source, "USD", "USD 4.20")
        result = _parse_extraction(json.dumps(rows), source)
        self.assertIsNone(result["pack_quantity"])
        self.assertEqual(result["unit_price"]["value"], "4.20")

    def _modules(self, execute_tool):
        holder = {}

        def register(_, profile):
            holder["profile"] = profile

        def create_agent(**kwargs):
            self.assertEqual(len(kwargs["tools"]), 1)
            self.assertEqual(kwargs["subagents"], [])
            self.assertIn("若同一证据片段在原文重复出现", kwargs["system_prompt"])
            self.assertIn("1-9 packs: USD 8.00 per pack", kwargs["system_prompt"])
            holder["tool"] = kwargs["tools"][0]
            gate = kwargs["middleware"][0]
            blocked = {"called": False}
            denied = gate.wrap_tool_call(
                types.SimpleNamespace(tool_call={"name": "write_file", "id": "forged"}),
                lambda _: blocked.__setitem__("called", True))
            self.assertFalse(blocked["called"])
            self.assertEqual(denied.status, "error")

            class Agent:
                def invoke(self, payload, config):
                    assert config["recursion_limit"] <= 5
                    messages = [AIMessage(tool_calls=[{"name": "read_quote_snapshot", "id": "call-1"}])]
                    if execute_tool:
                        messages.append(ToolMessage(holder["tool"](), "call-1", "read_quote_snapshot"))
                    messages.append(AIMessage(json.dumps(self_values, ensure_ascii=False)))
                    return {"messages": messages}

            self_values = self.values
            return Agent()

        deepagents = types.ModuleType("deepagents")
        deepagents.GeneralPurposeSubagentProfile = FakeSubagent
        deepagents.HarnessProfile = FakeProfile
        deepagents.register_harness_profile = register
        deepagents.create_deep_agent = create_agent
        langchain = types.ModuleType("langchain")
        agents = types.ModuleType("langchain.agents")
        middleware = types.ModuleType("langchain.agents.middleware")
        middleware.AgentMiddleware = type("AgentMiddleware", (), {})
        profiles = types.ModuleType("deepagents.profiles")
        harness = types.ModuleType("deepagents.profiles.harness")
        harness_profiles = types.ModuleType("deepagents.profiles.harness.harness_profiles")
        harness_profiles._harness_profile_for_model = lambda model, spec: holder["profile"]
        core = types.ModuleType("langchain_core")
        messages = types.ModuleType("langchain_core.messages")
        messages.AIMessage = AIMessage
        messages.ToolMessage = ToolMessage
        tools = types.ModuleType("langchain_core.tools")
        tools.tool = lambda func: func
        deepseek = types.ModuleType("langchain_deepseek")
        deepseek.ChatDeepSeek = lambda **kwargs: types.SimpleNamespace()
        return {
            "deepagents": deepagents, "langchain": langchain,
            "langchain.agents": agents, "langchain.agents.middleware": middleware,
            "deepagents.profiles": profiles, "deepagents.profiles.harness": harness,
            "deepagents.profiles.harness.harness_profiles": harness_profiles,
            "langchain_core": core, "langchain_core.messages": messages,
            "langchain_core.tools": tools, "langchain_deepseek": deepseek,
        }

    def test_verified_tool_call_is_recorded(self):
        with patch.dict(sys.modules, self._modules(True)), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            result = extract_quote(self.source, {"supplier_name": "星辰", "sku": "X-2"})
        self.assertEqual(result["tool_calls"][0]["tool_call_id"], "call-1")
        self.assertEqual(result["extracted"]["sku"]["value"], "X-2")

    def test_claim_without_actual_tool_execution_is_rejected(self):
        with patch.dict(sys.modules, self._modules(False)), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with self.assertRaises(QuoteFailed):
                extract_quote(self.source, {"supplier_name": "星辰", "sku": "X-2"})

    def test_missing_key_rejects_before_model_call(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            with self.assertRaises(QuoteUnavailable):
                extract_quote(self.source, {})


if __name__ == "__main__":
    unittest.main()
