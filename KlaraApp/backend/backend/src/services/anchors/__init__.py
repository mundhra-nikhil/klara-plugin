"""Anchor management services for durable finding references.

This package provides multi-tier anchoring strategies that work across
different document editors (OnlyOffice, Word Online) and maintain
stability across document edits, co-authoring, and revision cycles.
"""

from src.core.logger import get_logger_with_context

logger = get_logger_with_context()