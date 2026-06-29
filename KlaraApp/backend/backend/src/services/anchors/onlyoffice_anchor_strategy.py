"""OnlyOffice anchor strategy using page mapping and custom metadata.

This module provides durable anchoring strategies specific to OnlyOffice Document Server,
utilizing page/paragraph mapping, bookmarks, and custom metadata for maintaining finding
references across document edits and modifications.
"""

import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from src.core.logger import get_logger_with_context
from .anchor_manager import AnchorType, AnchorConfidence

logger = get_logger_with_context()


class OnlyOfficeAnchorStrategy:
    """
    OnlyOffice-specific anchor strategy implementation.

    Uses OnlyOffice Document Server features for durable finding references:
    - Page/Paragraph mapping (existing Klara system)
    - Custom metadata injection
    - Bookmark creation
    - Content Control insertion
    - Structural markers
    """

    async def create_page_mapping_anchor(
        self,
        finding_text: str,
        occurrence_index: int,
        page_number: Optional[int] = None,
        paragraph_number: Optional[int] = None,
        document_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create page/paragraph mapping-based anchor for finding.

        OnlyOffice provides page and paragraph mapping that Klara already uses.
        This leverages the existing Klara page mapping system.

        Args:
            finding_text: Text to anchor to
            occurrence_index: Which occurrence to use
            page_number: Page number if available
            paragraph_number: Paragraph number if available
            document_context: OnlyOffice document context

        Returns:
            Page mapping anchor data or None
        """
        logger.info(
            "creating_page_mapping_anchor",
            function="create_page_mapping_anchor",
            page_number=page_number,
            paragraph_number=paragraph_number
        )

        try:
            # Generate unique anchor identifier
            anchor_id = str(uuid.uuid4())

            anchor_data = {
                "type": "page_offset",
                "anchor_id": anchor_id,
                "finding_text": finding_text,
                "occurrence_index": occurrence_index,
                "page_number": page_number,
                "paragraph_number": paragraph_number,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "method": "onlyoffice_page_mapping",
                "persistence": "medium"
            }

            # In actual implementation, this would:
            # 1. Use OnlyOffice API to get page/paragraph info
            # 2. Store the mapping in document metadata
            # 3. Create cross-reference

            logger.info("page_mapping_anchor_created", function="create_page_mapping_anchor", anchor_id=anchor_id)
            return anchor_data

        except Exception as e:
            logger.error("page_mapping_anchor_failed", function="create_page_mapping_anchor", error=str(e))
            return None

    async def create_onlyoffice_bookmark_anchor(
        self,
        finding_text: str,
        occurrence_index: int,
        document_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create OnlyOffice-specific bookmark anchor.

        OnlyOffice bookmarks are different from Word bookmarks:
        - They're created via OnlyOffice API
        - They have different persistence characteristics
        - They may not survive all document operations

        Args:
            finding_text: Text to anchor to
            occurrence_index: Which occurrence to use
            document_context: OnlyOffice document context

        Returns:
            OnlyOffice bookmark anchor data or None
        """
        logger.info(
            "creating_onlyoffice_bookmark_anchor",
            function="create_onlyoffice_bookmark_anchor",
            occurrence_index=occurrence_index
        )

        if not document_context:
            return None

        try:
            # Generate unique bookmark name
            bookmark_name = f"oo_finding_{uuid.uuid4().hex[:8]}"

            anchor_data = {
                "type": AnchorType.BOOKMARK,
                "bookmark_name": bookmark_name,
                "finding_text": finding_text,
                "occurrence_index": occurrence_index,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "method": "onlyoffice_bookmark",
                "persistence": "low_medium"
            }

            # In actual implementation, this would:
            # 1. Use OnlyOffice DocsAPI to create bookmark
            # 2. Store the bookmark name
            # 3. Associate with finding metadata

            logger.info("onlyoffice_bookmark_anchor_created", function="create_onlyoffice_bookmark_anchor", bookmark=bookmark_name)
            return anchor_data

        except Exception as e:
            logger.error("onlyoffice_bookmark_anchor_failed", function="create_onlyoffice_bookmark_anchor", error=str(e))
            return None

    async def create_custom_metadata_anchor(
        self,
        finding_text: str,
        occurrence_index: int,
        finding_id: str,
        document_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create custom metadata anchor in OnlyOffice document.

        OnlyOffice allows custom metadata injection via document properties:
        - Document-level metadata
        - Paragraph-level metadata
        - Range-level metadata

        Args:
            finding_text: Text to anchor to
            occurrence_index: Which occurrence to use
            finding_id: Finding ID for metadata
            document_context: OnlyOffice document context

        Returns:
            Custom metadata anchor data or None
        """
        logger.info(
            "creating_custom_metadata_anchor",
            function="create_custom_metadata_anchor",
            finding_id=finding_id
        )

        if not document_context:
            return None

        try:
            # Generate unique metadata key
            metadata_key = f"klara_finding_{finding_id}"

            # Create metadata structure
            metadata_value = {
                "finding_id": finding_id,
                "anchor_text": finding_text,
                "occurrence_index": occurrence_index,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "klara_version": "1.0"
            }

            anchor_data = {
                "type": "custom_xml",
                "metadata_key": metadata_key,
                "metadata_value": metadata_value,
                "finding_text": finding_text,
                "occurrence_index": occurrence_index,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "method": "onlyoffice_custom_metadata",
                "persistence": "medium"
            }

            # In actual implementation, this would:
            # 1. Use OnlyOffice API to set document property
            # 2. Store structured metadata
            # 3. Create lookup reference

            logger.info("custom_metadata_anchor_created", function="create_custom_metadata_anchor", metadata_key=metadata_key)
            return anchor_data

        except Exception as e:
            logger.error("custom_metadata_anchor_failed", function="create_custom_metadata_anchor", error=str(e))
            return None

    async def create_context_search_anchor(
        self,
        finding_text: str,
        occurrence_index: int,
        document_content: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create context-based search anchor for OnlyOffice.

        Uses surrounding text context to make finding more robust:
        - Text before and after finding
        - Paragraph context
        - Section headers
        - Formatting patterns

        Args:
            finding_text: Text to anchor to
            occurrence_index: Which occurrence to use
            document_content: Document text content

        Returns:
            Context search anchor data or None
        """
        logger.info(
            "creating_context_search_anchor",
            function="create_context_search_anchor"
        )

        if not document_content:
            return None

        try:
            # Find the specific occurrence
            context = self._find_occurrence_context(document_content, finding_text, occurrence_index)

            if context:
                anchor_data = {
                    "type": "context_search",
                    "finding_text": finding_text,
                    "occurrence_index": occurrence_index,
                    "context_before": context.get("before"),
                    "context_after": context.get("after"),
                    "paragraph_context": context.get("paragraph"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "method": "onlyoffice_context_search",
                    "persistence": "low"
                }

                logger.info("context_search_anchor_created", function="create_context_search_anchor")
                return anchor_data

            return None

        except Exception as e:
            logger.error("context_search_anchor_failed", function="create_context_search_anchor", error=str(e))
            return None

    async def resolve_page_mapping_anchor(
        self,
        anchor_data: Dict[str, Any],
        editor_context: Optional[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Resolve page mapping anchor to actual document location.

        Args:
            anchor_data: Page mapping anchor data
            editor_context: OnlyOffice API context

        Returns:
            Tuple of (success, location_data, method_used)
        """
        logger.info("resolving_page_mapping_anchor", function="resolve_page_mapping_anchor")

        try:
            if not editor_context:
                return False, None, None

            page_number = anchor_data.get("page_number")
            paragraph_number = anchor_data.get("paragraph_number")
            finding_text = anchor_data.get("finding_text")

            # In actual implementation with OnlyOffice DocsAPI:
            # 1. Navigate to page/paragraph
            # 2. Search for text within that region
            # 3. Return exact position

            # Simulated resolution:
            location_data = {
                "type": "page_mapping",
                "page_number": page_number,
                "paragraph_number": paragraph_number,
                "finding_text": finding_text,
                "found": True
            }

            logger.info("page_mapping_resolved", function="resolve_page_mapping_anchor", page=page_number)
            return True, location_data, "page_mapping_resolution"

        except Exception as e:
            logger.error("page_mapping_resolution_failed", function="resolve_page_mapping_anchor", error=str(e))
            return False, None, None

    def _find_occurrence_context(
        self,
        document_content: str,
        finding_text: str,
        occurrence_index: int,
        context_chars: int = 150
    ) -> Optional[Dict[str, Any]]:
        """
        Find context around specific occurrence of text.

        Args:
            document_content: Full document text
            finding_text: Text to find
            occurrence_index: Which occurrence to use
            context_chars: Characters of context to extract

        Returns:
            Context dictionary with surrounding information
        """
        try:
            # Find all occurrences
            occurrences = []
            index = 0
            while True:
                index = document_content.lower().find(finding_text.lower(), index)
                if index == -1:
                    break
                occurrences.append(index)
                index += len(finding_text)

            if occurrence_index >= len(occurrences):
                return None

            position = occurrences[occurrence_index]

            # Extract context
            start_context = max(0, position - context_chars)
            end_context = min(len(document_content), position + len(finding_text) + context_chars)

            context_before = document_content[start_context:position]
            context_after = document_content[position + len(finding_text):end_context]

            # Try to get paragraph context
            paragraph = self._extract_paragraph_context(document_content, position)

            return {
                "before": context_before,
                "after": context_after,
                "paragraph": paragraph,
                "position": position
            }

        except Exception as e:
            logger.error("find_occurrence_context_failed", function="_find_occurrence_context", error=str(e))
            return None

    def _extract_paragraph_context(self, document_content: str, position: int) -> Optional[str]:
        """Extract the paragraph containing the position."""
        try:
            # Find paragraph boundaries around position
            paragraph_start = document_content.rfind('\n\n', 0, position)
            paragraph_end = document_content.find('\n\n', position)

            if paragraph_start == -1:
                paragraph_start = 0
            else:
                paragraph_start += 2  # Skip the newlines

            if paragraph_end == -1:
                paragraph_end = len(document_content)

            return document_content[paragraph_start:paragraph_end].strip()

        except Exception as e:
            logger.error("extract_paragraph_context_failed", function="_extract_paragraph_context", error=str(e))
            return None


class OnlyOfficeEditTracking:
    """
    Track document edits to maintain anchor validity.

    OnlyOffice editing sessions can affect anchor stability:
    - Auto-save operations
    - Collaborative editing
    - Force save events
    """

    async def track_edit_operation(
        self,
        anchor_data: Dict[str, Any],
        edit_operation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Track document edit operation and update anchor if needed.

        Args:
            anchor_data: Current anchor data
            edit_operation: Information about the edit

        Returns:
            Updated anchor data after edit tracking
        """
        logger.info("tracking_edit_operation", function="track_edit_operation")

        # Determine if edit affects anchor
        affects_anchor = await self._edit_affects_anchor(anchor_data, edit_operation)

        if affects_anchor:
            # Try to update anchor position
            updated_anchor = await self._update_anchor_position(anchor_data, edit_operation)
            logger.info("anchor_position_updated", function="track_edit_operation")
            return updated_anchor

        return anchor_data

    async def _edit_affects_anchor(
        self,
        anchor_data: Dict[str, Any],
        edit_operation: Dict[str, Any]
    ) -> bool:
        """Determine if edit operation affects anchor location."""
        # Implementation would check if edit is in anchor region
        return False

    async def _update_anchor_position(
        self,
        anchor_data: Dict[str, Any],
        edit_operation: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update anchor position after edit."""
        # Implementation would recalculate anchor position
        return anchor_data


# Global instances
onlyoffice_anchor_strategy = OnlyOfficeAnchorStrategy()
onlyoffice_edit_tracking = OnlyOfficeEditTracking()
