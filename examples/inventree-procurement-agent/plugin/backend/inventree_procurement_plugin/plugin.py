"""InvenTree URL, app, and UI plugin entry point."""

from importlib.resources import files

from django.urls import path

from plugin import InvenTreePlugin
from plugin.mixins import AppMixin, UrlsMixin, UserInterfaceMixin

from . import views
from .access import read_status


class InvenTreeProcurementAgent(AppMixin, UrlsMixin, UserInterfaceMixin, InvenTreePlugin):
    """Read-only procurement plugin; no approval or PO write URLs exist."""

    NAME = "InvenTreeProcurementAgent"
    SLUG = "inventree_procurement"
    TITLE = "Procurement Agent Tasks"
    DESCRIPTION = "Read-only task integration spike for procurement planning"
    AUTHOR = "InvenTree procurement agent contributors"
    VERSION = "0.1.0"

    def setup_urls(self):
        """Expose authenticated health and task reads under the plugin slug."""
        return [
            path("health/", views.health, name="health"),
            path("tasks/", views.tasks, name="tasks"),
            path("tasks/<uuid:task_id>/", views.task_detail, name="task-detail"),
        ]

    def get_ui_panels(self, request, context, **kwargs):
        """Show the read-only panel on purchasing pages when its bundle exists."""
        if read_status(getattr(request, "user", None)) != 200:
            return []
        if (context or {}).get("target_model") != "purchasing":
            return []
        bundle = files("inventree_procurement_plugin").joinpath(
            "static", "procurement-panel.js"
        )
        if not bundle.is_file():
            return []
        return [{
            "key": "procurement-agent-tasks",
            "title": "Procurement tasks",
            "icon": "ti:clipboard-list:outline",
            "source": self.plugin_static_file("procurement-panel.js:RenderProcurementPanel"),
        }]
