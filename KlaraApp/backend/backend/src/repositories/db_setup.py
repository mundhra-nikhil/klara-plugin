from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.configs.config import settings
from src.models.dao.base import Base

# Import all models so SQLAlchemy can initialize mappers
from src.models.dao.user import User  # noqa: F401
from src.models.dao.client import Client  # noqa: F401
from src.models.dao.department import Department  # noqa: F401
from src.models.dao.document import Document, DocumentVersion, Notification, JobQueueEvent, SystemConfig  # noqa: F401
from src.models.dao.ai_analysis_job import AIAnalysisJob  # noqa: F401
from src.models.dao.qc_finding import QCFinding  # noqa: F401
from src.models.dao.qc_review import QCReview  # noqa: F401
from src.models.dao.checklist import QCChecklist  # noqa: F401
from src.models.dao.checklist_item import ChecklistItem  # noqa: F401
from src.models.dao.validation_rule import ClientValidationRule  # noqa: F401
from src.models.dao.audit_log import AuditLog  # noqa: F401


engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    echo=settings.app_debug,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
