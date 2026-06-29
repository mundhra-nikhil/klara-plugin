"""LLM token & cost tracking utilities."""

from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


def log_llm_usage(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    job_id: str = "",
):
    """Log LLM token usage for cost tracking."""
    total_tokens = prompt_tokens + completion_tokens
    logger.info(
        "llm_usage",
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        job_id=job_id,
    )
