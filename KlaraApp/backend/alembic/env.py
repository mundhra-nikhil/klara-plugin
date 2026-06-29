from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add the backend directory to the Python path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables from .env file
load_dotenv(backend_dir / ".env")

# Import all models so Alembic can detect them
from src.models.dao.base import Base
from src.models.dao.user import User  # noqa: F401
from src.models.dao.client import Client  # noqa: F401
from src.models.dao.department import Department  # noqa: F401
from src.models.dao.document import Document  # noqa: F401
from src.models.dao.ai_analysis_job import AIAnalysisJob  # noqa: F401
from src.models.dao.qc_finding import QCFinding  # noqa: F401
from src.models.dao.qc_review import QCReview  # noqa: F401
from src.models.dao.checklist import QCChecklist  # noqa: F401
from src.models.dao.checklist_item import ChecklistItem  # noqa: F401
from src.models.dao.qc_review_checklist_status import QCReviewChecklistStatus  # noqa: F401
from src.models.dao.validation_rule import ClientValidationRule  # noqa: F401
from src.models.dao.audit_log import AuditLog  # noqa: F401
from src.models.dao.document import DocumentVersion, Notification, JobQueueEvent, SystemConfig  # noqa: F401

config = context.config

# Override the sqlalchemy.url from environment variable if available
if os.getenv("DATABASE_URL"):
    config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
