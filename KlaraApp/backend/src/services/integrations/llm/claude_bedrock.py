"""Claude (via AWS Bedrock) client for the QC analysis engine.

This is the primary engine: it reads the real uploaded document's structured
paragraph metadata + pre-computed rule violations and asks Claude to emit
rule-anchored findings (rule_id, paragraph, anchor_text, original/replacement
text) so the frontend can navigate to and highlight each error in the document.

The large 18-rule system prompt is stable across every request, so it is sent
as a cached block (prompt caching) — repeat analyses pay ~0.1x for that prefix.
"""

from src.configs.config import settings
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()

_client = None


def claude_configured() -> bool:
    """True when AWS credentials for Bedrock are present."""
    return bool(settings.aws_access_key_id and settings.aws_secret_access_key)


def _get_client():
    global _client
    if _client is None:
        # Imported lazily so the backend still boots if the package is absent.
        from anthropic import AsyncAnthropicBedrock

        kwargs = {
            "aws_access_key": settings.aws_access_key_id or None,
            "aws_secret_key": settings.aws_secret_access_key or None,
            "aws_region": settings.aws_region or "us-east-1",
            # Fail fast so the deterministic rule engine can take over quickly
            # if Bedrock is unreachable.
            "timeout": 60.0,
            "max_retries": 1,
        }
        if settings.aws_session_token:
            kwargs["aws_session_token"] = settings.aws_session_token
        _client = AsyncAnthropicBedrock(**kwargs)
    return _client


async def run_claude_analysis(user_prompt: str, system_prompt: str) -> dict:
    """Run the QC analysis with Claude on Bedrock.

    Returns the same shape the rest of the pipeline expects from the Azure path:
    {"content": <raw JSON string>, "model", "prompt_tokens", "completion_tokens"}.
    """
    client = _get_client()
    model = settings.anthropic_model or "global.anthropic.claude-sonnet-4-6"

    response = await client.messages.create(
        model=model,
        max_tokens=8000,
        # Cache the frozen 18-rule checklist prompt; only the per-document user
        # turn below the breakpoint varies between requests.
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": (
                    user_prompt
                    + "\n\nReturn ONLY the strict-JSON object described above. "
                    "No prose, no explanation, no markdown code fences."
                ),
            }
        ],
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    usage = response.usage
    logger.info(
        "Claude analysis complete",
        function="run_claude_analysis",
        model=model,
        cache_read=getattr(usage, "cache_read_input_tokens", 0),
        input_tokens=getattr(usage, "input_tokens", 0),
        output_tokens=getattr(usage, "output_tokens", 0),
    )
    return {
        "content": text,
        "model": getattr(response, "model", model),
        "prompt_tokens": getattr(usage, "input_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "output_tokens", 0) or 0,
    }
