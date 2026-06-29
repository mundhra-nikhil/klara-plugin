"""Microsoft Teams channel notification service."""

from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


async def send_teams_notification(channel_id: str, message: str):
    """Send notification to a Microsoft Teams channel."""
    logger.info("teams_notification_sent", channel_id=channel_id)
    # MS Teams webhook implementation placeholder
