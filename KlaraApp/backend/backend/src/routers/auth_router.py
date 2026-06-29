from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from jose import jwt
from typing import Optional
from pydantic import BaseModel

from src.repositories.db_setup import get_db
from src.models.dto.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, LogoutRequest, UserClaims
from src.utils.dependencies import get_current_user
from src.services.auth import auth_service
from src.services.integrations.microsoft_graph.auth_service import microsoft_auth_service
from src.configs.config import settings
from src.core.logger import get_logger_with_context
from src.models.dao.user import User

logger = get_logger_with_context()
router = APIRouter()
security_optional = HTTPBearer(auto_error=False)


# Microsoft OAuth Models
class MicrosoftAuthUrlRequest(BaseModel):
    """Request to get Microsoft authorization URL."""
    redirect_uri: Optional[str] = None


class MicrosoftAuthCallbackRequest(BaseModel):
    """Request to exchange Microsoft authorization code for tokens."""
    code: str
    state: str


class MicrosoftTokenRefreshRequest(BaseModel):
    """Request to refresh Microsoft access token."""
    refresh_token: str


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Exchange Azure AD token for session JWT or authenticate with username/password."""
    logger.info("Entering login", function="login", action="entry")
    
    # Azure AD authentication flow
    if body.azure_ad_token:
        try:
            logger.info("Validating Azure AD token", function="login", step="validate_token")
            azure_claims = await auth_service.validate_azure_ad_token(body.azure_ad_token)
            logger.info("Azure AD token validated successfully", function="login", step="token_validated", azure_oid=azure_claims.get("oid"))
        except Exception as e:
            logger.error("Azure AD token validation failed", function="login", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Azure AD token",
            )

        logger.info("Upserting user from Azure claims", function="login", step="upsert_user")
        user = await auth_service.upsert_user_from_azure(db, azure_claims)
        logger.info("User upserted successfully", function="login", step="user_upserted", user_id=str(user.id))
    
    # Username/Password authentication flow
    else:
        logger.info("Authenticating with username and password", function="login", step="password_auth", username=body.username)
        user = await auth_service.authenticate_with_password(db, body.username, body.password)
        
        if not user:
            logger.warning("Password authentication failed", function="login", step="auth_failed", username=body.username)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password",
            )
        
        logger.info("User authenticated successfully", function="login", step="user_authenticated", user_id=str(user.id))
    
    logger.info("Creating access and refresh tokens", function="login", step="create_tokens")
    access_token = auth_service.create_access_token(user)
    refresh_token = auth_service.create_refresh_token(user)
    await auth_service.store_session(user, access_token, refresh_token)
    logger.info("Session stored successfully", function="login", step="session_stored", user_id=str(user.id))

    logger.info("Exiting login", function="login", action="exit", user_id=str(user.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=auth_service.settings.jwt_access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token."""
    logger.info("Entering refresh", function="refresh", action="entry")
    logger.info("Refreshing access token", function="refresh", step="refresh_token")
    result = await auth_service.refresh_access_token(body.refresh_token, db)
    if not result:
        logger.warning("Refresh token validation failed", function="refresh", step="validation_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    logger.info("Exiting refresh", function="refresh", action="exit", success=True)
    return result


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_optional)
):
    """Invalidate current session and refresh token."""
    logger.info("Entering logout", function="logout", action="entry")
    
    refresh_token = body.refresh_token if body else None
    
    # 1. Invalidate refresh token and session via body if refresh_token is provided
    if refresh_token:
        try:
            payload = jwt.decode(
                refresh_token, 
                settings.jwt_secret_key, 
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False}
            )
            user_id = payload.get("sub")
            if user_id:
                await auth_service.invalidate_session(user_id, refresh_token)
                logger.info("Invalidated session and refresh token via body refresh_token", function="logout", user_id=user_id)
                return
        except Exception as e:
            logger.warning("Failed to decode refresh token during logout", error=str(e))
            
    # 2. Invalidate via access token if credentials are provided
    if credentials:
        token = credentials.credentials
        try:
            payload = jwt.decode(
                token, 
                settings.jwt_secret_key, 
                algorithms=[settings.jwt_algorithm],
                options={"verify_exp": False}
            )
            user_id = payload.get("sub")
            if user_id:
                await auth_service.invalidate_session(user_id, refresh_token)
                logger.info("Invalidated session via access token", function="logout", user_id=user_id)
                return
        except Exception as e:
            logger.warning("Failed to decode access token during logout", error=str(e))

    logger.info("Logout processed with no active session to invalidate")


@router.get("/me", response_model=UserClaims)
async def get_current_user_profile(current_user: UserClaims = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return current_user



# Microsoft Graph OAuth Endpoints

@router.post("/microsoft/authorize", response_model=dict)
async def get_microsoft_auth_url(
    request: MicrosoftAuthUrlRequest = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate Microsoft OAuth authorization URL for user consent.

    Returns authorization URL and state parameter for CSRF protection.
    """
    logger.info("Entering microsoft_authorize", function="get_microsoft_auth_url")

    try:
        # Use custom redirect URI if provided, otherwise use default
        redirect_uri = request.redirect_uri if request else None
        if redirect_uri:
            microsoft_auth_service.redirect_uri = redirect_uri

        auth_response = await microsoft_auth_service.get_authorization_url(db)

        logger.info("Exiting microsoft_authorize", function="get_microsoft_auth_url", success=True)
        return auth_response

    except Exception as e:
        logger.error("microsoft_authorize_failed", function="get_microsoft_auth_url", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )


@router.post("/microsoft/callback", response_model=dict)
async def microsoft_oauth_callback(
    body: MicrosoftAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange Microsoft authorization code for access token.

    Handles the OAuth callback and exchanges the authorization code for
    Microsoft Graph access tokens.
    """
    logger.info("Entering microsoft_callback", function="microsoft_oauth_callback", state=body.state)

    try:
        # Exchange authorization code for access token
        token_response = await microsoft_auth_service.acquire_token_from_code(
            db,
            body.code,
            body.state
        )

        logger.info("Exiting microsoft_callback", function="microsoft_oauth_callback", success=True)
        return token_response

    except ValueError as e:
        logger.error("microsoft_callback_failed", function="microsoft_oauth_callback", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error("microsoft_callback_exception", function="microsoft_oauth_callback", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Microsoft authentication failed: {str(e)}"
        )


@router.post("/microsoft/refresh", response_model=dict)
async def refresh_microsoft_token(
    body: MicrosoftTokenRefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh Microsoft access token using refresh token.

    Returns new access token and updated refresh token if available.
    """
    logger.info("Entering microsoft_refresh", function="refresh_microsoft_token")

    try:
        token_response = await microsoft_auth_service.refresh_access_token(db, body.refresh_token)

        logger.info("Exiting microsoft_refresh", function="refresh_microsoft_token", success=True)
        return token_response

    except ValueError as e:
        logger.error("microsoft_refresh_failed", function="refresh_microsoft_token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        logger.error("microsoft_refresh_exception", function="refresh_microsoft_token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Microsoft token refresh failed: {str(e)}"
        )


@router.get("/microsoft/validate", response_model=dict)
async def validate_microsoft_token(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
):
    """
    Validate Microsoft access token and return token claims.

    Used to verify token validity and extract user information.
    """
    logger.info("Entering microsoft_validate", function="validate_microsoft_token")

    try:
        token = credentials.credentials
        claims = microsoft_auth_service.validate_token(token)

        logger.info("Exiting microsoft_validate", function="validate_microsoft_token", success=True)
        return {
            "valid": True,
            "claims": claims
        }

    except ValueError as e:
        logger.error("microsoft_validate_failed", function="validate_microsoft_token", error=str(e))
        return {
            "valid": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error("microsoft_validate_exception", function="validate_microsoft_token", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Microsoft token validation failed: {str(e)}"
        )
