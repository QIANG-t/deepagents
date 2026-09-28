"""Deep Agents entry point; the host supplies a model and procurement adapter."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import TYPE_CHECKING

from procurement import ProcurementWorkflow

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel
    from langgraph.checkpoint.base import BaseCheckpointSaver


SYSTEM_PROMPT = """You assist with purchasing for selected InvenTree build orders.
Use inspect_inputs and propose_plan to gather evidence. Explain selected build lines,
shared supply, quote provenance, rounding, price, and unresolved questions.
Never claim an InvenTree connection unless the host adapter actually provides one.
Never invent missing prices, currency conversion, lead times, or permissions.
The user must approve the exact plan digest through the host application. You cannot
call the host approval action. Only call create_pending_drafts after host approval.
Created orders must remain PENDING; never place orders with suppliers.
"""


def create_procurement_agent(
    model: BaseChatModel,
    workflow: ProcurementWorkflow,
    checkpointer: BaseCheckpointSaver,
):
    """Construct the agent around one task's workflow and durable graph checkpoint.

    The host must persist workflow plans and approvals separately before production
    use. The in-memory workflow here exists for local prototyping only.
    """
    from deepagents import create_deep_agent
    from langchain_core.tools import tool

    @tool
    def inspect_inputs() -> str:
        """Read selected build needs, shared supply, and sourced quotes."""
        snapshot = workflow.gateway.read_snapshot(workflow.build_ids)
        return json.dumps(asdict(snapshot), default=str, sort_keys=True)

    @tool
    def propose_plan() -> str:
        """Calculate a new plan; this invalidates any earlier approval."""
        return json.dumps(asdict(workflow.analyze()), default=str, sort_keys=True)

    @tool
    def create_pending_drafts() -> str:
        """Create approved PENDING purchase order drafts after rechecking data."""
        return json.dumps(workflow.create_drafts(), sort_keys=True)

    return create_deep_agent(
        model=model,
        tools=[inspect_inputs, propose_plan, create_pending_drafts],
        system_prompt=SYSTEM_PROMPT,
        interrupt_on={"create_pending_drafts": {"allowed_decisions": ["approve", "reject"]}},
        checkpointer=checkpointer,
    )
