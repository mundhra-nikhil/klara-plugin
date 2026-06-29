import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.enum.job_status import AuditAction, ActorType
from src.utils.audit_helpers import create_audit_log
from src.repositories import qc_finding_repo
from src.models.dto.schemas.qc import (
    FindingResponse,
    ResolveFindingRequest,
)


async def get_findings_for_document(
    db: AsyncSession, document_id: uuid.UUID
) -> List[FindingResponse]:
    findings = await qc_finding_repo.find_by_document_id(db, document_id)
    return [FindingResponse.model_validate(f) for f in findings]


async def resolve_finding(
    db: AsyncSession,
    finding_id: uuid.UUID,
    body: ResolveFindingRequest,
    actor_id: uuid.UUID,
) -> FindingResponse:
    finding = await qc_finding_repo.find_by_id(db, finding_id)
    if not finding:
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Finding {finding_id} not found")

    old_status = finding.status
    finding.status = body.status
    finding.resolved_by_user_id = actor_id
    finding.resolved_at = datetime.now(timezone.utc)

    # If the operator provided an inline edit, persist it into the location
    # JSONB so the side-by-side viewer can render the edited result instead of
    # the AI's original replacement_text.
    new_values: dict = {"status": body.status.value}
    if body.applied_text is not None:
        loc = dict(finding.location) if isinstance(finding.location, dict) else {}
        loc["applied_text"] = body.applied_text
        if body.note:
            loc["resolution_note"] = body.note
        finding.location = loc
        new_values["applied_text"] = body.applied_text
        if body.note:
            new_values["note"] = body.note
    elif body.note:
        loc = dict(finding.location) if isinstance(finding.location, dict) else {}
        loc["resolution_note"] = body.note
        finding.location = loc
        new_values["note"] = body.note

    await create_audit_log(
        db,
        entity_type="qc_findings",
        entity_id=finding.id,
        action=AuditAction.STATUS_CHANGE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        old_values={"status": old_status.value},
        new_values=new_values,
    )

    await db.flush()
    return FindingResponse.model_validate(finding)
