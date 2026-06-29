"""Global exception handlers for FastAPI/Starlette."""

from datetime import datetime, timezone

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with consistent error envelope."""
    correlation_id = getattr(request.state, "correlation_id", None) if hasattr(request, "state") else None

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "statusCode": exc.status_code,
            "message": exc.detail,
            "error": type(exc).__name__,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": str(request.url.path),
            "traceId": correlation_id,
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    correlation_id = getattr(request.state, "correlation_id", None) if hasattr(request, "state") else None
    logger.error("unhandled_exception", error=str(exc), path=str(request.url.path))

    return JSONResponse(
        status_code=500,
        content={
            "statusCode": 500,
            "message": "Internal server error",
            "error": "InternalServerError",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "path": str(request.url.path),
            "traceId": correlation_id,
        },
    )
