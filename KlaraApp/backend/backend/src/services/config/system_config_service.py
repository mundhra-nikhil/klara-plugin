from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.models.dao.document import SystemConfig
from src.models.dto.schemas.system_config import SetSystemConfigRequest
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


class SystemConfigService:
    async def get_config(self, db: AsyncSession, key: str) -> Optional[SystemConfig]:
        """Get a system configuration by key."""
        logger.info("getting_system_config", key=key)
        stmt = select(SystemConfig).where(SystemConfig.key == key)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def set_config(self, db: AsyncSession, key: str, req: SetSystemConfigRequest) -> SystemConfig:
        """Set or update a system configuration."""
        logger.info("setting_system_config", key=key)
        config = await self.get_config(db, key)
        
        if config:
            config.value = req.value
            if req.description is not None:
                config.description = req.description
            if req.ttl_seconds is not None:
                config.ttl_seconds = req.ttl_seconds
        else:
            config = SystemConfig(
                key=key,
                value=req.value,
                description=req.description,
                ttl_seconds=req.ttl_seconds
            )
            db.add(config)
            
        await db.commit()
        await db.refresh(config)
        return config

    async def delete_config(self, db: AsyncSession, key: str) -> bool:
        """Delete a system configuration."""
        logger.info("deleting_system_config", key=key)
        config = await self.get_config(db, key)
        if config:
            await db.delete(config)
            await db.commit()
            return True
        return False


system_config_service = SystemConfigService()
