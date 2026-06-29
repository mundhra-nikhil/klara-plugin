from uuid import UUID
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.client import Client


async def find_by_id(db: AsyncSession, client_id: UUID) -> Optional[Client]:
    return await db.get(Client, client_id)


async def create(db: AsyncSession, client: Client) -> Client:
    db.add(client)
    await db.flush()
    return client
