import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.configs.config import settings
from src.core.state import redis_client
from src.models.dao.user import User
from src.models.enum.user_role import UserRole
from src.models.dto.schemas.auth import TokenResponse, UserClaims
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()

AZURE_JWKS_URL = f"{settings.azure_ad_authority}/discovery/v2.0/keys"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def validate_azure_ad_token(token: str) -> dict:
    """Validate Azure AD token and return claims."""
    logger.info("Entering validate_azure_ad_token", function="validate_azure_ad_token", action="entry")
    try:
        logger.info("Fetching Azure AD JWKS", function="validate_azure_ad_token", step="fetch_jwks")
        async with httpx.AsyncClient() as client:
            resp = await client.get(AZURE_JWKS_URL)
            resp.raise_for_status()
            jwks = resp.json()

        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks.get("keys", []):
            if key["kid"] == unverified_header.get("kid"):
                rsa_key = key
                break

        if not rsa_key:
            logger.error("RSA key not found", function="validate_azure_ad_token", step="key_not_found")
            raise ValueError("Unable to find appropriate key")

        logger.info("Decoding JWT token", function="validate_azure_ad_token", step="decode_token")
        claims = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=settings.azure_ad_client_id,
            issuer=f"{settings.azure_ad_authority}/v2.0",
        )
        logger.info("Exiting validate_azure_ad_token", function="validate_azure_ad_token", action="exit", oid=claims.get("oid"))
        return claims
    except Exception as e:
        logger.error("Failed to validate Azure AD token", function="validate_azure_ad_token", error=str(e))
        raise


async def upsert_user_from_azure(db: AsyncSession, claims: dict) -> User:
    """Create or update a user from Azure AD claims."""
    logger.info("Entering upsert_user_from_azure", function="upsert_user_from_azure", action="entry")
    azure_oid = claims.get("oid") or claims.get("sub")
    email = claims.get("preferred_username") or claims.get("email", "")
    display_name = claims.get("name", email)
    
    logger.info("Querying user by Azure OID", function="upsert_user_from_azure", step="query_user", azure_oid=azure_oid)
    stmt = select(User).where(User.azure_ad_oid == azure_oid)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        logger.info("Updating existing user", function="upsert_user_from_azure", step="update_user", user_id=str(user.id))
        user.email = email
        user.display_name = display_name
    else:
        logger.info("Creating new user", function="upsert_user_from_azure", step="create_user", email=email)
        user = User(
            azure_ad_oid=azure_oid,
            email=email,
            display_name=display_name,
            role=UserRole.DOC_SPECIALIST,
        )
        db.add(user)

    await db.flush()
    logger.info("Exiting upsert_user_from_azure", function="upsert_user_from_azure", action="exit", user_id=str(user.id))
    return user


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


async def authenticate_with_password(db: AsyncSession, username: str, password: str) -> Optional[User]:
    """Authenticate user with username (email) and password."""
    logger.info("Entering authenticate_with_password", function="authenticate_with_password", action="entry", username=username)
    
    try:
        logger.info("Querying user by email", function="authenticate_with_password", step="query_user")
        stmt = select(User).where(User.email == username, User.is_active == True)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            logger.warning("User not found or inactive", function="authenticate_with_password", step="user_not_found", username=username)
            return None
        
        if not user.password_hash:
            logger.warning("User has no password set", function="authenticate_with_password", step="no_password", username=username)
            return None
        
        logger.info("Verifying password", function="authenticate_with_password", step="verify_password")
        if not verify_password(password, user.password_hash):
            logger.warning("Password verification failed", function="authenticate_with_password", step="password_mismatch", username=username)
            return None
        
        logger.info("Exiting authenticate_with_password", function="authenticate_with_password", action="exit", user_id=str(user.id))
        return user
    except Exception as e:
        logger.error("Error during password authentication", function="authenticate_with_password", error=str(e))
        return None


def create_access_token(user: User) -> str:
    logger.info("Entering create_access_token", function="create_access_token", action="entry", user_id=str(user.id))
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value if isinstance(user.role, UserRole) else user.role,
        "azure_ad_oid": user.azure_ad_oid,
        "department_id": str(user.department_id) if user.department_id else None,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    logger.info("Exiting create_access_token", function="create_access_token", action="exit", user_id=str(user.id))
    return token


def create_refresh_token(user: User) -> str:
    logger.info("Entering create_refresh_token", function="create_refresh_token", action="entry", user_id=str(user.id))
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": str(user.id),
        "type": "refresh",
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    logger.info("Exiting create_refresh_token", function="create_refresh_token", action="exit", user_id=str(user.id))
    return token


async def store_session(user: User, access_token: str, refresh_token: str):
    """Store session in Redis for instant revocation capability."""
    logger.info("Entering store_session", function="store_session", action="entry", user_id=str(user.id))
    session_data = {
        "user_id": str(user.id),
        "email": user.email,
        "role": user.role.value if isinstance(user.role, UserRole) else user.role,
        "access_token": access_token,
    }
    ttl = settings.jwt_access_token_expire_minutes * 60
    await redis_client.hset(f"user:{user.id}:session", mapping=session_data)
    await redis_client.expire(f"user:{user.id}:session", ttl)

    refresh_ttl = settings.jwt_refresh_token_expire_days * 86400
    await redis_client.set(f"refresh:{refresh_token}", str(user.id), ex=refresh_ttl)
    logger.info("Exiting store_session", function="store_session", action="exit", user_id=str(user.id))


async def invalidate_session(user_id: str, refresh_token: Optional[str] = None):
    """Remove session from Redis."""
    logger.info("Entering invalidate_session", function="invalidate_session", action="entry", user_id=user_id)
    await redis_client.delete(f"user:{user_id}:session")
    if refresh_token:
        logger.info("Invalidating refresh token in Redis", function="invalidate_session", step="invalidate_refresh")
        await redis_client.delete(f"refresh:{refresh_token}")
    logger.info("Exiting invalidate_session", function="invalidate_session", action="exit", user_id=user_id)


async def verify_access_token(token: str) -> Optional[UserClaims]:
    """Verify JWT access token and check session exists in Redis."""
    logger.info("Entering verify_access_token", function="verify_access_token", action="entry")
    try:
        logger.info("Decoding JWT token", function="verify_access_token", step="decode_token")
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("No user_id in token payload", function="verify_access_token", step="no_user_id")
            return None

        logger.info("Checking session in Redis", function="verify_access_token", step="check_session", user_id=user_id)
        session = await redis_client.hgetall(f"user:{user_id}:session")
        if not session:
            logger.warning("Session not found in Redis", function="verify_access_token", step="session_not_found", user_id=user_id)
            return None

        logger.info("Exiting verify_access_token", function="verify_access_token", action="exit", user_id=user_id)
        return UserClaims(
            id=user_id,
            email=payload["email"],
            display_name=payload["display_name"],
            role=payload["role"],
            azure_ad_oid=payload.get("azure_ad_oid"),
            department_id=payload.get("department_id"),
        )
    except JWTError as e:
        logger.error("JWT verification failed", function="verify_access_token", error=str(e))
        return None


async def refresh_access_token(refresh_token: str, db: AsyncSession) -> Optional[TokenResponse]:
    """Issue new access token from refresh token."""
    logger.info("Entering refresh_access_token", function="refresh_access_token", action="entry")
    try:
        logger.info("Decoding refresh token", function="refresh_access_token", step="decode_token")
        payload = jwt.decode(refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "refresh":
            logger.warning("Token is not a refresh token", function="refresh_access_token", step="invalid_type")
            return None

        user_id = payload.get("sub")
        logger.info("Validating refresh token in Redis", function="refresh_access_token", step="validate_redis", user_id=user_id)
        stored_user_id = await redis_client.get(f"refresh:{refresh_token}")
        if not stored_user_id or stored_user_id != user_id:
            logger.warning("Refresh token not found or mismatch", function="refresh_access_token", step="token_mismatch")
            return None

        logger.info("Fetching user from database", function="refresh_access_token", step="fetch_user", user_id=user_id)
        stmt = select(User).where(User.id == user_id, User.is_active == True)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if not user:
            logger.warning("User not found or inactive", function="refresh_access_token", step="user_not_found", user_id=user_id)
            return None

        logger.info("Creating new access token", function="refresh_access_token", step="create_token", user_id=user_id)
        new_access_token = create_access_token(user)
        await store_session(user, new_access_token, refresh_token)

        logger.info("Exiting refresh_access_token", function="refresh_access_token", action="exit", user_id=user_id)
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_token,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )
    except JWTError as e:
        logger.error("JWT error during refresh", function="refresh_access_token", error=str(e))
        return None
