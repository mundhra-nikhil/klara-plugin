"""File validation & sanitization utilities."""

import os
import re
from src.core.constants import MAX_UPLOAD_SIZE_BYTES, ALLOWED_MIME_TYPES


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename to prevent path traversal and injection."""
    # Remove any directory components
    filename = os.path.basename(filename)
    # Replace any non-alphanumeric characters except dots, hyphens, underscores
    filename = re.sub(r'[^\w\-.]', '_', filename)
    return filename


def validate_file_size(size_bytes: int) -> bool:
    """Check if file size is within allowed limits."""
    return size_bytes <= MAX_UPLOAD_SIZE_BYTES


def validate_mime_type(mime_type: str) -> bool:
    """Check if MIME type is in the allowed list."""
    return mime_type in ALLOWED_MIME_TYPES
