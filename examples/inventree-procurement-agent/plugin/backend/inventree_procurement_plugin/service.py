"""ORM boundary for authorized, durable single-build analysis."""

from __future__ import annotations

import hashlib
import json

from .facts import build_facts


class BusinessReadDenied(PermissionError):
    """The current user cannot view every model required for the preview."""


class BuildMissing(LookupError):
    """The selected build does not exist."""


def check_business_read_permissions(user: object) -> None:
    """Require the same model view rights as InvenTree's read APIs."""
    from build.models import Build, BuildLine
    from part.models import Part
    from stock.models import StockItem
    from users.permissions import check_user_permission

    for model in (Build, BuildLine, Part, StockItem):
        if not check_user_permission(user, model, "view"):
            raise BusinessReadDenied("Build, build-line, part, and stock view permissions are required")


def create_analysis_task(user: object, build_id: int):
    """Read one build after permission checks and persist a factual snapshot."""
    check_business_read_permissions(user)
    from django.db import transaction
    from django.utils import timezone
    from build.models import Build, BuildLine
    from build.serializers import BuildLineSerializer
    from .models import ProcurementTask

    with transaction.atomic():
        try:
            build = Build.objects.get(pk=build_id)
        except Build.DoesNotExist as error:
            raise BuildMissing("Selected build was not found") from error
        lines = BuildLineSerializer.annotate_queryset(
            BuildLine.objects.filter(build_id=build_id), build=build
        ).order_by("pk")
        preview = build_facts(build, lines)
        payload = json.dumps(preview, sort_keys=True, separators=(",", ":"))
        task = ProcurementTask.objects.create(
            owner=user,
            status="analyzed",
            build_ids=[build_id],
            preview=preview,
            analyzed_at=timezone.now(),
            snapshot_digest=hashlib.sha256(payload.encode()).hexdigest(),
        )
    return task
