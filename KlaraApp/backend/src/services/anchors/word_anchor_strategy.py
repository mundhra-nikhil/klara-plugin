"""Word Online anchor strategy using Content Controls and Word features.

This module provides durable anchoring strategies specific to Microsoft Word Online,
utilizing Content Controls, Bookmarks, and Custom XML for maintaining finding references
across document edits and co-authoring sessions.
"""

import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from src.core.logger import get_logger_with_context
from .anchor_manager import AnchorType, AnchorConfidence

logger = get_logger_with_context()


class WordAnchorStrategy:
    """
    Word Online-specific anchor strategy implementation.

    Uses Word JavaScript API features for durable finding references:
    - Content Control IDs (most durable)
    - Bookmarks (moderately durable)
    - Custom XML parts (moderately durable)
    - Structural markers (fallback)
    - Context-based search (last resort)
    """

    async def create_content_control_anchor(
        self,
        finding_text: str,
        occurrence_index: int,
        document_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create Content Control-based anchor for finding.

        Content Controls in Word are the most durable anchors because:
        - They have unique IDs that persist across edits
        - They survive co-authoring sessions
        - They're maintained through document revisions
        - They can be programmatically managed

        Args:
            finding_text: Text to anchor to
            occurrence_index: Which occurrence to use
            document_context: Word document context

        Returns:
            Content Control anchor data or None
        """
        logger.info(
            "creating_content_control_anchor",
            function="create_content_control_anchor",
            occurrence_index=occurrence_index
        )

        if not document_context:
            return None

        try:
            # Generate unique Content Control ID
            control_id = str(uuid.uuid4())

            anchor_data = {
                "type": AnchorType.CONTENT_CONTROL,
                "content_control_id": control_id,
                "finding_text": finding_text,
                "occurrence_index": occurrence_index,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "method": "word_content_control",
                "persistence": "high"
            }

            # In actual implementation, this would:
            # 1. Use Word JavaScript API to insert Content Control around text
            # 2. Store the Content Control ID
            # 3. Tag it with finding metadata

            logger.info("content_control_anchor_created", function="create_content_control_anchor", control_id=control_id)
            return anchor_data

        except Exception as e:
            logger.error("content_control_anchor_failed", function="create_content_control_anchor", error=str(e))
            return None

    async def create_bookmark_anchor(
        self,
        finding_text: str,
        occurrence_index: int,
        document_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create Word bookmark-based anchor for finding.

        Bookmarks in Word are moderately durable but may be affected by:
        - Major document restructuring
        - Some editing operations
        - Co-authoring conflicts

        Args:
            finding_text: Text to anchor to
            occurrence_index: Which occurrence to use
            document_context: Word document context

        Returns:
            Bookmark anchor data or None
        """
        logger.info(
            "creating_bookmark_anchor",
            function="create_bookmark_anchor",
            occurrence_index=occurrence_index
        )

        if not document_context:
            return None

        try:
            # Generate unique bookmark name
            bookmark_name = f"finding_{uuid.uuid4().hex[:8]}"

            anchor_data = {
                "type": AnchorType.BOOKMARK,
                "bookmark_name": bookmark_name,
                "finding_text": finding_text,
                "occurrence_index": occurrence_index,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "method": "word_bookmark",
                "persistence": "medium"
            }

            # In actual implementation, this would:
            # 1. Use Word JavaScript API to create bookmark
            # 2. Store the bookmark name
            # 3. Associate with finding metadata

            logger.info("bookmark_anchor_created", function="create_bookmark_anchor", bookmark=bookmark_name)
            return anchor_data

        except Exception as e:
            logger.error("bookmark_anchor_failed", function="create_bookmark_anchor", error=str(e))
            return None

    async def create_custom_xml_anchor(
        self,
        finding_text: str,
        occurrence_index: int,
        finding_id: str,
        document_context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create Custom XML part-based anchor for finding.

        Custom XML parts in Word provide:
        - Moderate durability across edits
        - Structured metadata storage
        - Integration with document content

        Args:
            finding_text: Text to anchor to
            occurrence_index: Which occurrence to use
            finding_id: Finding ID for metadata
            document_context: Word document context

        Returns:
            Custom XML anchor data or None
        """
        logger.info(
            "creating_custom_xml_anchor",
            function="create_custom_xml_anchor",
            finding_id=finding_id
        )

        if not document_context:
            return None

        try:
            # Generate Custom XML part ID
            xml_part_id = str(uuid.uuid4())

            # Create XML metadata structure
            xml_metadata = f"""<?xml version="1.0" encoding="UTF-8"?>
<finding xmlns="http://klara.ai/findings">
    <id>{finding_id}</id>
    <anchor_text>{finding_text}</anchor_text>
    <occurrence_index>{occurrence_index}</occurrence_index>
    <created_at>{datetime.now(timezone.utc).isoformat()}</created_at>
</finding>"""

            anchor_data = {
                "type": AnchorType.CUSTOM_XML,
                "xml_part_id": xml_part_id,
                "finding_text": finding_text,
                "occurrence_index": occurrence_index,
                "xml_metadata": xml_metadata,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "method": "word_custom_xml",
                "persistence": "medium"
            }

            # In actual implementation, this would:
            # 1. Use Word JavaScript API to create CustomXMLPart
            # 2. Store the metadata XML
            # 3. Associate with finding

            logger.info("custom_xml_anchor_created", function="create_custom_xml_anchor", xml_part_id=xml_part_id)
            return anchor_data

        except Exception as e:
            logger.error("custom_xml_anchor_failed", function="create_custom_xml_anchor", error=str(e))
            return None

    async def create_structural_marker_anchor(
        self,
        finding_text: str,
        occurrence_index: int,
        document_content: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create structural marker-based anchor (heading, section, etc.).

        Structural markers provide context for finding locations:
        - Section numbers
        - Heading hierarchies
        - Page breaks
        - Paragraph numbers

        Args:
            finding_text: Text to anchor to
            occurrence_index: Which occurrence to use
            document_content: Document text content for analysis

        Returns:
            Structural marker anchor data or None
        """
        logger.info(
            "creating_structural_marker_anchor",
            function="create_structural_marker_anchor"
        )

        if not document_content:
            return None

        try:
            # Find the context around the finding text
            context = self._find_text_context(document_content, finding_text, occurrence_index)

            if context:
                anchor_data = {
                    "type": AnchorType.STRUCTURAL_MARKER,
                    "context_before": context.get("before", ""),
                    "context_after": context.get("after", ""),
                    "finding_text": finding_text,
                    "occurrence_index": occurrence_index,
                    "section_number": context.get("section_number"),
                    "heading": context.get("heading"),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "method": "word_structural_marker",
                    "persistence": "low"
                }

                logger.info("structural_marker_anchor_created", function="create_structural_marker_anchor")
                return anchor_data

            return None

        except Exception as e:
            logger.error("structural_marker_anchor_failed", function="create_structural_marker_anchor", error=str(e))
            return None

    async def resolve_content_control(
        self,
        anchor_data: Dict[str, Any],
        editor_context: Optional[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Resolve Content Control anchor to actual document location.

        Args:
            anchor_data: Content Control anchor data
            editor_context: Word API context

        Returns:
            Tuple of (success, location_data, method_used)
        """
        logger.info("resolving_content_control", function="resolve_content_control")

        try:
            if not editor_context:
                return False, None, None

            control_id = anchor_data.get("content_control_id")
            if not control_id:
                return False, None, None

            # In actual implementation with Word JavaScript API:
            # 1. Get Content Control by ID
            # 2. Get its range/position
            # 3. Return location data

            # Simulated resolution:
            location_data = {
                "type": "content_control",
                "control_id": control_id,
                "range_start": 0,  # Would be actual range start
                "range_end": 0,    # Would be actual range end
                "text": anchor_data.get("finding_text", ""),
                "found": True
            }

            logger.info("content_control_resolved", function="resolve_content_control", control_id=control_id)
            return True, location_data, "content_control_resolution"

        except Exception as e:
            logger.error("content_control_resolution_failed", function="resolve_content_control", error=str(e))
            return False, None, None

    async def resolve_bookmark(
        self,
        anchor_data: Dict[str, Any],
        editor_context: Optional[Dict[str, Any]]
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """
        Resolve Bookmark anchor to actual document location.

        Args:
            anchor_data: Bookmark anchor data
            editor_context: Word API context

        Returns:
            Tuple of (success, location_data, method_used)
        """
        logger.info("resolving_bookmark", function="resolve_bookmark")

        try:
            if not editor_context:
                return False, None, None

            bookmark_name = anchor_data.get("bookmark_name")
            if not bookmark_name:
                return False, None, None

            # In actual implementation with Word JavaScript API:
            # 1. Get bookmark by name
            # 2. Get its range/position
            # 3. Return location data

            # Simulated resolution:
            location_data = {
                "type": "bookmark",
                "bookmark_name": bookmark_name,
                "range_start": 0,
                "range_end": 0,
                "text": anchor_data.get("finding_text", ""),
                "found": True
            }

            logger.info("bookmark_resolved", function="resolve_bookmark", bookmark=bookmark_name)
            return True, location_data, "bookmark_resolution"

        except Exception as e:
            logger.error("bookmark_resolution_failed", function="resolve_bookmark", error=str(e))
            return False, None, None

    def _find_text_context(
        self,
        document_content: str,
        finding_text: str,
        occurrence_index: int,
        context_chars: int = 200
    ) -> Optional[Dict[str, Any]]:
        """
        Find surrounding context for text to create structural anchor.

        Args:
            document_content: Full document text
            finding_text: Text to find context for
            occurrence_index: Which occurrence to use
            context_chars: Characters of context to extract

        Returns:
            Context dictionary with before/after text and structural info
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

            # Try to identify structural markers
            heading = self._extract_heading(context_before)
            section_number = self._extract_section_number(context_before)

            return {
                "before": context_before,
                "after": context_after,
                "heading": heading,
                "section_number": section_number,
                "position": position
            }

        except Exception as e:
            logger.error("find_text_context_failed", function="_find_text_context", error=str(e))
            return None

    def _extract_heading(self, text: str) -> Optional[str]:
        """Extract heading from text (looking for heading patterns)."""
        lines = text.split('\n')
        for line in reversed(lines[-5:]):  # Check last 5 lines
            line = line.strip()
            if line and (line.startswith('#') or line.startswith('Heading')):
                return line
        return None

    def _extract_section_number(self, text: str) -> Optional[str]:
        """Extract section number from text."""
        import re
        # Look for patterns like "Section 1", "1.", etc.
        patterns = [
            r'section\s+(\d+)',
            r'chapter\s+(\d+)',
            r'^(\d+)\.',
            r'^(\d+)\s+[A-Z]'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                return match.group(1)
        return None


class WordCoAuthoringAnchor:
    """
    Specialized anchor handling for Word co-authoring scenarios.

    In co-authoring environments, additional considerations:
    - Other users may edit the document
    - Conflicts may occur in anchor regions
    - Merge operations may affect anchor stability
    """

    async def handle_coauthoring_conflict(
        self,
        anchor_data: Dict[str, Any],
        conflict_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle anchor resolution during co-authoring conflicts.

        Args:
            anchor_data: Existing anchor data
            conflict_info: Information about the conflict

        Returns:
            Updated anchor data with conflict resolution
        """
        logger.info("handling_coauthoring_conflict", function="handle_coauthoring_conflict")

        # Strategy: Try to migrate to more durable anchor type
        if anchor_data.get("primary_anchor") and anchor_data["primary_anchor"]["type"] != "content_control":
            # Try to upgrade to Content Control
            logger.info("migrating_to_content_control", function="handle_coauthoring_conflict")
            # Implementation would create Content Control anchor

        return anchor_data

    async def validate_anchor_after_merge(
        self,
        anchor_data: Dict[str, Any],
        merge_info: Dict[str, Any]
    ) -> bool:
        """
        Validate if anchor is still valid after document merge.

        Args:
            anchor_data: Anchor data to validate
            merge_info: Information about the merge operation

        Returns:
            True if anchor is still valid
        """
        logger.info("validating_anchor_after_merge", function="validate_anchor_after_merge")

        # Check if anchor was in merged region
        merge_region = merge_info.get("affected_ranges", [])

        for range_data in merge_region:
            if self._is_anchor_in_range(anchor_data, range_data):
                logger.warning("anchor_in_merge_region", function="validating_anchor_after_merge")
                return False

        return True

    def _is_anchor_in_range(self, anchor_data: Dict[str, Any], range_data: Dict[str, Any]) -> bool:
        """Check if anchor is within affected range."""
        # Implementation would compare anchor position with range
        return False


# Global instances
word_anchor_strategy = WordAnchorStrategy()
word_coauthoring_anchor = WordCoAuthoringAnchor()