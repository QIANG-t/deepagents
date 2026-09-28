"""Exercise plugin view guards with small Django stand-ins, without a server."""

from __future__ import annotations

import importlib
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


class FakeTask:
    def __init__(self, owner_id: int):
        self.id = "task-1"
        self.owner_id = owner_id
        self.status = "created"
        self.build_ids = [10]
        self.created_at = datetime(2026, 9, 28, tzinfo=timezone.utc)
        self.updated_at = self.created_at


class ViewTests(unittest.TestCase):
    def setUp(self) -> None:
        django = types.ModuleType("django")
        django.__path__ = []
        http = types.ModuleType("django.http")
        http.HttpRequest = FakeRequest
        http.JsonResponse = FakeJsonResponse
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
        http_decorators = types.ModuleType("django.views.decorators.http")
        http_decorators.require_GET = lambda function: function
        modules = {
            "django": django,
            "django.http": http,
            "django.shortcuts": shortcuts,
            "django.views": views_package,
            "django.views.decorators": decorators,
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

    def test_health_reports_writes_disabled(self) -> None:
        response = self.views.health(FakeRequest(FakeUser(True, 7)))
        self.assertEqual(response.data, {"status": "ok", "writes_enabled": False})

    def test_task_list_filters_by_owner(self) -> None:
        manager = FakeManager([FakeTask(7), FakeTask(8)])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}):
            response = self.views.tasks(FakeRequest(FakeUser(True, 7)))
        self.assertEqual(manager.owner_filters, [7])
        self.assertEqual(len(response.data["tasks"]), 1)
        self.assertEqual(response.data["tasks"][0]["build_ids"], [10])

    def test_task_detail_hides_another_users_task(self) -> None:
        manager = FakeManager([FakeTask(7)])
        models = types.ModuleType("inventree_procurement_plugin.models")
        models.ProcurementTask = types.SimpleNamespace(objects=manager)
        with patch.dict(sys.modules, {"inventree_procurement_plugin.models": models}):
            owned = self.views.task_detail(FakeRequest(FakeUser(True, 7)), "task-1")
            self.assertEqual(owned.data["task"]["id"], "task-1")
            with self.assertRaises(LookupError):
                self.views.task_detail(FakeRequest(FakeUser(True, 8)), "task-1")


if __name__ == "__main__":
    unittest.main()
