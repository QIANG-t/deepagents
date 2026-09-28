"""Offline URL and panel registration checks using framework stand-ins."""

from __future__ import annotations

import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class FakePluginBase:
    @property
    def slug(self) -> str:
        return self.SLUG

    def plugin_static_file(self, name: str) -> str:
        return f"/static/plugins/{self.slug}/{name}"


class PluginContractTests(unittest.TestCase):
    def setUp(self) -> None:
        django = types.ModuleType("django")
        django.__path__ = []
        urls = types.ModuleType("django.urls")
        urls.path = lambda route, view, name: (route, view, name)
        plugin_framework = types.ModuleType("plugin")
        plugin_framework.__path__ = []
        plugin_framework.InvenTreePlugin = FakePluginBase
        mixins = types.ModuleType("plugin.mixins")
        mixins.AppMixin = type("AppMixin", (), {})
        mixins.UrlsMixin = type("UrlsMixin", (), {})
        mixins.UserInterfaceMixin = type("UserInterfaceMixin", (), {})
        views = types.ModuleType("inventree_procurement_plugin.views")
        views.health = lambda request: None
        views.tasks = lambda request: None
        views.task_detail = lambda request, task_id: None
        views.task_preview = lambda request, task_id: None
        self.package = importlib.import_module("inventree_procurement_plugin")
        self.old_views = getattr(self.package, "views", None)
        self.package.views = views
        self.modules = patch.dict(sys.modules, {
            "django": django,
            "django.urls": urls,
            "plugin": plugin_framework,
            "plugin.mixins": mixins,
            "inventree_procurement_plugin.views": views,
        })
        self.modules.start()
        sys.modules.pop("inventree_procurement_plugin.plugin", None)
        self.module = importlib.import_module("inventree_procurement_plugin.plugin")
        self.instance = self.module.InvenTreeProcurementAgent()

    def tearDown(self) -> None:
        sys.modules.pop("inventree_procurement_plugin.plugin", None)
        self.modules.stop()
        if self.old_views is None:
            delattr(self.package, "views")
        else:
            self.package.views = self.old_views

    def test_slug_and_task_routes_are_registered(self) -> None:
        self.assertEqual(self.instance.SLUG, "inventree_procurement")
        self.assertEqual([route for route, _, _ in self.instance.setup_urls()], [
            "health/", "tasks/", "tasks/<uuid:task_id>/", "tasks/<uuid:task_id>/preview/"
        ])

    def test_panel_requires_login_context_and_bundle(self) -> None:
        missing = MagicMock()
        missing.joinpath.return_value.is_file.return_value = False
        with patch.object(self.module, "files", return_value=missing):
            self.assertEqual(self.instance.get_ui_panels(
                types.SimpleNamespace(user=types.SimpleNamespace(is_authenticated=True, pk=1)),
                {"target_model": "purchasing"}
            ), [])
        present = MagicMock()
        present.joinpath.return_value.is_file.return_value = True
        anonymous = types.SimpleNamespace(user=types.SimpleNamespace(is_authenticated=False, pk=None))
        authorized = types.SimpleNamespace(user=types.SimpleNamespace(is_authenticated=True, pk=1))
        with patch.object(self.module, "files", return_value=present):
            self.assertEqual(self.instance.get_ui_panels(anonymous, {"target_model": "purchasing"}), [])
            self.assertEqual(self.instance.get_ui_panels(authorized, {"target_model": "manufacturing"}), [])
            panel = self.instance.get_ui_panels(authorized, {"target_model": "purchasing"})[0]
        self.assertEqual(panel["source"],
                         "/static/plugins/inventree_procurement/procurement-panel.js:RenderProcurementPanel")


if __name__ == "__main__":
    unittest.main()
