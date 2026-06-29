import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.qc_review import QCReview
from src.models.enum.job_status import AuditAction, ActorType
from src.utils.audit_helpers import create_audit_log
from src.repositories import qc_review_repo, qc_review_checklist_status_repo
from src.models.dto.schemas.qc import (
    CreateReviewRequest,
    CompleteReviewRequest,
    ReviewResponse,
    SaveChecklistItemStatusRequest,
    QCReviewChecklistStatusResponse,
)
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


async def list_reviews(
    db: AsyncSession,
    document_id: Optional[uuid.UUID] = None
) -> List[QCReview]:
    logger.info("Entering list_reviews", function="list_reviews", action="entry", document_id=str(document_id) if document_id else None)
    reviews = await qc_review_repo.find_all(db, document_id)
    return reviews


async def get_review(
    db: AsyncSession,
    review_id: uuid.UUID
) -> QCReview:
    logger.info("Entering get_review", function="get_review", action="entry", review_id=str(review_id))
    review = await qc_review_repo.find_by_id(db, review_id)
    if not review:
        logger.warning("QC review not found", function="get_review", review_id=str(review_id))
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Review {review_id} not found")
    return review


async def create_review(
    db: AsyncSession,
    body: CreateReviewRequest,
    operator_id: uuid.UUID,
) -> ReviewResponse:
    logger.info("Entering create_review", function="create_review", action="entry", document_id=str(body.document_id), operator_id=str(operator_id))
    
    checklist_id = body.checklist_id
    if not checklist_id:
        from src.repositories import document_repo, checklist_repo
        doc = await document_repo.find_by_id(db, body.document_id)
        if doc:
            checklists = await checklist_repo.find_all(db, document_type=doc.document_type)
            if checklists:
                checklist_id = checklists[0].id
                logger.info("Auto-resolved checklist", checklist_id=str(checklist_id), doc_type=str(doc.document_type))

    logger.info("Creating QC review", function="create_review", step="create_review")
    review = QCReview(
        document_id=body.document_id,
        checklist_id=checklist_id,
        operator_id=operator_id,
        status="in_progress",
        notes=body.notes,
    )
    await qc_review_repo.create(db, review)
    logger.info("QC review created", function="create_review", step="review_created", review_id=str(review.id))

    logger.info("Creating audit log", function="create_review", step="audit_log")
    await create_audit_log(
        db,
        entity_type="qc_reviews",
        entity_id=review.id,
        action=AuditAction.CREATE,
        actor_id=operator_id,
        actor_type=ActorType.HUMAN,
        new_values={"document_id": str(body.document_id)},
    )

    await db.flush()
    logger.info("Exiting create_review", function="create_review", action="exit", review_id=str(review.id))
    return ReviewResponse.model_validate(review)


async def complete_review(
    db: AsyncSession,
    review_id: uuid.UUID,
    body: CompleteReviewRequest,
    actor_id: uuid.UUID,
) -> ReviewResponse:
    logger.info("Entering complete_review", function="complete_review", action="entry", review_id=str(review_id), actor_id=str(actor_id))
    
    review = await qc_review_repo.find_by_id(db, review_id)
    if not review:
        logger.warning("QC review not found", function="complete_review", review_id=str(review_id))
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Review {review_id} not found")
    if review.status == "completed":
        logger.warning("Review already completed", function="complete_review", review_id=str(review_id))
        from src.utils.dependencies import BadRequestError
        raise BadRequestError("Review already completed")

    review.status = "completed"
    review.completed_at = datetime.now(timezone.utc)
    if body.notes:
        review.notes = body.notes

    await create_audit_log(
        db,
        entity_type="qc_reviews",
        entity_id=review.id,
        action=AuditAction.STATUS_CHANGE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        old_values={"status": "in_progress"},
        new_values={"status": "completed"},
    )

    # Also update the linked document status to COMPLETED
    # so the document queue reflects the QC completion immediately
    try:
        from src.repositories import document_repo
        from src.models.enum.document_status import DocumentStatus

        document = await document_repo.find_by_id(db, review.document_id)
        if document and document.status in (DocumentStatus.QC_REVIEW, DocumentStatus.PROCESSING):
            old_doc_status = document.status
            document.status = DocumentStatus.COMPLETED
            if document.completed_at is None:
                document.completed_at = datetime.now(timezone.utc)
            logger.info(
                "Auto-completing document after QC review",
                function="complete_review",
                document_id=str(review.document_id),
                old_status=old_doc_status.value,
            )
            await create_audit_log(
                db,
                entity_type="documents",
                entity_id=document.id,
                action=AuditAction.STATUS_CHANGE,
                actor_id=actor_id,
                actor_type=ActorType.HUMAN,
                old_values={"status": old_doc_status.value},
                new_values={"status": DocumentStatus.COMPLETED.value, "reason": "QC review completed"},
            )
    except Exception as ex:
        logger.error(f"Failed to auto-complete document status: {ex}", function="complete_review")

    await db.flush()
    logger.info("Exiting complete_review", function="complete_review", action="exit", review_id=str(review_id))
    return ReviewResponse.model_validate(review)


async def save_checklist_item_status(
    db: AsyncSession,
    review_id: uuid.UUID,
    body: SaveChecklistItemStatusRequest,
    actor_id: uuid.UUID
) -> QCReviewChecklistStatusResponse:
    logger.info("Entering save_checklist_item_status", function="save_checklist_item_status", review_id=str(review_id), checklist_item_id=str(body.checklist_item_id))
    
    # Verify review exists
    review = await qc_review_repo.find_by_id(db, review_id)
    if not review:
        logger.warning("QC review not found", function="save_checklist_item_status", review_id=str(review_id))
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Review {review_id} not found")

    # Save checklist item status
    db_status = await qc_review_checklist_status_repo.save_status(
        db,
        review_id=review_id,
        checklist_item_id=body.checklist_item_id,
        status=body.status,
        details=body.details
    )

    # Log to audit trail
    await create_audit_log(
        db,
        entity_type="qc_review_checklist_statuses",
        entity_id=db_status.id,
        action=AuditAction.UPDATE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        new_values={
            "review_id": str(review_id),
            "checklist_item_id": str(body.checklist_item_id),
            "status": body.status,
            "details": body.details
        }
    )

    await db.flush()
    return QCReviewChecklistStatusResponse.model_validate(db_status)


async def get_checklist_statuses(
    db: AsyncSession,
    review_id: uuid.UUID
) -> List[QCReviewChecklistStatusResponse]:
    logger.info("Entering get_checklist_statuses", function="get_checklist_statuses", review_id=str(review_id))
    statuses = await qc_review_checklist_status_repo.get_statuses_for_review(db, review_id)
    return [QCReviewChecklistStatusResponse.model_validate(s) for s in statuses]
