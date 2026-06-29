from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime


class StandardAPIResponse(BaseModel):
    """Standard API response envelope."""
    status_code: int
    message: str
    data: Optional[Any] = None
    timestamp: datetime
    path: Optional[str] = None
    trace_id: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""
    status_code: int
    message: str
    error: str
    timestamp: datetime
    path: str
    trace_id: Optional[str] = None
