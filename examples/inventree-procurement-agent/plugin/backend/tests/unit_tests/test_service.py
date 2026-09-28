"""Permission gate checks for ORM-backed analysis without importing Django."""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inventree_procurement_plugin.service import BusinessReadDenied, create_analysis_task  # noqa: E402


def package(name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__path__ = []
    return module


class PermissionGateTests(unittest.TestCase):
    def test_denied_stock_view_stops_before_build_query(self) -> None:
        build = type("Build", (), {"objects": MagicMock()})
        build_line = type("BuildLine", (), {})
        part = type("Part", (), {})
        stock_item = type("StockItem", (), {})
        build_models = types.ModuleType("build.models")
        build_models.Build = build
        build_models.BuildLine = build_line
        part_models = types.ModuleType("part.models")
        part_models.Part = part
        stock_models = types.ModuleType("stock.models")
        stock_models.StockItem = stock_item
        permissions = types.ModuleType("users.permissions")
        seen = []

        def check(user, model, action):
            seen.append((model, action))
            return model is not stock_item

        permissions.check_user_permission = check
        modules = {
            "build": package("build"), "build.models": build_models,
            "part": package("part"), "part.models": part_models,
            "stock": package("stock"), "stock.models": stock_models,
            "users": package("users"), "users.permissions": permissions,
        }
        with patch.dict(sys.modules, modules):
            with self.assertRaises(BusinessReadDenied):
                create_analysis_task(object(), 10)
        self.assertEqual([model for model, _ in seen], [build, build_line, part, stock_item])
        self.assertTrue(all(action == "view" for _, action in seen))
        build.objects.get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
