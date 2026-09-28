"""Run one live, bounded DeepSeek explanation in the isolated spike instance.

Use ``manage.py shell < verify_milestone3.py`` inside the inventree-spike server.
This creates one new analysis task for BO-9001 and makes one paid model run.
It never prints credentials or makes a purchase-order request.
"""

import json
import os
from time import monotonic
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from django.contrib.auth.models import User
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory

from build.models import Build
from inventree_procurement_plugin.service import create_analysis_task
from order.models import PurchaseOrder, PurchaseOrderLineItem


if os.environ.get("INVENTREE_SITE_URL") != "http://127.0.0.1:18080":
    raise RuntimeError("This script runs only in the isolated inventree-spike instance")
if not os.environ.get("DEEPSEEK_API_KEY"):
    raise RuntimeError("DEEPSEEK_API_KEY is absent from the server process")

owner = User.objects.get(username="spike_buyer_reader")
other = User.objects.get(username="spike_owner")
build = Build.objects.get(reference="BO-9001")
orders_before = (PurchaseOrder.objects.count(), PurchaseOrderLineItem.objects.count())
task = create_analysis_task(owner, build.pk)
base = f"/plugin/inventree_procurement/tasks/{task.pk}/explanation/"


def session_headers(user, *, csrf=False):
    client = Client()
    client.force_login(user)
    headers = {"Host": "127.0.0.1:18080"}
    cookies = [f"sessionid={client.cookies['sessionid'].value}"]
    if csrf:
        request = RequestFactory().get("/")
        token = get_token(request)
        cookies.append(f"csrftoken={request.META['CSRF_COOKIE']}")
        headers["X-CSRFToken"] = token
    headers["Cookie"] = "; ".join(cookies)
    return headers


def http(method, path, *, headers=None):
    request = Request(
        "http://127.0.0.1:8000" + path,
        data=b"" if method == "POST" else None,
        method=method,
        headers=headers or {"Host": "127.0.0.1:18080"},
    )
    try:
        with urlopen(request, timeout=120) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        try:
            return error.code, json.load(error)
        except ValueError:
            return error.code, {"code": "non_json_error"}


owner_headers = session_headers(owner, csrf=True)
assert http("GET", base)[0] == 401
assert http("GET", base, headers=session_headers(other))[0] == 404
assert http("GET", base, headers=owner_headers)[0] == 409
assert http("POST", base, headers=session_headers(owner))[0] == 403

started = monotonic()
status, created = http("POST", base, headers=owner_headers)
elapsed = round(monotonic() - started, 2)
print("live_post_status", status, "elapsed_seconds", elapsed, "task_id", str(task.pk))
if status != 200:
    print("live_post_error_code", created.get("code"))
    raise AssertionError("The live explanation request did not succeed")

explanation = created["explanation"]
assert explanation["model"] == "deepseek-flash"
assert explanation["snapshot_digest"] == task.snapshot_digest
assert explanation["text"].strip()
assert len(explanation["tool_calls"]) == 1
call = explanation["tool_calls"][0]
assert call["name"] == "read_task_snapshot" and call["status"] == "success"
assert call["tool_call_id"] and len(call["result_sha256"]) == 64

assert http("GET", base, headers=owner_headers) == (200, created)
assert http("POST", base, headers=owner_headers) == (200, created)
assert (PurchaseOrder.objects.count(), PurchaseOrderLineItem.objects.count()) == orders_before
print("snapshot_digest", task.snapshot_digest)
print("tool_call_id", call["tool_call_id"], "result_sha256", call["result_sha256"])
print("explanation_text", explanation["text"])
print("cache_reused", True, "purchase_orders_unchanged", True)
