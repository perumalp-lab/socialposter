"""Pagination helper for SQLAlchemy queries."""

from __future__ import annotations

from typing import Any, Callable


def paginate_query(
    query,
    page: int,
    per_page: int = 20,
    max_per_page: int = 100,
    *,
    serializer: Callable | None = None,
) -> dict[str, Any]:
    """Apply offset/limit pagination and return a standard response dict.

    Parameters
    ----------
    query:
        A SQLAlchemy query (not yet executed).
    page:
        1-based page number.
    per_page:
        Items per page (clamped to *max_per_page*).
    serializer:
        Optional callable applied to each item.  When ``None`` the raw
        model instances are returned in ``"items"``.
    """
    per_page = min(per_page, max_per_page)
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    if serializer is not None:
        items = [serializer(item) for item in items]
    return {
        "items": items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": (total + per_page - 1) // per_page,
    }
