"""Microsoft Graph OAuth authentication service for M365 integration."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from urllib.parse import urlencode

from msal import ConfidentialClientApplication, PublicClientApplication
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger_with_context
from src.configs.config import settings
from src.services.config.system_config_service import system_config_service

logger = get_logger_with_context()


class MicrosoftAuthService:
    """Service for Microsoft Graph OAuth authentication and token management."""

    # Microsoft Graph API endpoints
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    AUTHORITY = "https://login.microsoftonline.com/{tenant_id}"

    # OAuth Scopes for SharePoint and Word Online
    DEFAULT_SCOPES = [
        "https://graph.microsoft.com/Files.Read.All",
        "https://graph.microsoft.com/Files.ReadWrite.All",
        "https://graph.microsoft.com/Sites.Read.All",
        "https://graph.microsoft.com/Sites.ReadWrite.All",
        "https://graph.microsoft.com/User.Read.All",
    ]

    def __init__(self):
        """Initialize Microsoft authentication service."""
        self.tenant_id = settings.microsoft_tenant_id
        self.client_id = settings.microsoft_client_id
        self.client_secret = settings.microsoft_client_secret
        self.redirect_uri = settings.microsoft_redirect_uri

        # Determine if using confidential client (service-to-service) or public client (user delegation)
        self.app = None

    async def _ensure_app_initialized(self, db: AsyncSession):
        """Ensure MSAL application is initialized with current DB config."""
        config = await system_config_service.get_config(db, "ms365_integration")
        if config and config.value:
            self.client_id = config.value.get("clientId", self.client_id)
            self.client_secret = config.value.get("clientSecret", self.client_secret)
            self.tenant_id = config.value.get("tenantId", self.tenant_id)

        if self.client_secret:
            self.app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=self.AUTHORITY.format(tenant_id=self.tenant_id or "common"),
            )
        else:
            self.app = PublicClientApplication(
                client_id=self.client_id,
                authority=self.AUTHORITY.format(tenant_id=self.tenant_id or "common"),
            )

    async def get_authorization_url(self, db: AsyncSession, state: Optional[str] = None) -> Dict[str, str]:
        """
        Generate Microsoft OAuth authorization URL for user consent flow.

        Args:
            state: Optional state parameter for CSRF protection

        Returns:
            Dict with auth_url and state parameters
        """
        logger.info("generating_microsoft_auth_url", function="get_authorization_url")

        # Generate state if not provided
        if not state:
            state = secrets.token_urlsafe(32)

        await self._ensure_app_initialized(db)

        # Build authorization URL
        auth_url = self.app.get_authorization_request_url(
            scopes=self.DEFAULT_SCOPES,
            state=state,
            redirect_uri=self.redirect_uri,
        )

        logger.info("microsoft_auth_url_generated", function="get_authorization_url", state=state)

        return {
            "auth_url": auth_url,
            "state": state,
            "redirect_uri": self.redirect_uri,
        }

    async def acquire_token_from_code(self, db: AsyncSession, authorization_code: str, state: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.

        Args:
            authorization_code: OAuth authorization code from callback
            state: State parameter for validation

        Returns:
            Token response with access_token, refresh_token, expires_in

        Raises:
            ValueError: If state validation fails or token acquisition fails
        """
        logger.info("acquiring_token_from_code", function="acquire_token_from_code", state=state)

        try:
            await self._ensure_app_initialized(db)

            # Exchange authorization code for tokens
            result = self.app.acquire_token_by_authorization_code(
                code=authorization_code,
                scopes=self.DEFAULT_SCOPES,
                redirect_uri=self.redirect_uri,
            )

            if "access_token" not in result:
                error = result.get("error", "unknown_error")
                error_description = result.get("error_description", "No error description")
                logger.error("token_acquisition_failed", function="acquire_token_from_code",
                           error=error, error_description=error_description)
                raise ValueError(f"Token acquisition failed: {error} - {error_description}")

            logger.info("token_acquired_successfully", function="acquire_token_from_code")

            return {
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token"),
                "expires_in": result.get("expires_in", 3600),
                "token_type": result.get("token_type", "Bearer"),
                "scope": " ".join(self.DEFAULT_SCOPES),
            }

        except Exception as e:
            logger.error("token_acquisition_exception", function="acquire_token_from_code", error=str(e))
            raise

    async def get_access_token_for_user(self, user_id: str, db: AsyncSession) -> Optional[str]:
        """
        Get cached access token for user or refresh if expired.

        Args:
            user_id: User ID to get token for
            db: Database session

        Returns:
            Access token if available, None otherwise
        """
        # This would integrate with a token cache/database
        # For now, return None to force new authentication
        logger.info("get_access_token_for_user", function="get_access_token_for_user", user_id=user_id)
        return None

    async def refresh_access_token(self, db: AsyncSession, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.

        Args:
            refresh_token: Refresh token from initial authentication

        Returns:
            New token response

        Raises:
            ValueError: If refresh fails
        """
        logger.info("refreshing_access_token", function="refresh_access_token")

        try:
            await self._ensure_app_initialized(db)

            result = self.app.acquire_token_by_refresh_token(
                refresh_token=refresh_token,
                scopes=self.DEFAULT_SCOPES,
            )

            if "access_token" not in result:
                error = result.get("error", "unknown_error")
                error_description = result.get("error_description", "No error description")
                logger.error("token_refresh_failed", function="refresh_access_token",
                           error=error, error_description=error_description)
                raise ValueError(f"Token refresh failed: {error} - {error_description}")

            logger.info("token_refreshed_successfully", function="refresh_access_token")

            return {
                "access_token": result["access_token"],
                "refresh_token": result.get("refresh_token", refresh_token),
                "expires_in": result.get("expires_in", 3600),
                "token_type": result.get("token_type", "Bearer"),
                "scope": " ".join(self.DEFAULT_SCOPES),
            }

        except Exception as e:
            logger.error("token_refresh_exception", function="refresh_access_token", error=str(e))
            raise

    async def get_client_credentials_token(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Get access token using client credentials flow (service-to-service).

        Returns:
            Token response

        Raises:
            ValueError: If token acquisition fails
        """
        logger.info("getting_client_credentials_token", function="get_client_credentials_token")

        try:
            await self._ensure_app_initialized(db)

            result = self.app.acquire_token_for_client(scopes=self.DEFAULT_SCOPES)

            if "access_token" not in result:
                error = result.get("error", "unknown_error")
                error_description = result.get("error_description", "No error description")
                logger.error("client_credentials_token_failed", function="get_client_credentials_token",
                           error=error, error_description=error_description)
                raise ValueError(f"Client credentials failed: {error} - {error_description}")

            logger.info("client_credentials_token_acquired", function="get_client_credentials_token")

            return {
                "access_token": result["access_token"],
                "expires_in": result.get("expires_in", 3600),
                "token_type": result.get("token_type", "Bearer"),
                "scope": " ".join(self.DEFAULT_SCOPES),
            }

        except Exception as e:
            logger.error("client_credentials_exception", function="get_client_credentials_token", error=str(e))
            raise

    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate Microsoft Graph access token and extract claims.

        Args:
            token: Access token to validate

        Returns:
            Token claims if valid

        Raises:
            ValueError: If token is invalid
        """
        logger.info("validating_microsoft_token", function="validate_token")

        try:
            # Decode JWT without verification for basic validation
            # Microsoft Graph tokens are signed by Microsoft
            from jose import jwt
            claims = jwt.get_unverified_claims(token)

            # Validate token structure
            if not claims.get("aud"):
                raise ValueError("Token missing audience claim")

            if "graph.microsoft.com" not in claims.get("aud", ""):
                raise ValueError("Token not intended for Microsoft Graph")

            if claims.get("exp", 0) < datetime.now(timezone.utc).timestamp():
                raise ValueError("Token expired")

            logger.info("token_validated_successfully", function="validate_token")
            return claims

        except Exception as e:
            logger.error("token_validation_failed", function="validate_token", error=str(e))
            raise ValueError(f"Token validation failed: {str(e)}")


# Global instance
microsoft_auth_service = MicrosoftAuthService()