"""Authenticated GET-only endpoints for health and owned task metadata."""

from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .access import read_status


def _denied(request: HttpRequest) -> JsonResponse | None:
    if read_status(request.user) == 200:
        return None
    return JsonResponse({"error": "Authentication required"}, status=401)


def _task_data(task: object) -> dict[str, object]:
    return {
        "id": str(task.id),
        "status": task.status,
        "build_ids": task.build_ids,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Return plugin readiness to a logged-in user only."""
    denial = _denied(request)
    if denial is not None:
        return denial
    return JsonResponse({"status": "ok", "writes_enabled": False})


@require_GET
def tasks(request: HttpRequest) -> JsonResponse:
    """List only task metadata owned by the current user."""
    denial = _denied(request)
    if denial is not None:
        return denial
    from .models import ProcurementTask

    rows = ProcurementTask.objects.filter(owner_id=request.user.pk).order_by("-created_at")[:100]
    return JsonResponse({"tasks": [_task_data(task) for task in rows]})


@require_GET
def task_detail(request: HttpRequest, task_id: str) -> JsonResponse:
    """Return 404 for unknown or other-user task IDs."""
    denial = _denied(request)
    if denial is not None:
        return denial
    from .models import ProcurementTask

    task = get_object_or_404(ProcurementTask, pk=task_id, owner_id=request.user.pk)
    return JsonResponse({"task": _task_data(task)})
