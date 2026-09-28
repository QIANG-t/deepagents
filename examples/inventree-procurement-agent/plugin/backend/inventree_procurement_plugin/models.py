"""Durable task metadata; no approval or purchase execution is stored here yet."""

import uuid

from django.conf import settings
from django.db import models


class ProcurementTask(models.Model):
    """A task owned by one user; created only through trusted server-side code."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="procurement_agent_tasks")
    status = models.CharField(max_length=32, default="created")
    build_ids = models.JSONField(default=list)
    snapshot_digest = models.CharField(max_length=64, blank=True)
    plan_digest = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    @classmethod
    def check_user_permission(cls, user: object, permission: str) -> bool:
        """Deny generic model access; plugin views apply owner checks explicitly."""
        return False
