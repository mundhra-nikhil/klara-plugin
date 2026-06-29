import asyncio
import os
import sys

# Add backend to path so src can be resolved
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.repositories.db_setup import engine
from src.models.dao.base import Base
from src.models.dao.system_config import SystemConfig

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_db())
