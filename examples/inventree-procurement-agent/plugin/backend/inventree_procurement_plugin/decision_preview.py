"""Deterministic, read-only procurement decision preview from persisted facts."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from .quote import compare_quote


def _blocker(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


_COMMON_BLOCKERS = (
    _blocker("snapshot_not_live", "需求与库存来自已保存快照，尚未重新核实实时状态。"),
    _blocker("incoming_unverified", "初步缺口尚未核实在途供应。"),
    _blocker("substitutes_policy_unverified", "替代料及可选、消耗性物料策略尚未核实。"),
    _blocker("unit_conversion_unverified", "物料原生单位与供应商订货单位的换算尚未核实。"),
    _blocker("order_multiple_unverified", "供应商订货倍数尚未核实。"),
    _blocker("price_tier_unverified", "价格档位与订货数量的对应关系尚未核实。"),
    _blocker("price_unit_unverified", "报价计价单位与供应商订货单位的关系尚未核实。"),
    _blocker("quote_validity_unverified", "报价有效性尚未人工核实。"),
)

_CONFLICTS = {
    "supplier_name": ("supplier_conflict", "报价供应商与当前 SupplierPart 不一致。"),
    "sku": ("sku_conflict", "报价 SKU 与当前 SupplierPart 不一致。"),
    "pack_quantity": ("pack_quantity_conflict", "报价包装数量与当前 SupplierPart 不一致。"),
}


def make_decision_preview(
    task_id: str, snapshot_digest: str, preview: dict, quote: dict,
    supplier_snapshot: dict | None = None,
) -> dict:
    """Describe review blockers without deriving order quantities or money totals.

    ``supplier_snapshot`` must be permission-checked and current when a quote exists.
    Only the Part linked to that SupplierPart receives the quote observations.
    """
    if quote and supplier_snapshot is None:
        raise ValueError("A current SupplierPart snapshot is required for a quote")

    current_part_id = supplier_snapshot["part_id"] if supplier_snapshot else None
    original_part_id = quote.get("part_id") if quote else None
    quote_link_verified = (bool(quote) and original_part_id == current_part_id and
                           quote.get("snapshot_digest") == snapshot_digest)
    checks = {}
    if quote_link_verified:
        checks = {item["field"]: item["status"] for item in compare_quote(
            quote["extracted"], supplier_snapshot, quote["source_text"]
        )}

    rows = []
    for part in preview.get("parts", []):
        linked_quote = quote_link_verified and part["part_id"] == current_part_id
        blockers = [dict(item) for item in _COMMON_BLOCKERS]
        shortage = part.get("preliminary_shortage", {}).get("value")
        if shortage is None:
            blockers.append(_blocker("preliminary_shortage_unverified", "可用库存或初步缺口尚未核实。"))
        else:
            try:
                if Decimal(shortage) == 0:
                    blockers.append(_blocker("no_preliminary_shortage", "持久快照中的初步缺口为零；尚未核实实时供需。"))
            except (InvalidOperation, TypeError, ValueError):
                blockers.append(_blocker("preliminary_shortage_unverified", "初步缺口数值无效，需重新核实。"))
        if part.get("purchaseable") is False:
            blockers.append(_blocker("part_not_purchaseable", "该物料当前快照标记为不可采购。"))
        if not linked_quote and quote and not quote_link_verified and part["part_id"] in {
                current_part_id, original_part_id}:
            blockers.append(_blocker("quote_link_unverified", "报价与当前快照或物料的关联无法核实；请新建分析任务并重新提交报价。"))
        elif not linked_quote:
            blockers.append(_blocker("missing_quote", "该物料尚未关联报价。"))
        else:
            for field, (code, message) in _CONFLICTS.items():
                if checks.get(field) == "conflict":
                    blockers.append(_blocker(code, message))

        extracted = quote.get("extracted", {}) if linked_quote else {}
        rows.append({
            "part_id": part["part_id"],
            "name": part["name"],
            "units": part["units"],
            "preliminary_shortage": shortage,
            "supplier_part_id": quote["supplier_part_id"] if linked_quote else None,
            "quote_unit_price": extracted["unit_price"]["value"] if extracted.get("unit_price") else None,
            "quote_currency": extracted["currency"]["value"] if extracted.get("currency") else None,
            "quote_price_unit": extracted["price_unit"]["value"] if extracted.get("price_unit") else None,
            "blockers": blockers,
            "order_quantity": None,
            "estimated_total": None,
        })

    return {
        "task_id": str(task_id),
        "snapshot_digest": snapshot_digest,
        "quote_source_sha256": quote.get("source_sha256") if quote else None,
        "status": "needs_review",
        "rows": rows,
    }
