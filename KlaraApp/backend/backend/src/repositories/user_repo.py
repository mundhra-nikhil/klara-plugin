from uuid import UUID
from typing import Optional, List

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.user import User


async def find_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    return await db.get(User, user_id)


async def find_by_azure_oid(db: AsyncSession, azure_ad_oid: str) -> Optional[User]:
    stmt = select(User).where(User.azure_ad_oid == azure_ad_oid)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_by_email_or_oid(db: AsyncSession, email: str, azure_ad_oid: str) -> Optional[User]:
    stmt = select(User).where(
        (User.azure_ad_oid == azure_ad_oid) | (User.email == email)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def find_all(
    db: AsyncSession,
    *,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[List[User], int]:
    query = select(User)
    count_query = select(func.count()).select_from(User)

    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    query = query.order_by(User.display_name).limit(limit).offset(offset)

    result = await db.execute(query)
    users = list(result.scalars().all())
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return users, total


async def create(db: AsyncSession, user: User) -> User:
    db.add(user)
    await db.flush()
    return user
