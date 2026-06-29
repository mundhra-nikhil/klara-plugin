from uuid import UUID
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.ai_analysis_job import AIAnalysisJob


async def find_by_id(db: AsyncSession, job_id: UUID) -> Optional[AIAnalysisJob]:
    return await db.get(AIAnalysisJob, job_id)


async def create(db: AsyncSession, job: AIAnalysisJob) -> AIAnalysisJob:
    db.add(job)
    await db.flush()
    return job
