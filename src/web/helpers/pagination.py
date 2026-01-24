"""
Pagination Helpers - Consistent pagination across all list endpoints.

Provides:
- Standard pagination metadata structure
- Reusable pagination response builder
- Query parameter helpers

Resolves Audit Finding: "Inconsistent pagination implementation"
"""

from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field
from fastapi import Query

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Standard pagination metadata."""
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Number of items skipped")
    total_count: int = Field(..., description="Total number of items available")
    has_next: bool = Field(..., description="Whether there are more items after this page")
    has_previous: bool = Field(..., description="Whether there are items before this page")
    page: int = Field(..., description="Current page number (1-indexed)")
    total_pages: int = Field(..., description="Total number of pages")


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Standard paginated response structure.

    Usage:
        @router.get("/items")
        async def list_items(
            limit: int = Query(50, ge=1, le=500),
            offset: int = Query(0, ge=0)
        ):
            items = get_items(limit=limit, offset=offset)
            total = count_items()
            return paginate(items, total, limit, offset)
    """
    data: List[Any] = Field(..., description="List of items for this page")
    pagination: PaginationMeta = Field(..., description="Pagination metadata")

    class Config:
        arbitrary_types_allowed = True


def paginate(
    items: List[Any],
    total_count: int,
    limit: int,
    offset: int,
    data_key: str = "data"
) -> dict:
    """
    Build a paginated response with consistent structure.

    Args:
        items: List of items for the current page
        total_count: Total number of items across all pages
        limit: Number of items requested per page
        offset: Number of items skipped
        data_key: Key name for the data list (default: "data")

    Returns:
        Dict with data and pagination metadata

    Example:
        >>> items = [{"id": 1}, {"id": 2}]
        >>> response = paginate(items, total_count=100, limit=10, offset=0)
        >>> response["pagination"]["has_next"]
        True
        >>> response["pagination"]["total_pages"]
        10
    """
    # Calculate pagination values
    page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = ((total_count + limit - 1) // limit) if limit > 0 else 1
    has_next = (offset + limit) < total_count
    has_previous = offset > 0

    pagination = PaginationMeta(
        limit=limit,
        offset=offset,
        total_count=total_count,
        has_next=has_next,
        has_previous=has_previous,
        page=page,
        total_pages=total_pages
    )

    return {
        data_key: items,
        "pagination": pagination.model_dump()
    }


def pagination_params(
    default_limit: int = 50,
    max_limit: int = 500,
):
    """
    Factory for common pagination query parameters.

    Usage:
        @router.get("/items")
        async def list_items(
            pagination = Depends(pagination_params())
        ):
            limit, offset = pagination["limit"], pagination["offset"]
            ...
    """
    def get_params(
        limit: int = Query(default_limit, ge=1, le=max_limit, description="Number of items to return"),
        offset: int = Query(0, ge=0, description="Number of items to skip"),
    ) -> dict:
        return {"limit": limit, "offset": offset}

    return get_params


# Convenience function for API responses that need backwards compatibility
def paginate_legacy(
    items: List[Any],
    total_count: int,
    limit: int,
    offset: int,
    items_key: str = "items",
    count_key: str = "count",
) -> dict:
    """
    Build a paginated response with legacy key names.

    For backwards compatibility with existing API consumers.

    Args:
        items: List of items for the current page
        total_count: Total number of items across all pages
        limit: Number of items requested per page
        offset: Number of items skipped
        items_key: Key name for the items list
        count_key: Key name for the current page count

    Returns:
        Dict with items, count, and pagination metadata
    """
    page = (offset // limit) + 1 if limit > 0 else 1
    total_pages = ((total_count + limit - 1) // limit) if limit > 0 else 1

    return {
        items_key: items,
        count_key: len(items),
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
        "page": page,
        "total_pages": total_pages,
        "has_next": (offset + limit) < total_count,
        "has_previous": offset > 0,
    }
