"""Inject X-Correlation-ID into every request/response."""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
import structlog

from src.core.constants import CORRELATION_ID_HEADER
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER, str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        # Clear and bind context vars for this request
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=correlation_id,
            org_name=request.headers.get("X-Org-Name", "-"),
        )

        logger.info("Incoming request", method=request.method, path=request.url.path)
        
        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        
        logger.info("Request completed", method=request.method, path=request.url.path, status_code=response.status_code)
        return response
