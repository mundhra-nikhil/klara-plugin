"""Cursor-based pagination helpers."""

from typing import Optional
from pydantic import BaseModel


class PaginationParams(BaseModel):
    cursor: Optional[str] = None
    limit: int = 20


class PaginatedResponse(BaseModel):
    data: list
    next_cursor: Optional[str] = None
    total: Optional[int] = None
