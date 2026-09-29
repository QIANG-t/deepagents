"""Exercise plugin view guards with small Django stand-ins, without a server."""

from __future__ import annotations

import importlib
import json
import sys
import types
import unittest
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class FakeJsonResponse:
    def __init__(self, data: dict, status: int = 200):
        self.data = data
        self.status_code = status


@dataclass
class FakeUser:
    is_authenticated: bool
    pk: int | None


@dataclass
class FakeRequest:
    user: FakeUser
    method: str = "GET"
    content_type: str = "application/json"
    body: bytes = b""


class FakeQuerySet(list):
    def order_by(self, key: str):
        assert key == "-created_at"
        return self


class FakeManager:
    def __init__(self, tasks: list):
        self.tasks = tasks
        self.owner_filters: list[int] = []

    def filter(self, owner_id: int):
        self.owner_filters.append(owner_id)
        return FakeQuerySet(task for task in self.tasks if task.owner_id == owner_id)

    def select_for_update(self):
        return self

    def get(self, pk: str, owner_id: int):
        for task in self.tasks:
            if task.id == str(pk) and task.owner_id == owner_id:
                return task
        raise LookupError("task not found for owner")


class FakeTask:
    def __init__(self, owner_id: int):
        self.id = "task-1"
        self.owner_id = owner_id
        self.status = "created"
        self.build_ids = [10]
        self.snapshot_digest = "digest"
        self.preview = {"schema_version": 1, "lines": []}
        self.created_at = datetime(2026, 9, 28, tzinfo=timezone.utc)
        self.updated_at = self.created_at
        self.analyzed_at = self.created_at
        self.explanation = {}
        self.explanation_started_at = None
        self.explanation_run_id = None
        self.quote = {}
        self.quote_started_at = None
        self.quote_run_id = None

    def save(self, update_fields):
        self.updated_at = datetime(2026, 9, 28, tzinfo=timezone.utc)


class ViewTests(unittest.TestCase):
    def setUp(self) -> None:
        django = types.ModuleType("django")
        django.__path__ = []
        http = types.ModuleType("django.http")
        http.HttpRequest = FakeRequest
        http.JsonResponse = FakeJsonResponse
        db = types.ModuleType("django.db")
        from contextlib import nullcontext
        db.transaction = types.SimpleNamespace(atomic=nullcontext)
        utils = types.ModuleType("django.utils")
        utils.__path__ = []
        django_timezone = types.ModuleType("django.utils.timezone")
        django_timezone.now = lambda: datetime(2026, 9, 28, tzinfo=timezone.utc)
        shortcuts = types.ModuleType("django.shortcuts")
        def lookup(model, **filters):
            for task in model.objects.tasks:
                if task.id == str(filters["pk"]) and task.owner_id == filters["owner_id"]:
                    return task
            raise LookupError("task not found for owner")
        shortcuts.get_object_or_404 = lookup
        views_package = types.ModuleType("django.views")
        views_package.__path__ = []
        decorators = types.ModuleType("django.views.decorators")
        decorators.__path__ = []
        csrf = types.ModuleType("django.views.decorators.csrf")
        csrf.csrf_protect = lambda function: function
        csrf.csrf_exempt = lambda function: function
        http_decorators = types.ModuleType("django.views.decorators.http")
        http_decorators.require_GET = lambda function: function
        http_decorators.require_http_methods = lambda methods: (lambda function: function)
        modules = {
            "django": django,
            "django.http": http,
            "django.db": db,
            "django.utils": utils,
            "django.utils.timezone": django_timezone,
            "django.shortcuts": shortcuts,
            "django.views": views_package,
            "django.views.decorators": decorators,
            "django.views.decorators.csrf": csrf,
            "django.views.decorators.http": http_decorators,
        }
        self.patch_modules = patch.dict(sys.modules, modules)
        self.patch_modules.start()
        sys.modules.pop("inventree_procurement_plugin.views", None)
        self.views = importlib.import_module("inventree_procurement_plugin.views")

    def tearDown(self) -> None:
        sys.modules.pop("inventree_procurement_plugin.views", None)
        self.patch_modules.stop()

    def test_anonymous_health_and_tasks_return_401(self) -> None:
        anonymous = FakeRequest(FakeUser(False, None))
        self.assertEqual(self.views.health(anonymous).status_code, 401)
        self.assertEqual(self.views.tasks(anonymous).status_code, 401)
        self.assertEqual(self.views.task_detail(anonymous, "task-1").status_code, 401)
        anonymous.method = "POST"
        anonymous.body = b'{"build_ids":[10]}'
        with patch.object(self.views, "create_analysis_task") as create:
            self.assertEqual(self.views.tasks(anonymous).status_code, 401)
        create.assert_not_called()

    def test_health_reports_writes_disabled(self) -> None:
        response = self.views.health(FakeRequest(FakeUser(True, 7)))
        self.assertEqual(response.data, {"status": "ok", "writes_enabled": False})

    def test_task_list_filters_by_owner(self) -> None:
        manager = FakeManager([FakeTask(7), FakeTask(8)])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}), \
                patch.object(self.views, "check_business_read_permissions"):
            response = self.views.tasks(FakeRequest(FakeUser(True, 7)))
        self.assertEqual(manager.owner_filters, [7])
        self.assertEqual(len(response.data["tasks"]), 1)
        self.assertEqual(response.data["tasks"][0]["build_ids"], [10])

    def test_task_detail_hides_another_users_task(self) -> None:
        manager = FakeManager([FakeTask(7)])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}), \
                patch.object(self.views, "check_business_read_permissions"):
            owned = self.views.task_detail(FakeRequest(FakeUser(True, 7)), "task-1")
            self.assertEqual(owned.data["task"]["id"], "task-1")
            with self.assertRaises(LookupError):
                self.views.task_detail(FakeRequest(FakeUser(True, 8)), "task-1")

    def test_preview_returns_persisted_facts_and_checks_permission(self) -> None:
        manager = FakeManager([FakeTask(7)])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}), \
                patch.object(self.views, "check_business_read_permissions"):
            response = self.views.task_preview(FakeRequest(FakeUser(True, 7)), "task-1")
        self.assertEqual(response.data["preview"], {"schema_version": 1, "lines": []})
        self.assertEqual(response.data["snapshot_digest"], "digest")

    def test_decision_preview_without_quote_is_read_only(self) -> None:
        task = FakeTask(7)
        task.preview = {"parts": [{"part_id": 2, "name": "Part 2", "units": "",
                                   "preliminary_shortage": {"value": "5"}}]}
        manager = FakeManager([task])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}), \
                patch.object(self.views, "check_business_read_permissions"), \
                patch.object(self.views, "supplier_part_snapshot") as supplier_read:
            response = self.views.task_decision_preview(FakeRequest(FakeUser(True, 7)), "task-1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "needs_review")
        self.assertEqual(response.data["rows"][0]["preliminary_shortage"], "5")
        self.assertIsNone(response.data["rows"][0]["order_quantity"])
        self.assertIsNone(response.data["rows"][0]["estimated_total"])
        supplier_read.assert_not_called()

    def test_decision_preview_checks_owner_and_current_permissions(self) -> None:
        from inventree_procurement_plugin.service import BusinessReadDenied
        from inventree_procurement_plugin.quote_service import SupplierPartMissing

        task = FakeTask(7)
        task.preview = {"parts": [{"part_id": 2, "name": "Part 2", "units": "",
                                   "preliminary_shortage": {"value": "5"}}]}
        task.quote = {"supplier_part_id": 9, "part_id": 2, "snapshot_digest": "digest",
                      "source_sha256": "a" * 64,
                      "source_text": "SKU X", "extracted": {
                          "supplier_name": None, "sku": None, "unit_price": None,
                          "currency": None, "price_unit": None, "pack_quantity": None,
                          "valid_until": None, "lead_time": None}}
        manager = FakeManager([task])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        request = FakeRequest(FakeUser(True, 7))
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}):
            with self.assertRaises(LookupError):
                self.views.task_decision_preview(FakeRequest(FakeUser(True, 8)), "task-1")
            with patch.object(self.views, "check_business_read_permissions", side_effect=BusinessReadDenied()):
                self.assertEqual(self.views.task_decision_preview(request, "task-1").status_code, 403)
            with patch.object(self.views, "check_business_read_permissions"), \
                    patch.object(self.views, "supplier_part_snapshot", side_effect=BusinessReadDenied()):
                self.assertEqual(self.views.task_decision_preview(request, "task-1").status_code, 403)
            with patch.object(self.views, "check_business_read_permissions"), \
                    patch.object(self.views, "supplier_part_snapshot", side_effect=SupplierPartMissing()):
                self.assertEqual(self.views.task_decision_preview(request, "task-1").status_code, 404)
            with patch.object(self.views, "check_business_read_permissions"), \
                    patch.object(self.views, "supplier_part_snapshot", return_value={
                        "part_id": 2, "supplier_name": "Supplier", "sku": "X",
                        "part_units": "", "pack_quantity_native": "5"}) as supplier_read:
                response = self.views.task_decision_preview(request, "task-1")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["rows"][0]["supplier_part_id"], 9)
            supplier_read.assert_called_once_with(request.user, 9, task.preview)

    def test_explanation_requires_generation_and_reuses_matching_cache(self) -> None:
        task = FakeTask(7)
        manager = FakeManager([task])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        request = FakeRequest(FakeUser(True, 7))
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}), \
                patch.object(self.views, "check_business_read_permissions"):
            self.assertEqual(self.views.task_explanation(request, "task-1").status_code, 409)
            task.explanation = {"text": "Cached", "snapshot_digest": "digest"}
            self.assertEqual(self.views.task_explanation(request, "task-1").data["explanation"]["text"], "Cached")
            request.method = "POST"
            self.assertEqual(self.views.task_explanation(request, "task-1").data["explanation"]["text"], "Cached")
            task.snapshot_digest = "new-digest"
            request.method = "GET"
            self.assertEqual(self.views.task_explanation(request, "task-1").status_code, 409)

    def test_explanation_denies_other_owner_and_revoked_business_permission(self) -> None:
        from inventree_procurement_plugin.service import BusinessReadDenied

        manager = FakeManager([FakeTask(7)])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}):
            with self.assertRaises(LookupError):
                self.views.task_explanation(FakeRequest(FakeUser(True, 8)), "task-1")
            with patch.object(self.views, "check_business_read_permissions", side_effect=BusinessReadDenied()):
                self.assertEqual(self.views.task_explanation(FakeRequest(FakeUser(True, 7)), "task-1").status_code, 403)

    def test_explanation_unexpected_failure_releases_generation_claim(self) -> None:
        from inventree_procurement_plugin import explanation

        task = FakeTask(7)
        manager = FakeManager([task])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        request = FakeRequest(FakeUser(True, 7), method="POST")
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}), \
                patch.object(self.views, "check_business_read_permissions"), \
                patch.object(explanation, "generate_explanation", side_effect=RuntimeError("secret provider details")):
            response = self.views.task_explanation(request, "task-1")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("secret", str(response.data))
        self.assertIsNone(task.explanation_run_id)
        self.assertIsNone(task.explanation_started_at)

    def test_post_validates_one_build_id_and_creates_task(self) -> None:
        task = FakeTask(7)
        request = FakeRequest(FakeUser(True, 7), method="POST", body=json.dumps({"build_ids": [10]}).encode())
        with patch.object(self.views, "check_business_read_permissions"), \
                patch.object(self.views, "create_analysis_task", return_value=task) as create:
            response = self.views.tasks(request)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["task"]["build_ids"], [10])
        self.assertEqual(response.data["preview_url"], "/plugin/inventree_procurement/tasks/task-1/preview/")
        create.assert_called_once_with(request.user, 10)
        for invalid in ([], [0], [-1], [True], [10, 11], ["10"], [2_147_483_648]):
            request.body = json.dumps({"build_ids": invalid}).encode()
            with patch.object(self.views, "check_business_read_permissions"):
                self.assertEqual(self.views.tasks(request).status_code, 400)

    def test_business_permission_failure_returns_403_before_post_parse(self) -> None:
        from inventree_procurement_plugin.service import BusinessReadDenied

        request = FakeRequest(FakeUser(True, 7), method="POST", body=b"invalid")
        with patch.object(self.views, "check_business_read_permissions", side_effect=BusinessReadDenied()):
            response = self.views.tasks(request)
        self.assertEqual(response.status_code, 403)

    def test_revoked_business_permission_blocks_saved_preview(self) -> None:
        from inventree_procurement_plugin.service import BusinessReadDenied

        manager = FakeManager([FakeTask(7)])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}), \
                patch.object(self.views, "check_business_read_permissions", side_effect=BusinessReadDenied()):
            response = self.views.task_preview(FakeRequest(FakeUser(True, 7)), "task-1")
        self.assertEqual(response.status_code, 403)

    def test_missing_build_returns_404(self) -> None:
        from inventree_procurement_plugin.service import BuildMissing

        request = FakeRequest(FakeUser(True, 7), method="POST", body=b'{"build_ids":[10]}')
        with patch.object(self.views, "check_business_read_permissions"), \
                patch.object(self.views, "create_analysis_task", side_effect=BuildMissing()):
            response = self.views.tasks(request)
        self.assertEqual(response.status_code, 404)

    def test_quote_input_rejects_invalid_ids_and_oversized_text(self) -> None:
        for supplier_id, source in ((True, "报价"), (0, "报价"), (1, " "),
                                    (1, "字" * 3000)):
            request = FakeRequest(FakeUser(True, 7), method="POST",
                                  body=json.dumps({"supplier_part_id": supplier_id,
                                                   "text": source}).encode())
            with self.assertRaises(ValueError):
                self.views._quote_input(request)

        escaped_source = "字" * 2000  # 6 KiB of text, 12 KiB after JSON escaping.
        request = FakeRequest(
            FakeUser(True, 7), method="POST",
            body=json.dumps({"supplier_part_id": 1, "text": escaped_source}).encode(),
        )
        self.assertEqual(self.views._quote_input(request), (1, escaped_source))

    def test_quote_owner_and_supplier_permissions_precede_model(self) -> None:
        from inventree_procurement_plugin.service import BusinessReadDenied

        task = FakeTask(7)
        manager = FakeManager([task])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        request = FakeRequest(FakeUser(True, 7), method="POST",
                              body=b'{"supplier_part_id":1,"text":"USD 10"}')
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}), \
                patch.object(self.views, "check_business_read_permissions"), \
                patch.object(self.views, "supplier_part_snapshot", side_effect=BusinessReadDenied()), \
                patch.object(self.views, "extract_quote") as model:
            response = self.views.task_quote(request, "task-1")
            self.assertEqual(response.status_code, 403)
            with self.assertRaises(LookupError):
                self.views.task_quote(FakeRequest(FakeUser(True, 8)), "task-1")
        model.assert_not_called()

    def test_quote_creation_is_cached_and_source_cannot_change(self) -> None:
        task = FakeTask(7)
        task.preview = {"parts": [{"part_id": 3}]}
        manager = FakeManager([task])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        source = "SKU X-2"
        request = FakeRequest(FakeUser(True, 7), method="POST",
                              body=json.dumps({"supplier_part_id": 1, "text": source}).encode())
        snapshot = {"part_id": 3, "supplier_name": "Acme", "sku": "X-2",
                    "pack_quantity_native": None}
        extracted = {field: None for field in ("supplier_name", "sku", "unit_price",
                    "currency", "price_unit", "pack_quantity", "valid_until", "lead_time")}
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}), \
                patch.object(self.views, "check_business_read_permissions"), \
                patch.object(self.views, "check_supplier_read_permissions"), \
                patch.object(self.views, "supplier_part_snapshot", return_value=snapshot), \
                patch.object(self.views, "extract_quote", return_value={
                    "extracted": extracted, "tool_calls": [], "model": "deepseek-flash"}) as model:
            first = self.views.task_quote(request, "task-1")
            second = self.views.task_quote(request, "task-1")
            read = self.views.task_quote(FakeRequest(FakeUser(True, 7)), "task-1")
            request.body = b'{"supplier_part_id":1,"text":"changed"}'
            changed = self.views.task_quote(request, "task-1")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(read.status_code, 200)
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(first.data["quote"]["source_text"], source)
        self.assertEqual(first.data["quote"]["part_id"], 3)
        self.assertEqual(first.data["quote"]["snapshot_digest"], "digest")
        model.assert_called_once()


if __name__ == "__main__":
    unittest.main()
