"""Verify the explanation needs a real, matching snapshot tool result."""

import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inventree_procurement_plugin.explanation import (
    ExplanationFailed, ExplanationUnavailable, _with_verified_digest, generate_explanation,
)


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
    def __init__(self, excluded_tools=frozenset(), general_purpose_subagent=None):
        self.excluded_tools = excluded_tools
        self.general_purpose_subagent = general_purpose_subagent


class FakeSubagentProfile:
    def __init__(self, enabled=True):
        self.enabled = enabled


class FakeModel:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class ExplanationTests(unittest.TestCase):
    def _modules(self, execute_tool):
        holder = {}

        def register(key, profile):
            self.assertEqual(key, "deepseek:deepseek-flash")
            holder["profile"] = profile

        def create_agent(**kwargs):
            self.assertEqual(len(kwargs["tools"]), 1)
            self.assertEqual(kwargs["subagents"], [])
            holder["tool"] = kwargs["tools"][0]
            gate = kwargs["middleware"][0]
            blocked = {"called": False}
            request = types.SimpleNamespace(tool_call={"name": "unknown_write", "id": "forged"})
            result = gate.wrap_tool_call(request, lambda _: blocked.__setitem__("called", True))
            self.assertFalse(blocked["called"])
            self.assertEqual(result.status, "error")

            class Agent:
                def invoke(self, payload, config):
                    self_config = config
                    assert self_config["recursion_limit"] <= 5
                    call = {"name": "read_task_snapshot", "id": "call-1"}
                    messages = [AIMessage(tool_calls=[call])]
                    if execute_tool:
                        value = holder["tool"]()
                        messages.append(ToolMessage(value, "call-1", "read_task_snapshot"))
                    messages.append(AIMessage("Facts only."))
                    return {"messages": messages}

            return Agent()

        deepagents = types.ModuleType("deepagents")
        deepagents.GeneralPurposeSubagentProfile = FakeSubagentProfile
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
        deepseek.ChatDeepSeek = FakeModel
        return {
            "deepagents": deepagents,
            "langchain": langchain,
            "langchain.agents": agents,
            "langchain.agents.middleware": middleware,
            "deepagents.profiles": profiles,
            "deepagents.profiles.harness": harness,
            "deepagents.profiles.harness.harness_profiles": harness_profiles,
            "langchain_core": core,
            "langchain_core.messages": messages,
            "langchain_core.tools": tools,
            "langchain_deepseek": deepseek,
        }, holder

    def test_success_requires_actual_tool_execution(self):
        modules, holder = self._modules(execute_tool=True)
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            result = generate_explanation({"lines": []}, "digest")
        self.assertEqual(result["snapshot_digest"], "digest")
        self.assertEqual(result["tool_calls"][0]["name"], "read_task_snapshot")
        self.assertEqual(result["tool_calls"][0]["status"], "success")
        self.assertEqual(result["tool_calls"][0]["tool_call_id"], "call-1")
        self.assertEqual(len(result["tool_calls"][0]["result_sha256"]), 64)
        self.assertFalse(holder["profile"].general_purpose_subagent.enabled)
        self.assertIn("write_file", holder["profile"].excluded_tools)
        self.assertIn("execute", holder["profile"].excluded_tools)

    def test_model_claim_without_tool_execution_is_rejected(self):
        modules, _ = self._modules(execute_tool=False)
        with patch.dict(sys.modules, modules), patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with self.assertRaises(ExplanationFailed):
                generate_explanation({"lines": []}, "digest")

    def test_missing_key_and_oversized_snapshot_fail_before_model_construction(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}):
            with self.assertRaises(ExplanationUnavailable):
                generate_explanation({"lines": []}, "digest")
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"}):
            with self.assertRaises(ExplanationFailed):
                generate_explanation({"lines": ["x" * 40_000]}, "digest")

    def test_complete_digest_is_appended_only_when_model_abbreviates_it(self):
        digest = "a" * 64
        self.assertEqual(
            _with_verified_digest("已核实：摘要 aaaa…aaaa", digest),
            f"已核实：摘要 aaaa…aaaa\n\n服务端校验快照摘要：{digest}",
        )
        self.assertEqual(_with_verified_digest(f"快照摘要：{digest}", digest), f"快照摘要：{digest}")
        with self.assertRaises(ExplanationFailed):
            _with_verified_digest("x" * 3990, digest)


if __name__ == "__main__":
    unittest.main()
