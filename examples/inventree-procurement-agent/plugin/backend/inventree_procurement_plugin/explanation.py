"""Bounded, read-only explanation of one persisted analysis snapshot."""

import json
import os
from hashlib import sha256

MODEL = "deepseek-flash"
MAX_SNAPSHOT_BYTES = 32_768
MAX_TEXT_CHARS = 4_000
EXCLUDED_TOOLS = frozenset({
    "ls", "read_file", "write_file", "edit_file", "glob", "grep",
    "execute", "task", "write_todos", "delete",
})


class ExplanationUnavailable(Exception):
    """Configuration or optional dependencies are unavailable."""


class ExplanationFailed(Exception):
    """The provider failed or returned an unverified explanation."""


def _with_verified_digest(text: str, snapshot_digest: str) -> str:
    """Keep the complete server-verified snapshot ID visible in the explanation."""
    content = text.strip()
    if snapshot_digest not in content:
        content += f"\n\n服务端校验快照摘要：{snapshot_digest}"
    if len(content) > MAX_TEXT_CHARS:
        raise ExplanationFailed("Explanation output was invalid")
    return content


def generate_explanation(preview: dict, snapshot_digest: str) -> dict:
    """Generate one explanation only after the snapshot tool really ran."""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise ExplanationUnavailable("DEEPSEEK_API_KEY is not configured")
    snapshot = json.dumps(
        {"snapshot_digest": snapshot_digest, "preview": preview},
        ensure_ascii=False, separators=(",", ":"), sort_keys=True,
    )
    if len(snapshot.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ExplanationFailed("Snapshot exceeds the explanation size limit")
    try:
        from deepagents import (  # Optional extra; no import at plugin startup.
            GeneralPurposeSubagentProfile, HarnessProfile, create_deep_agent,
            register_harness_profile,
        )
        from deepagents.profiles.harness.harness_profiles import _harness_profile_for_model
        from langchain.agents.middleware import AgentMiddleware
        from langchain_core.messages import AIMessage, ToolMessage
        from langchain_core.tools import tool
        from langchain_deepseek import ChatDeepSeek
    except ImportError as error:
        raise ExplanationUnavailable("AI optional dependencies are not installed") from error

    invocation_count = 0

    class SnapshotToolGate(AgentMiddleware):
        """Enforce the tool allowlist at execution, including unknown names."""

        def wrap_tool_call(self, request, handler):
            name = request.tool_call.get("name")
            if name != "read_task_snapshot":
                return ToolMessage(
                    content="Tool is unavailable",
                    tool_call_id=request.tool_call.get("id") or "",
                    name=name or "unknown",
                    status="error",
                )
            return handler(request)

    @tool
    def read_task_snapshot() -> str:
        """Read the authorized task's persisted factual snapshot."""
        nonlocal invocation_count
        invocation_count += 1
        if invocation_count > 1:
            raise ValueError("Snapshot tool call limit exceeded")
        return snapshot

    try:
        model = ChatDeepSeek(
            model=MODEL,
            api_base="https://api.deepseek.com",
            api_key=api_key,
            extra_body={"thinking": {"type": "disabled"}},
            timeout=15,
            max_retries=0,
            max_tokens=600,
        )
        profile = HarnessProfile(
            excluded_tools=EXCLUDED_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        )
        register_harness_profile("deepseek:deepseek-flash", profile)
        resolved = _harness_profile_for_model(model, None)
        if not EXCLUDED_TOOLS.issubset(resolved.excluded_tools):
            raise ExplanationUnavailable("Read-only agent profile was not applied")
        if not resolved.general_purpose_subagent or resolved.general_purpose_subagent.enabled:
            raise ExplanationUnavailable("Subagent restriction was not applied")
        agent = create_deep_agent(
            model=model,
            tools=[read_task_snapshot],
            middleware=[SnapshotToolGate()],
            subagents=[],
            system_prompt=(
                "你是 InvenTree 采购分析的只读解释助手。回答前必须恰好调用一次 "
                "read_task_snapshot，只能依据工具返回的快照。全程使用简体中文，分为“已核实事实”“来源”"
                "和“未核实事项”三段，每段尽量简短。说明同一 Part 的库存只计一次，标明 Build、"
                "BuildLine、Part ID 和完整的 64 位快照摘要，不要缩写。报价、交期、在途供应、替代料及可选或消耗性物料"
                "策略若没有证据，明确写未核实。初步缺口不能当作采购建议；不要建议下单数量，"
                "不要声称已经审批或创建采购单，也不要编造任何数值。"
            ),
        )
        result = agent.invoke(
            {"messages": [{"role": "user", "content": "请先读取任务快照，再用简体中文解释已核实的需求、库存、初步缺口和局限。"}]},
            config={"recursion_limit": 5},
        )
    except ExplanationUnavailable:
        raise
    except Exception as error:
        # Never return provider exception text: it may contain request details.
        raise ExplanationFailed("Explanation model failed") from error

    messages = result.get("messages", []) if isinstance(result, dict) else []
    calls = [call for message in messages if isinstance(message, AIMessage)
             for call in (message.tool_calls or [])]
    tool_results = [message for message in messages if isinstance(message, ToolMessage)]
    if (invocation_count != 1 or len(calls) != 1 or len(tool_results) != 1 or
            calls[0].get("name") != "read_task_snapshot" or
            tool_results[0].name != "read_task_snapshot" or
            tool_results[0].tool_call_id != calls[0].get("id") or
            tool_results[0].status == "error" or
            tool_results[0].content != snapshot):
        raise ExplanationFailed("Snapshot tool execution could not be verified")
    last = messages[-1] if messages else None
    text = getattr(last, "content", None)
    if not isinstance(text, str) or not text.strip():
        raise ExplanationFailed("Explanation output was invalid")
    return {
        "text": _with_verified_digest(text, snapshot_digest),
        "model": MODEL,
        "snapshot_digest": snapshot_digest,
        "tool_calls": [{
            "name": "read_task_snapshot",
            "status": "success",
            "tool_call_id": calls[0]["id"],
            "result_sha256": sha256(snapshot.encode("utf-8")).hexdigest(),
        }],
    }
