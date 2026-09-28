"""Django app registration for the plugin's durable task record."""

from django.apps import AppConfig


class ProcurementPluginConfig(AppConfig):
    """Register the package as a Django app when AppMixin is enabled."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "inventree_procurement_plugin"
    verbose_name = "Procurement Agent Tasks"
