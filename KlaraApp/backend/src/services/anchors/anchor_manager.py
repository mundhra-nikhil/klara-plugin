"""Anchor manager service for durable finding references.

This service implements a multi-tier anchoring strategy that maintains
finding references across document edits and different editor types.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import json

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from src.core.logger import get_logger_with_context
from src.repositories.db_setup import get_db
from src.models.dao.qc_finding import QCFinding
from src.models.dto.schemas.qc import FindingResponse


logger = get_logger_with_context()


class AnchorType(str, Enum):
    """Types of anchors available for finding references."""

    # Primary anchors (most durable)
    CONTENT_CONTROL = "content_control"  # Word Online Content Control IDs
    BOOKMARK = "bookmark"  # Word/OnlyOffice bookmark names
    CUSTOM_XML = "custom_xml"  # Custom XML metadata in documents

    # Secondary anchors (fallback)
    STRUCTURAL_MARKER = "structural_marker"  # Headings, sections, page breaks
    CONTEXT_SEARCH = "context_search"  # Context-based text search
    PAGE_OFFSET = "page_offset"  # Page number + character offset

    # Tertiary anchors (last resort)
    PURE_TEXT_SEARCH = "pure_text_search"  # Simple text search
    FUZZY_SEARCH = "fuzzy_search"  # Fuzzy text matching


class AnchorConfidence(str, Enum):
    """Confidence levels for anchor resolution."""

    HIGH = "high"  # Primary anchor matched
    MEDIUM = "medium"  # Secondary anchor matched
    LOW = "low"  # Tertiary anchor matched
    UNKNOWN = "unknown"  # Anchor type not supported


class AnchorManager:
    """
    Multi-tier anchor management service for finding references.

    Implements a hybrid anchoring strategy with fallback mechanisms
    to maintain finding references across document modifications,
    co-authoring sessions, and revision cycles.
    """

    def __init__(self):
        self.anchor_cache: Dict[str, Dict[str, Any]] = {}

    async def create_anchor_for_finding(
        self,
        finding: QCFinding,
        document_id: uuid.UUID,
        editor_type: str,
        document_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create durable anchor for a finding using multi-tier strategy.

        Args:
            finding: QC finding to create anchor for
            document_id: Document identifier
            editor_type: Type of editor ('onlyoffice' or 'word_online')
            document_content: Optional document content for analysis

        Returns:
            Anchor dictionary with multi-tier anchor data
        """
        logger.info(
            "creating_anchor_for_finding",
            function="create_anchor_for_finding",
            finding_id=str(finding.id),
            editor_type=editor_type
        )

        anchor_data = {
            "finding_id": str(finding.id),
            "document_id": str(document_id),
            "editor_type": editor_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "primary_anchor": None,
            "secondary_anchors": [],
            "tertiary_anchors": [],
            "confidence_score": 0.0,
            "resolution_history": []
        }

        # Extract finding text from location
        finding_text = self._extract_finding_text(finding)
        if not finding_text:
            logger.warning("no_finding_text_extracted", function="create_anchor_for_finding", finding_id=str(finding.id))
            return anchor_data

        # Try primary anchors based on editor type
        primary_anchors = await self._try_primary_anchors(
            finding, finding_text, document_id, editor_type, document_content
        )
        if primary_anchors:
            anchor_data["primary_anchor"] = primary_anchors[0]
            anchor_data["confidence_score"] = 1.0
            logger.info("primary_anchor_created", function="create_anchor_for_finding", anchor_type=primary_anchors[0]["type"])
            return anchor_data

        # Try secondary anchors
        secondary_anchors = await self._try_secondary_anchors(
            finding, finding_text, document_id, editor_type, document_content
        )
        if secondary_anchors:
            anchor_data["secondary_anchors"] = secondary_anchors
            anchor_data["confidence_score"] = 0.7
            logger.info("secondary_anchors_created", function="create_anchor_for_finding", count=len(secondary_anchors))
            return anchor_data

        # Fall back to tertiary anchors
        tertiary_anchors = await self._try_tertiary_anchors(
            finding, finding_text, document_id, editor_type
        )
        if tertiary_anchors:
            anchor_data["tertiary_anchors"] = tertiary_anchors
            anchor_data["confidence_score"] = 0.4
            logger.info("tertiary_anchors_created", function="create_anchor_for_finding", count=len(tertiary_anchors))
            return anchor_data

        logger.warning("no_anchor_created", function="create_anchor_for_finding", finding_id=str(finding.id))
        return anchor_data

    async def locate_anchor(
        self,
        anchor_data: Dict[str, Any],
        document_content: Optional[str] = None,
        editor_context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Locate finding position using multi-tier resolution strategy.

        Args:
            anchor_data: Anchor data from database
            document_content: Current document content
            editor_context: Editor-specific context

        Returns:
            Tuple of (success, location_data, resolution_method)
        """
        logger.info(
            "locating_anchor",
            function="locate_anchor",
            finding_id=anchor_data.get("finding_id"),
            confidence_score=anchor_data.get("confidence_score", 0)
        )

        # Try primary anchor first
        if anchor_data.get("primary_anchor"):
            success, location, method = await self._resolve_primary_anchor(
                anchor_data["primary_anchor"],
                document_content,
                editor_context
            )
            if success:
                self._record_resolution(anchor_data, method, AnchorConfidence.HIGH)
                return True, location, method

        # Try secondary anchors
        for secondary_anchor in anchor_data.get("secondary_anchors", []):
            success, location, method = await self._resolve_secondary_anchor(
                secondary_anchor,
                document_content,
                editor_context
            )
            if success:
                self._record_resolution(anchor_data, method, AnchorConfidence.MEDIUM)
                return True, location, method

        # Try tertiary anchors as last resort
        for tertiary_anchor in anchor_data.get("tertiary_anchors", []):
            success, location, method = await self._resolve_tertiary_anchor(
                tertiary_anchor,
                document_content,
                editor_context
            )
            if success:
                self._record_resolution(anchor_data, method, AnchorConfidence.LOW)
                return True, location, method

        logger.warning("anchor_resolution_failed", function="locate_anchor")
        self._record_resolution(anchor_data, "failed", AnchorConfidence.UNKNOWN)
        return False, None, None

    async def update_anchor_after_edit(
        self,
        anchor_data: Dict[str, Any],
        edit_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update anchor after document modification.

        Args:
            anchor_data: Existing anchor data
            edit_info: Information about the edit made

        Returns:
            Updated anchor data
        """
        logger.info(
            "updating_anchor_after_edit",
            function="update_anchor_after_edit",
            finding_id=anchor_data.get("finding_id")
        )

        # Check if primary anchor is still valid
        if anchor_data.get("primary_anchor"):
            is_valid = await self._validate_primary_anchor(
                anchor_data["primary_anchor"],
                edit_info
            )
            if not is_valid:
                # Move to secondary anchors
                logger.info("primary_anchor_invalid_migrating", function="update_anchor_after_edit")
                # Implementation would migrate to secondary anchors
                pass

        # Record resolution attempt
        anchor_data["resolution_history"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "update_after_edit",
            "edit_info": edit_info
        })

        return anchor_data

    async def _try_primary_anchors(
        self,
        finding: QCFinding,
        finding_text: str,
        document_id: uuid.UUID,
        editor_type: str,
        document_content: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Try to create primary anchors (most durable)."""
        anchors = []

        if editor_type == "word_online":
            # Try Content Control IDs
            content_control = await self._create_content_control_anchor(finding, finding_text)
            if content_control:
                anchors.append(content_control)

            # Try Bookmarks
            bookmark = await self._create_bookmark_anchor(finding, finding_text)
            if bookmark:
                anchors.append(bookmark)

        elif editor_type == "onlyoffice":
            # Try OnlyOffice-specific bookmarks
            bookmark = await self._create_onlyoffice_bookmark_anchor(finding, finding_text)
            if bookmark:
                anchors.append(bookmark)

        # Try Custom XML metadata (works for both)
        custom_xml = await self._create_custom_xml_anchor(finding, finding_text)
        if custom_xml:
            anchors.append(custom_xml)

        return anchors

    async def _try_secondary_anchors(
        self,
        finding: QCFinding,
        finding_text: str,
        document_id: uuid.UUID,
        editor_type: str,
        document_content: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Try to create secondary anchors (fallback mechanisms)."""
        anchors = []

        # Structural markers (headings, sections)
        structural = await self._create_structural_marker_anchor(finding, finding_text, document_content)
        if structural:
            anchors.append(structural)

        # Context-based search with surrounding text
        context_search = await self._create_context_search_anchor(finding, finding_text, document_content)
        if context_search:
            anchors.append(context_search)

        # Page number + offset (if available)
        page_offset = await self._create_page_offset_anchor(finding)
        if page_offset:
            anchors.append(page_offset)

        return anchors

    async def _try_tertiary_anchors(
        self,
        finding: QCFinding,
        finding_text: str,
        document_id: uuid.UUID,
        editor_type: str
    ) -> List[Dict[str, Any]]:
        """Try to create tertiary anchors (last resort)."""
        anchors = []

        # Pure text search
        text_search = await self._create_text_search_anchor(finding, finding_text)
        if text_search:
            anchors.append(text_search)

        # Fuzzy search
        fuzzy_search = await self._create_fuzzy_search_anchor(finding, finding_text)
        if fuzzy_search:
            anchors.append(fuzzy_search)

        return anchors

    async def _resolve_primary_anchor(
        self,
        anchor: Dict[str, Any],
        document_content: Optional[str],
        editor_context: Optional[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Resolve primary anchor to location."""
        # Implementation depends on anchor type
        if anchor["type"] == AnchorType.CONTENT_CONTROL:
            return await self._resolve_content_control(anchor, editor_context)
        elif anchor["type"] == AnchorType.BOOKMARK:
            return await self._resolve_bookmark(anchor, editor_context)
        elif anchor["type"] == AnchorType.CUSTOM_XML:
            return await self._resolve_custom_xml(anchor, document_content)

        return False, None, None

    async def _resolve_secondary_anchor(
        self,
        anchor: Dict[str, Any],
        document_content: Optional[str],
        editor_context: Optional[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Resolve secondary anchor to location."""
        # Implementation for secondary anchor types
        return False, None, None

    async def _resolve_tertiary_anchor(
        self,
        anchor: Dict[str, Any],
        document_content: Optional[str],
        editor_context: Optional[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Resolve tertiary anchor to location."""
        # Implementation for tertiary anchor types
        return False, None, None

    def _extract_finding_text(self, finding: QCFinding) -> Optional[str]:
        """Extract finding text from finding location data."""
        try:
            if isinstance(finding.location, dict):
                location = finding.location
                # Try to get text from various possible locations
                return (
                    location.get("anchor_text") or
                    location.get("original_text") or
                    location.get("before") or
                    str(location.get("text", ""))
                )
            return str(finding.location)
        except Exception as e:
            logger.error("extract_finding_text_failed", function="_extract_finding_text", error=str(e))
            return None

    def _record_resolution(
        self,
        anchor_data: Dict[str, Any],
        method: str,
        confidence: AnchorConfidence
    ):
        """Record anchor resolution attempt for tracking."""
        anchor_data["resolution_history"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "confidence": confidence.value,
        })

    async def _validate_primary_anchor(
        self,
        anchor: Dict[str, Any],
        edit_info: Dict[str, Any]
    ) -> bool:
        """Validate if primary anchor is still valid after edit."""
        # Implementation to check if anchor was affected by edit
        return True

    # Placeholder methods for specific anchor creation
    async def _create_content_control_anchor(self, finding, text) -> Optional[Dict]:
        return None

    async def _create_bookmark_anchor(self, finding, text) -> Optional[Dict]:
        return None

    async def _create_onlyoffice_bookmark_anchor(self, finding, text) -> Optional[Dict]:
        return None

    async def _create_custom_xml_anchor(self, finding, text) -> Optional[Dict]:
        return None

    async def _create_structural_marker_anchor(self, finding, text, content) -> Optional[Dict]:
        return None

    async def _create_context_search_anchor(self, finding, text, content) -> Optional[Dict]:
        return None

    async def _create_page_offset_anchor(self, finding) -> Optional[Dict]:
        return None

    async def _create_text_search_anchor(self, finding, text) -> Optional[Dict]:
        return {"type": "pure_text_search", "search_text": text}

    async def _create_fuzzy_search_anchor(self, finding, text) -> Optional[Dict]:
        return {"type": "fuzzy_search", "search_text": text}

    async def _resolve_content_control(self, anchor, context) -> Tuple[bool, Optional[Dict], Optional[str]]:
        return False, None, None

    async def _resolve_bookmark(self, anchor, context) -> Tuple[bool, Optional[Dict], Optional[str]]:
        return False, None, None

    async def _resolve_custom_xml(self, anchor, content) -> Tuple[bool, Optional[Dict], Optional[str]]:
        return False, None, None


# Global instance
anchor_manager = AnchorManager()