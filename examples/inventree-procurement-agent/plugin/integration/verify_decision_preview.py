"""Check the read-only decision preview in the isolated inventree-spike instance.

Run after ``verify_quote.py`` has created a synthetic, linked quote. This script
uses Django's test client for the real URL and records no purchase actions.
"""

import os
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client

from inventree_procurement_plugin.models import ProcurementTask
from order.models import PurchaseOrder, PurchaseOrderLineItem


if os.environ.get("INVENTREE_SITE_URL") != "http://127.0.0.1:18080":
    raise RuntimeError("This script runs only in the isolated inventree-spike instance")

owner = User.objects.get(username="spike_buyer_reader")
other = User.objects.get(username="spike_owner")
task = next(
    (item for item in ProcurementTask.objects.filter(owner=owner).order_by("-created_at")
     if item.quote and item.quote.get("part_id") is not None and
     item.quote.get("snapshot_digest") == item.snapshot_digest),
    None,
)
if task is None:
    raise RuntimeError("Run verify_quote.py first to create a linked synthetic quote")

path = f"/plugin/inventree_procurement/tasks/{task.pk}/decision-preview/"
orders_before = (PurchaseOrder.objects.count(), PurchaseOrderLineItem.objects.count())

anonymous = Client().get(path, HTTP_HOST="127.0.0.1:18080")
assert anonymous.status_code == 401

other_client = Client()
other_client.force_login(other)
assert other_client.get(path, HTTP_HOST="127.0.0.1:18080").status_code == 404

client = Client()
client.force_login(owner)
response = client.get(path, HTTP_HOST="127.0.0.1:18080")
assert response.status_code == 200, response.status_code
result = response.json()
assert result["task_id"] == str(task.pk)
assert result["snapshot_digest"] == task.snapshot_digest
assert result["quote_source_sha256"] == task.quote["source_sha256"]
assert result["status"] == "needs_review"
assert len(result["rows"]) == len(task.preview["parts"])
linked = [row for row in result["rows"] if row["supplier_part_id"] == task.quote["supplier_part_id"]]
assert len(linked) == 1 and linked[0]["part_id"] == task.quote["part_id"]
assert Decimal(linked[0]["preliminary_shortage"]) == Decimal("5")
assert linked[0]["quote_unit_price"] == "12.50"
for row in result["rows"]:
    assert row["order_quantity"] is None and row["estimated_total"] is None
    assert any(item["code"] == "incoming_unverified" for item in row["blockers"])
assert (PurchaseOrder.objects.count(), PurchaseOrderLineItem.objects.count()) == orders_before

print("decision_preview_status", response.status_code)
print("part_rows", len(result["rows"]), "linked_quote_rows", len(linked))
print("all_quantities_and_totals_unverified", True)
print("anonymous_denied", True, "other_owner_hidden", True, "purchase_orders_unchanged", True)
