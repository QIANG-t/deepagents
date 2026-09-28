"""Framework-free access policy shared by HTTP views and offline tests."""

from __future__ import annotations

from typing import Protocol


class Viewer(Protocol):
    """User fields required for authenticated task reads."""

    is_authenticated: bool
    pk: int | None


def read_status(user: Viewer | None, owner_id: int | None = None) -> int:
    """Return 200, 401, or 404 without revealing other users' task IDs."""
    if user is None or not user.is_authenticated or user.pk is None:
        return 401
    if owner_id is not None and user.pk != owner_id:
        return 404
    return 200
