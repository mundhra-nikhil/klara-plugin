"""FastAPI Depends() factories — auth, RBAC, and shared dependencies."""

from typing import List
import structlog

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.models.enum.user_role import UserRole
from src.models.dto.schemas.auth import UserClaims
from src.services.auth import auth_service
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()
security = HTTPBearer()


class NotFoundError(HTTPException):
    def __init__(self, detail: str = "Resource not found"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "You do not have permission to perform this action"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Resource conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class BadRequestError(HTTPException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserClaims:
    """Extract and validate the current user from the JWT token."""
    logger.info("Entering get_current_user")
    token = credentials.credentials
    user = await auth_service.verify_access_token(token)
    if user is None:
        logger.warning("Token verification failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Bind user context for logging (extract org from email domain)
    org_name = user.email.split('@')[1] if '@' in user.email else '-'
    structlog.contextvars.bind_contextvars(org_name=org_name)
    
    logger.info("Exiting get_current_user", user_id=str(user.id))
    return user


def require_roles(allowed_roles: List[UserRole]):
    """Dependency that checks if the current user has one of the allowed roles."""

    async def role_checker(current_user=Depends(get_current_user)):
        logger.info("Checking user role", user_id=str(current_user.id), user_role=current_user.role, allowed_roles=[r.value for r in allowed_roles])
        if current_user.role not in [r.value for r in allowed_roles]:
            logger.warning("Insufficient permissions", user_id=str(current_user.id), user_role=current_user.role)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return role_checker
