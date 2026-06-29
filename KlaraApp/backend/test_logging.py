"""Test script to verify the new logging format."""

import structlog
from src.core.logger import setup_logging, get_logger_with_context

# Setup logging
setup_logging()

# Create logger instance
logger = get_logger_with_context()


def test_function():
    """Test function to demonstrate logging."""
    # Bind some context
    structlog.contextvars.bind_contextvars(
        request_id="test-req-123",
        org_name="example.com"
    )
    
    logger.info("This is a test info message")
    logger.warning("This is a test warning message", extra_field="some_value")
    logger.error("This is a test error message", error_code=500)
    
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("Division by zero error occurred")


def another_function():
    """Another test function."""
    logger.info("Message from another function", user_id="user-456")


if __name__ == "__main__":
    print("Testing new logging format...")
    print("-" * 100)
    test_function()
    another_function()
    print("-" * 100)
    print("Test completed. Check log output above.")
