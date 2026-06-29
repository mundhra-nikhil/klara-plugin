"""Azure AD user validation and upsert service.
Delegates to auth_service for core Azure AD operations."""

from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dao.user import User
from src.services.auth.auth_service import upsert_user_from_azure, validate_azure_ad_token
