from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.db_setup import get_db
from src.utils.dependencies import get_current_user, require_roles
from src.models.dto.schemas.auth import UserClaims
from src.models.enum.user_role import UserRole
from src.services.ai_jobs import ai_job_service
from src.models.dto.schemas.ai_jobs import CreateAIJobRequest, AIJobResponse
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()
router = APIRouter()


@router.post("", response_model=AIJobResponse, status_code=202)
async def create_ai_job(
    body: CreateAIJobRequest,
    current_user: UserClaims = Depends(
        require_roles([
            UserRole.INTAKE_COORDINATOR, UserRole.DOC_SPECIALIST,
            UserRole.QC_OPERATOR, UserRole.PROOFREADER,
            UserRole.MANAGER, UserRole.ADMIN,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Trigger an AI analysis job for a document. Returns 202 with job details."""
    logger.info("Entering create_ai_job", function="create_ai_job", action="entry", user_id=current_user.id, document_id=str(body.document_id), job_type=body.job_type)
    result = await ai_job_service.create_ai_job(db, body, actor_id=current_user.id)
    logger.info("Exiting create_ai_job", function="create_ai_job", action="exit", job_id=str(result.id))
    return result


@router.get("/{job_id}", response_model=AIJobResponse)
async def get_ai_job(
    job_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll AI job status and results."""
    logger.info("Entering get_ai_job", function="get_ai_job", action="entry", job_id=str(job_id), user_id=current_user.id)
    result = await ai_job_service.get_ai_job(db, job_id)
    logger.info("Exiting get_ai_job", function="get_ai_job", action="exit", job_id=str(job_id), status=result.status)
    return result


@router.delete("/{job_id}/cancel", status_code=204)
async def cancel_ai_job(
    job_id: UUID,
    current_user: UserClaims = Depends(
        require_roles([
            UserRole.INTAKE_COORDINATOR, UserRole.DOC_SPECIALIST,
            UserRole.QC_OPERATOR, UserRole.PROOFREADER,
            UserRole.MANAGER, UserRole.ADMIN,
        ])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending or running AI job."""
    logger.info("Entering cancel_ai_job", function="cancel_ai_job", action="entry", job_id=str(job_id), user_id=current_user.id)
    await ai_job_service.cancel_ai_job(db, job_id, actor_id=current_user.id)
    logger.info("Exiting cancel_ai_job", function="cancel_ai_job", action="exit", job_id=str(job_id))
