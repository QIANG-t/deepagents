"""Authenticated task creation and read-only factual previews."""

import json
import uuid
from datetime import timedelta

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .access import read_status
from .service import BusinessReadDenied, BuildMissing, check_business_read_permissions, create_analysis_task

MAX_BUILD_ID = 2_147_483_647


def _denied(request: HttpRequest) -> JsonResponse | None:
    if read_status(request.user) == 200:
        return None
    return JsonResponse({"error": "Authentication required", "code": "unauthenticated"}, status=401)


def _business_denial(request: HttpRequest) -> JsonResponse | None:
    try:
        check_business_read_permissions(request.user)
    except BusinessReadDenied:
        return JsonResponse({"error": "Build, build-line, part, and stock view permissions are required", "code": "forbidden"}, status=403)
    return None


def _task_data(task: object) -> dict[str, object]:
    return {
        "id": str(task.id),
        "status": task.status,
        "build_ids": task.build_ids,
        "snapshot_digest": task.snapshot_digest,
        "preview_available": bool(task.preview),
        "analyzed_at": task.analyzed_at.isoformat() if task.analyzed_at else None,
        "created_at": task.created_at.isoformat(),
        "updated_at": task.updated_at.isoformat(),
    }


def _build_id(request: HttpRequest) -> int:
    if request.content_type != "application/json" or len(request.body) > 4096:
        raise ValueError("A small application/json body is required")
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeDecodeError) as error:
        raise ValueError("Malformed JSON") from error
    if not isinstance(payload, dict) or set(payload) != {"build_ids"}:
        raise ValueError("Expected only build_ids")
    build_ids = payload["build_ids"]
    if (not isinstance(build_ids, list) or len(build_ids) != 1 or
            isinstance(build_ids[0], bool) or not isinstance(build_ids[0], int) or
            not 0 < build_ids[0] <= MAX_BUILD_ID):
        raise ValueError("build_ids must contain exactly one positive 32-bit integer")
    return build_ids[0]


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Return readiness to a logged-in user; purchase writes remain disabled."""
    denial = _denied(request)
    if denial is not None:
        return denial
    return JsonResponse({"status": "ok", "writes_enabled": False})


@csrf_exempt  # Authenticate first; the only POST branch calls the protected helper below.
@require_http_methods(["GET", "POST"])
def tasks(request: HttpRequest) -> JsonResponse:
    """List owned tasks or persist one authorized build analysis."""
    denial = _denied(request)
    if denial is not None:
        return denial
    denial = _business_denial(request)
    if denial is not None:
        return denial
    if request.method == "POST":
        return _create_task(request)
    from .models import ProcurementTask

    rows = ProcurementTask.objects.filter(owner_id=request.user.pk).order_by("-created_at")[:100]
    return JsonResponse({"tasks": [_task_data(task) for task in rows]})


@csrf_protect
def _create_task(request: HttpRequest) -> JsonResponse:
    try:
        build_id = _build_id(request)
    except ValueError as error:
        return JsonResponse({"error": str(error), "code": "invalid_request"}, status=400)
    try:
        task = create_analysis_task(request.user, build_id)
    except BusinessReadDenied:
        return JsonResponse({"error": "Business read permission denied", "code": "forbidden"}, status=403)
    except BuildMissing:
        return JsonResponse({"error": "Selected build not found", "code": "build_not_found"}, status=404)
    return JsonResponse({
        "task": _task_data(task),
        "preview_url": f"/plugin/inventree_procurement/tasks/{task.id}/preview/",
    }, status=201)


@require_GET
def task_detail(request: HttpRequest, task_id: str) -> JsonResponse:
    """Return metadata for one owned task."""
    denial = _denied(request)
    if denial is not None:
        return denial
    from .models import ProcurementTask

    task = get_object_or_404(ProcurementTask, pk=task_id, owner_id=request.user.pk)
    denial = _business_denial(request)
    if denial is not None:
        return denial
    return JsonResponse({"task": _task_data(task)})


@require_GET
def task_preview(request: HttpRequest, task_id: str) -> JsonResponse:
    """Return the persisted facts without querying current business objects."""
    denial = _denied(request)
    if denial is not None:
        return denial
    from .models import ProcurementTask

    task = get_object_or_404(ProcurementTask, pk=task_id, owner_id=request.user.pk)
    denial = _business_denial(request)
    if denial is not None:
        return denial
    if not task.preview:
        return JsonResponse({"error": "Preview is not available", "code": "preview_unavailable"}, status=409)
    return JsonResponse({
        "task_id": str(task.id),
        "snapshot_digest": task.snapshot_digest,
        "analyzed_at": task.analyzed_at.isoformat() if task.analyzed_at else None,
        "preview": task.preview,
    })


@csrf_exempt  # Authenticate and check ownership before the protected POST helper.
@require_http_methods(["GET", "POST"])
def task_explanation(request: HttpRequest, task_id: str) -> JsonResponse:
    """Read or generate a cached explanation of an owned persisted snapshot."""
    denial = _denied(request)
    if denial is not None:
        return denial
    from .models import ProcurementTask

    task = get_object_or_404(ProcurementTask, pk=task_id, owner_id=request.user.pk)
    denial = _business_denial(request)
    if denial is not None:
        return denial
    if not task.preview or not task.snapshot_digest:
        return JsonResponse({"error": "Preview is not available", "code": "preview_unavailable"}, status=409)
    if request.method == "POST":
        return _generate_task_explanation(request, task_id)
    if not task.explanation or task.explanation.get("snapshot_digest") != task.snapshot_digest:
        return JsonResponse({"error": "Explanation has not been generated", "code": "explanation_unavailable"}, status=409)
    return JsonResponse({"explanation": task.explanation})


@csrf_protect
def _generate_task_explanation(request: HttpRequest, task_id: str) -> JsonResponse:
    """Claim generation briefly, then release the DB lock during the model call."""
    if request.body:
        return JsonResponse({"error": "Request body must be empty", "code": "invalid_request"}, status=400)
    from .explanation import ExplanationFailed, ExplanationUnavailable, generate_explanation
    from .models import ProcurementTask

    with transaction.atomic():
        task = ProcurementTask.objects.select_for_update().get(pk=task_id, owner_id=request.user.pk)
        if task.explanation and task.explanation.get("snapshot_digest") == task.snapshot_digest:
            return JsonResponse({"explanation": task.explanation})
        now = timezone.now()
        if task.explanation_started_at and task.explanation_started_at > now - timedelta(seconds=60):
            return JsonResponse({"error": "Explanation generation is in progress", "code": "explanation_busy"}, status=409)
        run_id = uuid.uuid4()
        task.explanation_run_id = run_id
        task.explanation_started_at = now
        task.save(update_fields=["explanation_run_id", "explanation_started_at", "updated_at"])
        preview = task.preview
        digest = task.snapshot_digest

    try:
        explanation = generate_explanation(preview, digest)
    except (ExplanationUnavailable, ExplanationFailed) as error:
        _release_explanation_claim(task_id, request.user.pk, run_id)
        if isinstance(error, ExplanationUnavailable):
            return JsonResponse({"error": "Explanation service is unavailable", "code": "explanation_unavailable"}, status=503)
        return JsonResponse({"error": "Explanation generation failed", "code": "explanation_failed"}, status=502)
    except Exception:
        _release_explanation_claim(task_id, request.user.pk, run_id)
        return JsonResponse({"error": "Explanation generation failed", "code": "explanation_failed"}, status=502)

    with transaction.atomic():
        task = ProcurementTask.objects.select_for_update().get(pk=task_id, owner_id=request.user.pk)
        if task.explanation_run_id != run_id or task.snapshot_digest != digest:
            return JsonResponse({"error": "Snapshot changed during generation", "code": "snapshot_changed"}, status=409)
        explanation["generated_at"] = timezone.now().isoformat()
        task.explanation = explanation
        task.explanation_started_at = None
        task.explanation_run_id = None
        task.save(update_fields=["explanation", "explanation_started_at", "explanation_run_id", "updated_at"])
    return JsonResponse({"explanation": explanation})


def _release_explanation_claim(task_id: str, owner_id: int, run_id: uuid.UUID) -> None:
    from .models import ProcurementTask

    with transaction.atomic():
        task = ProcurementTask.objects.select_for_update().get(pk=task_id, owner_id=owner_id)
        if task.explanation_run_id == run_id:
            task.explanation_started_at = None
            task.explanation_run_id = None
            task.save(update_fields=["explanation_started_at", "explanation_run_id", "updated_at"])
