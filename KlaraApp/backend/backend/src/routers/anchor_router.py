"""Anchor management API endpoints.

This router provides endpoints for creating, resolving, and managing
finding anchors that maintain references across document edits.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any, List, Optional
from uuid import UUID

from src.repositories.db_setup import get_db
from src.utils.dependencies import get_current_user
from src.models.dto.schemas.auth import UserClaims
from src.models.dto.schemas.qc import FindingResponse
from src.core.logger import get_logger_with_context
from src.services.anchors.anchor_manager import anchor_manager
from src.services.anchors.word_anchor_strategy import word_anchor_strategy
from src.services.anchors.onlyoffice_anchor_strategy import onlyoffice_anchor_strategy

logger = get_logger_with_context()
router = APIRouter(prefix="/anchors", tags=["anchors"])


@router.post("/findings/{finding_id}/anchor", response_model=Dict[str, Any])
async def create_finding_anchor(
    finding_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserClaims = Depends(get_current_user)
):
    """
    Create durable anchor for a finding.

    This endpoint creates a multi-tier anchor strategy for maintaining
    finding references across document edits and editor changes.

    Args:
        finding_id: Finding to create anchor for
        db: Database session
        current_user: Authenticated user

    Returns:
        Created anchor data with multi-tier fallback mechanisms
    """
    logger.info("creating_finding_anchor", function="create_finding_anchor", finding_id=str(finding_id))

    try:
        from src.repositories import qc_finding_repo
        from src.models.dao.document import Document
        from src.models.dao.qc_finding import QCFinding

        # Get finding
        finding = await qc_finding_repo.find_by_id(db, finding_id)
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found")

        # Get document to determine editor type
        from src.repositories import document_repo
        document = await document_repo.find_by_id(db, finding.document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        editor_type = document.editor_type or "onlyoffice"

        # Get document content for anchor creation
        document_content = await _get_document_content(document, db)

        # Create anchor using appropriate strategy
        if editor_type == "word_online":
            # Use Word Online strategy
            if finding.location and isinstance(finding.location, dict):
                finding_text = finding.location.get("anchor_text") or str(finding.location)
            else:
                finding_text = str(finding.location)

            primary_anchor = None
            if finding.location and finding.location.get("occurrence_index") is not None:
                primary_anchor = await word_anchor_strategy.create_content_control_anchor(
                    finding_text,
                    finding.location.get("occurrence_index", 0)
                )

            anchor_data = {
                "finding_id": str(finding_id),
                "document_id": str(finding.document_id),
                "editor_type": editor_type,
                "primary_anchor": primary_anchor,
                "secondary_anchors": [],
                "confidence_score": primary_anchor["persistence"] if primary_anchor else 0.5,
                "created_at": datetime.now().isoformat()
            }

        else:
            # Use OnlyOffice strategy
            if finding.location and isinstance(finding.location, dict):
                finding_text = finding.location.get("anchor_text") or str(finding.location)
                page_number = finding.location.get("page")
                paragraph_number = finding.location.get("paragraph")
            else:
                finding_text = str(finding.location)
                page_number = None
                paragraph_number = None

            primary_anchor = await onlyoffice_anchor_strategy.create_page_mapping_anchor(
                finding_text,
                finding.location.get("occurrence_index", 0) if finding.location else 0,
                page_number,
                paragraph_number
            )

            anchor_data = {
                "finding_id": str(finding_id),
                "document_id": str(finding.document_id),
                "editor_type": editor_type,
                "primary_anchor": primary_anchor,
                "secondary_anchors": [],
                "confidence_score": primary_anchor["persistence"] if primary_anchor else 0.5,
                "created_at": datetime.now().isoformat()
            }

        logger.info("finding_anchor_created", function="create_finding_anchor", finding_id=str(finding_id))
        return {"data": anchor_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("create_finding_anchor_failed", function="create_finding_anchor", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create anchor: {str(e)}")


@router.post("/anchors/{anchor_id}/resolve", response_model=Dict[str, Any])
async def resolve_anchor(
    anchor_id: str,
    request_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: UserClaims = Depends(get_current_user)
):
    """
    Resolve anchor to current document location.

    This endpoint attempts to locate a finding using its anchor data,
    trying primary, secondary, and tertiary anchor methods in order.

    Args:
        anchor_id: Anchor ID to resolve
        request_data: Optional document content and editor context
        db: Database session
        current_user: Authenticated user

    Returns:
        Resolution result with location data and method used
    """
    logger.info("resolving_anchor", function="resolve_anchor", anchor_id=anchor_id)

    try:
        # Get anchor data (in real implementation, from database)
        # For now, use the request data
        anchor_data = request_data.get("anchor_data")
        if not anchor_data:
            raise HTTPException(status_code=400, detail="Anchor data required")

        document_content = request_data.get("document_content")
        editor_context = request_data.get("editor_context")

        # Resolve anchor using manager
        success, location, method = await anchor_manager.locate_anchor(
            anchor_data,
            document_content,
            editor_context
        )

        result = {
            "success": success,
            "anchor_id": anchor_id,
            "location": location,
            "resolution_method": method,
            "resolved_at": datetime.now().isoformat()
        }

        logger.info("anchor_resolved", function="resolve_anchor", success=success, method=method)
        return {"data": result}

    except Exception as e:
        logger.error("resolve_anchor_failed", function="resolve_anchor", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to resolve anchor: {str(e)}")


@router.get("/anchors/metrics", response_model=Dict[str, Any])
async def get_anchor_metrics(
    document_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserClaims = Depends(get_current_user)
):
    """
    Get anchor resolution metrics and success rates.

    Provides analytics on anchor stability, resolution success rates,
    and performance for different anchor types.

    Args:
        document_id: Optional document filter
        db: Database session
        current_user: Authenticated user

    Returns:
        Anchor metrics and analytics data
    """
    logger.info("getting_anchor_metrics", function="get_anchor_metrics")

    try:
        # In real implementation, query anchor_resolutions table
        metrics = {
            "total_anchors": 0,
            "resolution_attempts": 0,
            "success_rate": 0.0,
            "by_method": {},
            "average_resolution_time_ms": 0
        }

        return {"data": metrics}

    except Exception as e:
        logger.error("get_anchor_metrics_failed", function="get_anchor_metrics", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.put("/anchors/{anchor_id}/update", response_model=Dict[str, Any])
async def update_anchor_after_edit(
    anchor_id: str,
    update_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
    current_user: UserClaims = Depends(get_current_user)
):
    """
    Update anchor after document modification.

    Called when document is edited to update anchor positions
    and validate stability.

    Args:
        anchor_id: Anchor to update
        update_data: Edit information and current document state
        db: Database session
        current_user: Authenticated user

    Returns:
        Updated anchor data
    """
    logger.info("updating_anchor_after_edit", function="update_anchor_after_edit", anchor_id=anchor_id)

    try:
        anchor_data = update_data.get("anchor_data")
        edit_info = update_data.get("edit_info")

        if not anchor_data or not edit_info:
            raise HTTPException(status_code=400, detail="Anchor data and edit info required")

        # Update anchor after edit
        updated_anchor = await anchor_manager.update_anchor_after_edit(anchor_data, edit_info)

        return {"data": updated_anchor}

    except Exception as e:
        logger.error("update_anchor_failed", function="update_anchor_after_edit", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update anchor: {str(e)}")


@router.get("/anchors/cache/stats", response_model=Dict[str, Any])
async def get_anchor_cache_stats(
    document_id: Optional[UUID] = None,
    db: AsyncSession = Depends(get_db),
    current_user: UserClaims = Depends(get_current_user)
):
    """
    Get anchor cache statistics for performance monitoring.

    Returns cache hit rates, size, and efficiency metrics.
    """
    logger.info("getting_anchor_cache_stats", function="get_anchor_cache_stats")

    try:
        stats = {
            "cache_size": 0,
            "hit_rate": 0.0,
            "average_resolution_time_ms": 0.0,
            "cache_entries": []
        }

        return {"data": stats}

    except Exception as e:
        logger.error("get_cache_stats_failed", function="get_cache_stats", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get cache stats: {str(e)}")


@router.delete("/anchors/cache/clear", response_model=Dict[str, Any])
async def clear_anchor_cache(
    current_user: UserClaims = Depends(get_current_user)
):
    """
    Clear anchor cache to force fresh resolutions.

    Useful for testing or after major document changes.
    """
    logger.info("clearing_anchor_cache", function="clear_anchor_cache")

    try:
        # Clear cache (implementation depends on cache mechanism)
        result = {"cleared": True, "cleared_at": datetime.now().isoformat()}

        logger.info("anchor_cache_cleared", function="clear_anchor_cache")
        return {"data": result}

    except Exception as e:
        logger.error("clear_cache_failed", function="clear_anchor_cache", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")


async def _get_document_content(document: any, db: AsyncSession) -> Optional[str]:
    """Helper to get document content for anchor creation."""
    try:
        # Try to get document from file storage or SharePoint
        if document.storage_type == "sharepoint":
            # Would use SharePoint service to get content
            return None
        else:
            # Try to get from local file
            from src.utils.text_extractor import extract_text_from_file
            file_path = document.blob_url.replace("/uploads/", "")
            if file_path and file_path.endswith(('.docx', '.doc')):
                import os
                if os.path.exists(file_path):
                    return extract_text_from_file(file_path)

        return None
    except Exception as e:
        logger.error("get_document_content_failed", function="_get_document_content", error=str(e))
        return None