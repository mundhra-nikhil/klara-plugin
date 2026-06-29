from uuid import UUID
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.models.dao.document import Document
from src.models.dao.client import Client
from src.models.dao.user import User
from src.models.enum.document_status import DocumentStatus
from src.models.enum.document_type import DocumentType
from src.models.enum.job_status import AuditAction, ActorType
from src.repositories import document_repo
from src.utils.audit_helpers import create_audit_log
from src.core.storage import generate_upload_sas_url
from src.models.dto.schemas.documents import (
    CreateDocumentRequest,
    CreateDocumentResponse,
    DocumentResponse,
    UpdateDocumentStatusRequest,
    AssignDocumentRequest,
    DocumentVersionResponse,
)
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


async def list_documents(
    db,
    *,
    client_id: Optional[UUID] = None,
    status: Optional[DocumentStatus] = None,
    document_type: Optional[DocumentType] = None,
    cursor: Optional[str] = None,
    limit: int = 20,
    assigned_specialist_id: Optional[UUID] = None,
) -> dict:
    logger.info(
        "Entering list_documents",
        function="list_documents",
        action="entry",
        client_id=str(client_id) if client_id else None,
        status=status,
        document_type=document_type,
        limit=limit,
        assigned_specialist_id=str(assigned_specialist_id) if assigned_specialist_id else None,
    )
    documents, next_cursor, total = await document_repo.find_all(
        db,
        client_id=client_id,
        status=status,
        document_type=document_type,
        cursor=cursor,
        limit=limit,
        assigned_specialist_id=assigned_specialist_id,
    )

    # Resolve names: build a map of user IDs → display_name
    specialist_ids = {d.assigned_specialist_id for d in documents if d.assigned_specialist_id}
    client_ids = {d.client_id for d in documents}

    user_name_map: dict = {}
    if specialist_ids:
        user_result = await db.execute(
            select(User.id, User.display_name).where(User.id.in_(specialist_ids))
        )
        for uid, name in user_result.all():
            user_name_map[uid] = name

    client_name_map: dict = {}
    if client_ids:
        client_result = await db.execute(
            select(Client.id, Client.name).where(Client.id.in_(client_ids))
        )
        for cid, cname in client_result.all():
            client_name_map[cid] = cname

    def enrich(d: Document) -> DocumentResponse:
        resp = DocumentResponse.model_validate(d)
        # Inject resolved names as proper fields
        if d.assigned_specialist_id:
            resp.assigned_specialist_name = user_name_map.get(
                d.assigned_specialist_id, str(d.assigned_specialist_id)
            )
        if d.client_id:
            resp.client_name = client_name_map.get(d.client_id, str(d.client_id))
        return resp

    enriched = [enrich(d) for d in documents]

    logger.info(
        "Exiting list_documents",
        function="list_documents",
        action="exit",
        document_count=len(enriched),
        total=total,
    )
    return {
        "data": enriched,
        "next_cursor": next_cursor,
        "total": total,
    }


async def get_document(db, document_id: UUID) -> Document:
    logger.info("Entering get_document", function="get_document", action="entry", document_id=str(document_id))
    document = await document_repo.find_by_id(db, document_id)
    if not document:
        logger.warning("Document not found", function="get_document", document_id=str(document_id))
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Document {document_id} not found")
    logger.info("Exiting get_document", function="get_document", action="exit", document_id=str(document_id))
    return document


async def create_document(
    db,
    body: CreateDocumentRequest,
    actor_id: UUID,
) -> CreateDocumentResponse:
    logger.info("Entering create_document", function="create_document", action="entry", client_id=str(body.client_id), title=body.title, actor_id=str(actor_id))

    logger.info("Fetching client", function="create_document", step="fetch_client", client_id=str(body.client_id))
    client = await db.get(Client, body.client_id)
    if not client:
        logger.warning("Client not found", function="create_document", client_id=str(body.client_id))
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Client {body.client_id} not found")

    blob_container = client.blob_container_name
    blob_path = f"{body.client_id}/{body.title}"

    client_profile = client.qa_rule_profile or {}
    client_val_mode = client_profile.get("validation_mode")
    if client_val_mode == "manual":
        resolved_mode = "review_assist"
    elif client_val_mode == "automatic":
        resolved_mode = "auto"
    else:
        resolved_mode = body.validation_mode if body.validation_mode else "auto"

    logger.info("Creating document record", function="create_document", step="create_record", blob_path=blob_path, resolved_mode=resolved_mode)
    document = Document(
        client_id=body.client_id,
        title=body.title,
        document_type=body.document_type,
        status=DocumentStatus.RECEIVED,
        blob_url=f"https://storage.azure.com/{blob_container}/{blob_path}",
        blob_container=blob_container,
        metadata_=body.metadata or {},
        priority=body.priority,
        deadline=body.deadline,
        validation_mode=resolved_mode,
    )
    await document_repo.create(db, document)
    logger.info("Document created", function="create_document", step="document_created", document_id=str(document.id))

    await create_audit_log(
        db,
        entity_type="documents",
        entity_id=document.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        new_values={"title": body.title, "status": "received"},
    )

    logger.info("Generating upload URL", function="create_document", step="generate_url")
    upload_url = await generate_upload_sas_url(blob_container, blob_path, document_id=str(document.id))

    # NOTE: in "auto" mode Klara is NOT triggered here — the file has not been
    # uploaded yet (the client PUTs it to the SAS/upload URL after this call
    # returns). Triggering now would analyse a missing file and fall back to a
    # canned template. The auto-run fires once the upload lands — see
    # `trigger_auto_klara` (called from the upload-local handler). In
    # "review_assist" mode there is no auto-run at all; the reviewer triggers
    # Klara on demand via the "Run Klara" button.
    logger.info(
        "Deferring AI analysis until upload completes" if document.validation_mode == "auto"
        else "Skipping auto AI analysis (review_assist mode)",
        function="create_document", step="defer_or_skip_auto_ai",
        document_id=str(document.id), validation_mode=document.validation_mode,
    )

    logger.info("Exiting create_document", function="create_document", action="exit", document_id=str(document.id))
    return CreateDocumentResponse(
        id=document.id,
        status=document.status,
        upload_url=upload_url,
        ws_channel=f"/docs/{document.id}/events",
    )


async def trigger_auto_klara(db, document: Document, actor_id: UUID) -> None:
    """Fire the automatic first-pass Klara QA run for a document whose client is
    configured for 'automatic' validation mode. Called once the uploaded file
    has actually landed (so the analysis runs against the real document, not a
    canned fallback). No-op for documents in 'review_assist' mode."""
    if document.validation_mode != "auto":
        logger.info(
            "Skipping auto Klara (review_assist mode)",
            function="trigger_auto_klara", document_id=str(document.id),
        )
        return
    try:
        from src.services.ai_jobs.ai_job_service import create_ai_job
        from src.models.dto.schemas.ai_jobs import CreateAIJobRequest
        from src.models.enum.job_type import AIJobType

        job_type = AIJobType.FORMATTING_CHECK
        if document.document_type == DocumentType.PROOFREADING:
            job_type = AIJobType.PROOFREADING

        logger.info(
            "Auto-triggering AI Analysis job after upload",
            function="trigger_auto_klara", document_id=str(document.id), job_type=job_type.value,
        )
        await create_ai_job(
            db=db,
            body=CreateAIJobRequest(document_id=document.id, job_type=job_type),
            actor_id=actor_id,
        )
    except Exception as ex:
        logger.error(
            f"Failed to auto-trigger AI analysis job: {ex}",
            function="trigger_auto_klara", document_id=str(document.id),
        )


async def update_document_status(
    db,
    document_id: UUID,
    body: UpdateDocumentStatusRequest,
    actor_id: UUID,
) -> DocumentResponse:
    document = await get_document(db, document_id)
    old_status = document.status
    document.status = body.status

    # Stamp completion time the first time a document reaches COMPLETED — powers
    # the reporting turnaround/LOE metrics. Don't overwrite an earlier stamp.
    if body.status == DocumentStatus.COMPLETED and document.completed_at is None:
        from datetime import datetime, timezone
        document.completed_at = datetime.now(timezone.utc)

    await create_audit_log(
        db,
        entity_type="documents",
        entity_id=document.id,
        action=AuditAction.STATUS_CHANGE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        old_values={"status": old_status.value},
        new_values={"status": body.status.value},
    )

    await db.flush()
    return DocumentResponse.model_validate(document)


async def assign_document(
    db,
    document_id: UUID,
    body: AssignDocumentRequest,
    actor_id: UUID,
) -> DocumentResponse:
    document = await get_document(db, document_id)
    old_specialist = document.assigned_specialist_id
    # proofreader_id takes precedence; fall back to specialist_id
    new_assignee = body.proofreader_id or body.specialist_id
    document.assigned_specialist_id = new_assignee

    await create_audit_log(
        db,
        entity_type="documents",
        entity_id=document.id,
        action=AuditAction.UPDATE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        old_values={"assigned_specialist_id": str(old_specialist) if old_specialist else None},
        new_values={"assigned_specialist_id": str(new_assignee) if new_assignee else None},
    )

    await db.flush()
    return DocumentResponse.model_validate(document)


async def get_document_versions(
    db, document_id: UUID
) -> List[DocumentVersionResponse]:
    await get_document(db, document_id)
    versions = await document_repo.find_versions(db, document_id)
    return [DocumentVersionResponse.model_validate(v) for v in versions]
