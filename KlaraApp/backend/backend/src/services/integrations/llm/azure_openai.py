"""Azure OpenAI client with Langfuse tracing."""

from openai import AsyncAzureOpenAI
from src.configs.config import settings

_client = None


def get_openai_client() -> AsyncAzureOpenAI:
    global _client
    if _client is None:
        _client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            # Keep this aggressive so when the endpoint is unreachable we fail
            # fast and the deterministic rule engine takes over within seconds.
            timeout=20.0,
            max_retries=0,
        )
    return _client


async def run_ai_analysis(prompt: str, system_prompt: str) -> dict:
    """Run an AI analysis using Azure OpenAI and return structured results."""
    import json
    
    is_mock = (
        not settings.azure_openai_api_key
        or "your-api-key" in settings.azure_openai_api_key.lower()
        or not settings.azure_openai_endpoint
        or "your-instance" in settings.azure_openai_endpoint.lower()
    )

    if is_mock:
        # No real LLM configured. Do NOT fabricate findings here — returning
        # canned, document-agnostic findings (with no rule_id/anchor_text/
        # paragraph) used to clobber the accurate deterministic rule engine and
        # broke navigation/highlighting. Return an empty findings set so the
        # caller falls back to the deterministic synthesis from the real .docx.
        return {
            "content": json.dumps({"findings": []}),
            "model": "no-llm-configured",
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }

    client = get_openai_client()
    response = await client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    usage = response.usage
    return {
        "content": response.choices[0].message.content,
        "model": response.model,
        "prompt_tokens": usage.prompt_tokens if usage else 0,
        "completion_tokens": usage.completion_tokens if usage else 0,
    }
