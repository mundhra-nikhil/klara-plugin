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
    result = []
    for finding in findings:
        # Extract location data for frontend compatibility
        loc = {}
        if isinstance(finding.location, dict):
            loc = finding.location
        elif finding.location:
            try:
                import json
                loc = json.loads(finding.location) if isinstance(finding.location, str) else finding.location
            except:
                loc = {}

        # Create response with additional fields
        response_dict = {
            "id": finding.id,
            "document_id": finding.document_id,
            "analysis_job_id": finding.analysis_job_id,
            "finding_type": finding.finding_type,
            "severity": finding.severity,
            "location": finding.location,
            "description": finding.description,
            "suggested_fix": finding.suggested_fix,
            "status": finding.status,
            "resolved_by_user_id": finding.resolved_by_user_id,
            "resolved_at": finding.resolved_at,
            "created_at": finding.created_at,
            # Additional fields from location
            "paragraph_index": loc.get("paragraph") or loc.get("paragraph_index"),
            "anchor_text": loc.get("anchor_text"),
            "title": loc.get("title"),
            "rule_name": loc.get("rule_name"),
            "original_text": loc.get("original_text"),
            "replacement_text": loc.get("replacement_text"),
        }
        result.append(FindingResponse(**response_dict))
    return result


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

    # Use resolution_notes if provided, otherwise fall back to note
    note_to_use = body.resolution_notes or body.note

    if body.applied_text is not None:
        loc = dict(finding.location) if isinstance(finding.location, dict) else {}
        loc["applied_text"] = body.applied_text
        if note_to_use:
            loc["resolution_note"] = note_to_use
        if body.auto_resolved is not None:
            loc["auto_resolved"] = body.auto_resolved
        if body.not_found_in_document is not None:
            loc["not_found_in_document"] = body.not_found_in_document
        finding.location = loc
        new_values["applied_text"] = body.applied_text
        if note_to_use:
            new_values["note"] = note_to_use
        if body.auto_resolved is not None:
            new_values["auto_resolved"] = body.auto_resolved
        if body.not_found_in_document is not None:
            new_values["not_found_in_document"] = body.not_found_in_document
    elif note_to_use:
        loc = dict(finding.location) if isinstance(finding.location, dict) else {}
        loc["resolution_note"] = note_to_use
        if body.auto_resolved is not None:
            loc["auto_resolved"] = body.auto_resolved
        if body.not_found_in_document is not None:
            loc["not_found_in_document"] = body.not_found_in_document
        finding.location = loc
        new_values["note"] = note_to_use
        if body.auto_resolved is not None:
            new_values["auto_resolved"] = body.auto_resolved
        if body.not_found_in_document is not None:
            new_values["not_found_in_document"] = body.not_found_in_document

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

    # Extract location data for frontend compatibility
    loc = {}
    if isinstance(finding.location, dict):
        loc = finding.location
    elif finding.location:
        try:
            import json
            loc = json.loads(finding.location) if isinstance(finding.location, str) else finding.location
        except:
            loc = {}

    # Create response with additional fields
    response_dict = {
        "id": finding.id,
        "document_id": finding.document_id,
        "analysis_job_id": finding.analysis_job_id,
        "finding_type": finding.finding_type,
        "severity": finding.severity,
        "location": finding.location,
        "description": finding.description,
        "suggested_fix": finding.suggested_fix,
        "status": finding.status,
        "resolved_by_user_id": finding.resolved_by_user_id,
        "resolved_at": finding.resolved_at,
        "created_at": finding.created_at,
        # Additional fields from location
        "paragraph_index": loc.get("paragraph") or loc.get("paragraph_index"),
        "anchor_text": loc.get("anchor_text"),
        "title": loc.get("title"),
        "rule_name": loc.get("rule_name"),
        "original_text": loc.get("original_text"),
        "replacement_text": loc.get("replacement_text"),
    }
    return FindingResponse(**response_dict)
