"""Router for Microsoft Word features.

Exposes REST endpoints for Track Changes, Comments, and Co-authoring functionality.
"""

from typing import List, Dict, Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.utils.dependencies import get_current_user, require_roles
from src.models.dto.schemas.auth import UserClaims
from src.models.enum.user_role import UserRole
from src.core.logger import get_logger_with_context

from src.services.word_features.track_changes_service import track_changes_service
from src.services.word_features.comments_service import comments_service
from src.services.word_features.coauthoring_service import coauthoring_service

logger = get_logger_with_context()
router = APIRouter()

# --- Request Models ---

class EnableTrackChangesRequest(BaseModel):
    enabled: bool = True

class ApplyAiEditRequest(BaseModel):
    finding_text: str
    replacement_text: str
    occurrence_index: int = 0

class BulkApplyAiEditsRequest(BaseModel):
    fixes: List[Dict[str, Any]]

class RevisionActionRequest(BaseModel):
    revision_ids: List[str]

class AddCommentRequest(BaseModel):
    text: str
    range: Optional[Dict[str, Any]] = None

class ReplyCommentRequest(BaseModel):
    text: str

class SyncPresenceRequest(BaseModel):
    status: str = "active"

class ManageConflictRequest(BaseModel):
    conflict_data: Dict[str, Any]

# --- Track Changes Endpoints ---

@router.get("/{document_id}/word/track-changes/status")
async def get_track_changes_status(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user)
):
    """Check if Track Changes is enabled for document."""
    logger.info("Entering get_track_changes_status", document_id=str(document_id))
    result = await track_changes_service.get_track_changes_status(document_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/track-changes/enable")
async def enable_track_changes(
    document_id: UUID,
    request: EnableTrackChangesRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Enable or disable Track Changes for document."""
    logger.info("Entering enable_track_changes", document_id=str(document_id), enabled=request.enabled)
    result = await track_changes_service.enable_track_changes(document_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/fixes/apply")
async def apply_ai_edit(
    document_id: UUID,
    request: ApplyAiEditRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Apply an AI edit as a tracked change."""
    logger.info("Entering apply_ai_edit", document_id=str(document_id))
    author_info = {"id": str(current_user.id), "name": current_user.display_name or "AI"}
    result = await track_changes_service.apply_ai_edit_with_track_changes(
        document_id,
        request.finding_text,
        request.replacement_text,
        request.occurrence_index,
        author_info
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/fixes/bulk-apply")
async def bulk_apply_ai_edits(
    document_id: UUID,
    request: BulkApplyAiEditsRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Apply multiple AI fixes as tracked changes."""
    logger.info("Entering bulk_apply_ai_edits", document_id=str(document_id))
    author_info = {"id": str(current_user.id), "name": current_user.display_name or "AI"}
    result = await track_changes_service.bulk_apply_fixes_with_track_changes(
        document_id,
        request.fixes,
        author_info
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.get("/{document_id}/word/track-changes/revisions")
async def get_tracked_changes(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user)
):
    """Get all tracked changes in document."""
    logger.info("Entering get_tracked_changes", document_id=str(document_id))
    result = await track_changes_service.get_tracked_changes(document_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/track-changes/revisions/accept")
async def accept_revisions(
    document_id: UUID,
    request: RevisionActionRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Accept specified tracked changes."""
    logger.info("Entering accept_revisions", document_id=str(document_id))
    result = await track_changes_service.accept_revisions(document_id, request.revision_ids)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/track-changes/revisions/reject")
async def reject_revisions(
    document_id: UUID,
    request: RevisionActionRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Reject specified tracked changes."""
    logger.info("Entering reject_revisions", document_id=str(document_id))
    result = await track_changes_service.reject_revisions(document_id, request.revision_ids)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

# --- Comments Endpoints ---

@router.get("/{document_id}/word/comments")
async def get_comments(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user)
):
    """Get all native Word comments in document."""
    logger.info("Entering get_comments", document_id=str(document_id))
    result = await comments_service.get_comments(document_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/comments")
async def add_comment(
    document_id: UUID,
    request: AddCommentRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Add a native Word comment."""
    logger.info("Entering add_comment", document_id=str(document_id))
    author_info = {"id": str(current_user.id), "name": current_user.display_name or "User"}
    result = await comments_service.add_comment(document_id, request.text, author_info, request.range)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/comments/{comment_id}/reply")
async def reply_to_comment(
    document_id: UUID,
    comment_id: str,
    request: ReplyCommentRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Reply to a native Word comment."""
    logger.info("Entering reply_to_comment", document_id=str(document_id), comment_id=comment_id)
    author_info = {"id": str(current_user.id), "name": current_user.display_name or "User"}
    result = await comments_service.reply_to_comment(document_id, comment_id, request.text, author_info)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/comments/{comment_id}/resolve")
async def resolve_comment(
    document_id: UUID,
    comment_id: str,
    current_user: UserClaims = Depends(get_current_user)
):
    """Resolve a native Word comment."""
    logger.info("Entering resolve_comment", document_id=str(document_id), comment_id=comment_id)
    result = await comments_service.resolve_comment(document_id, comment_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

# --- Co-authoring Endpoints ---

@router.get("/{document_id}/word/coauthoring/editors")
async def get_active_editors(
    document_id: UUID,
    current_user: UserClaims = Depends(get_current_user)
):
    """Get list of active editors in the document."""
    logger.info("Entering get_active_editors", document_id=str(document_id))
    result = await coauthoring_service.get_active_editors(document_id)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/coauthoring/presence")
async def sync_presence(
    document_id: UUID,
    request: SyncPresenceRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Sync user presence in a co-authoring session."""
    logger.info("Entering sync_presence", document_id=str(document_id))
    user_info = {"id": str(current_user.id), "name": current_user.display_name or "User"}
    result = await coauthoring_service.sync_presence(document_id, user_info, request.status)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result

@router.post("/{document_id}/word/coauthoring/conflicts")
async def manage_conflicts(
    document_id: UUID,
    request: ManageConflictRequest,
    current_user: UserClaims = Depends(get_current_user)
):
    """Manage editing conflicts between users."""
    logger.info("Entering manage_conflicts", document_id=str(document_id))
    result = await coauthoring_service.manage_conflicts(document_id, request.conflict_data)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    return result
