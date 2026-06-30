from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.db_setup import get_db
from src.utils.dependencies import get_current_user, require_roles
from src.models.dto.schemas.auth import UserClaims
from src.models.enum.user_role import UserRole
from src.models.enum.document_type import DocumentType
from src.services.qc import qc_service, finding_service, checklist_service
from src.models.dto.schemas.qc import (
    FindingResponse,
    ResolveFindingRequest,
    CreateReviewRequest,
    CompleteReviewRequest,
    ReviewResponse,
    ChecklistResponse,
    SaveChecklistItemStatusRequest,
    QCReviewChecklistStatusResponse,
)
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()
router = APIRouter()


@router.get("/reviews", response_model=list[ReviewResponse])
async def list_reviews(
    document_id: Optional[UUID] = Query(None),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List QC reviews, optionally filtered by document_id."""
    logger.info("Entering list_reviews router", document_id=str(document_id) if document_id else None)
    result = await qc_service.list_reviews(db, document_id)
    return result


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(
    review_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific QC review session."""
    logger.info("Entering get_review router", review_id=str(review_id))
    result = await qc_service.get_review(db, review_id)
    return result


@router.post("/reviews/{review_id}/checklist-items", response_model=QCReviewChecklistStatusResponse)
async def save_checklist_item_status(
    review_id: UUID,
    body: SaveChecklistItemStatusRequest,
    current_user: UserClaims = Depends(
        require_roles([UserRole.QC_OPERATOR, UserRole.MANAGER, UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Save or update the status of a specific checklist item under a review session."""
    logger.info("Entering save_checklist_item_status router", review_id=str(review_id), item_id=str(body.checklist_item_id))
    result = await qc_service.save_checklist_item_status(db, review_id, body, actor_id=current_user.id)
    return result


@router.get("/reviews/{review_id}/checklist-items", response_model=list[QCReviewChecklistStatusResponse])
async def get_checklist_statuses(
    review_id: UUID,
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve all checklist item statuses for a review session."""
    logger.info("Entering get_checklist_statuses router", review_id=str(review_id))
    result = await qc_service.get_checklist_statuses(db, review_id)
    return result


@router.get("/findings", response_model=list[FindingResponse])
async def list_findings(
    document_id: UUID = Query(...),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all QC findings for a document."""
    logger.info("Entering list_findings", function="list_findings", action="entry", document_id=str(document_id), user_id=current_user.id)
    result = await finding_service.get_findings_for_document(db, document_id)
    logger.info("Exiting list_findings", function="list_findings", action="exit", document_id=str(document_id), finding_count=len(result))
    return result


@router.patch("/findings/{finding_id}/resolve", response_model=FindingResponse)
async def resolve_finding(
    finding_id: UUID,
    body: ResolveFindingRequest,
    current_user: UserClaims = Depends(
        require_roles([UserRole.DOC_SPECIALIST, UserRole.QC_OPERATOR, UserRole.MANAGER, UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Accept, reject, or defer a QC finding."""
    logger.info("Entering resolve_finding", function="resolve_finding", action="entry", finding_id=str(finding_id), resolution=body.status, user_id=current_user.id)
    result = await finding_service.resolve_finding(db, finding_id, body, actor_id=current_user.id)
    logger.info("Exiting resolve_finding", function="resolve_finding", action="exit", finding_id=str(finding_id))
    return result


@router.post("/reviews", response_model=ReviewResponse, status_code=201)
async def create_review(
    body: CreateReviewRequest,
    current_user: UserClaims = Depends(
        require_roles([UserRole.QC_OPERATOR, UserRole.MANAGER, UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Start a QC review session."""
    logger.info("Entering create_review", function="create_review", action="entry", document_id=str(body.document_id), user_id=current_user.id)
    result = await qc_service.create_review(db, body, operator_id=current_user.id)
    logger.info("Exiting create_review", function="create_review", action="exit", review_id=str(result.id))
    return result


@router.patch("/reviews/{review_id}/complete", response_model=ReviewResponse)
async def complete_review(
    review_id: UUID,
    body: CompleteReviewRequest,
    current_user: UserClaims = Depends(
        require_roles([UserRole.QC_OPERATOR, UserRole.MANAGER, UserRole.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Mark a QC review as completed."""
    logger.info("Entering complete_review", function="complete_review", action="entry", review_id=str(review_id), user_id=current_user.id)
    result = await qc_service.complete_review(db, review_id, body, actor_id=current_user.id)
    logger.info("Exiting complete_review", function="complete_review", action="exit", review_id=str(review_id))
    return result


@router.get("/checklists", response_model=list[ChecklistResponse])
async def list_checklists(
    type: Optional[str] = Query(None),
    current_user: UserClaims = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List available QC checklists, optionally filtered by document type."""
    logger.info("Entering list_checklists", function="list_checklists", action="entry", type=type, user_id=current_user.id)

    # Map type to DocumentType enum
    doc_type_enum = None
    if type:
        try:
            # Direct mapping first
            doc_type_enum = DocumentType(type.lower())
        except ValueError:
            # Fallback mappings for common aliases
            type_lower = type.lower()
            if type_lower in ["document_review", "review", "qc"]:
                doc_type_enum = DocumentType.FORMATTING
            elif type_lower in ["litigation", "litigation_document"]:
                doc_type_enum = DocumentType.LITIGATION
            else:
                # Default to formatting if unknown
                doc_type_enum = DocumentType.FORMATTING

    result = await checklist_service.list_checklists(db, document_type=doc_type_enum)
    logger.info("Exiting list_checklists", function="list_checklists", action="exit", checklist_count=len(result))
    return result
