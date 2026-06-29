"""Vision analysis via the Azure OpenAI gpt-4o deployment.

Used to evaluate the rendered-layout POC rules that a text model / XML parse
cannot verify (margins, line numbers, page numbering, widows/orphans, footnote
flow). Shares the same Azure resource/key as the text engine — only the
deployment (model) differs (`azure_openai_vision_deployment`, default gpt-4o).
"""

import base64

from src.configs.config import settings
from src.services.integrations.llm.azure_openai import get_openai_client
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


def _is_mock() -> bool:
    return (
        not settings.azure_openai_api_key
        or "your-api-key" in settings.azure_openai_api_key.lower()
        or not settings.azure_openai_endpoint
        or "your-instance" in settings.azure_openai_endpoint.lower()
    )


def _image_part(png_bytes: bytes) -> dict:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return {
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
    }


async def run_vision_analysis(
    images: list[bytes], system_prompt: str, user_prompt: str
) -> dict:
    """Send rendered page images + prompts to the gpt-4o vision deployment and
    return structured JSON results. Raises on transport errors so the caller can
    fall back to static warnings."""
    if _is_mock() or not images:
        return {"content": "", "model": "vision-skipped", "prompt_tokens": 0, "completion_tokens": 0}

    client = get_openai_client()
    content: list[dict] = [{"type": "text", "text": user_prompt}]
    content.extend(_image_part(b) for b in images)

    # Vision requests carry several high-detail images — give them more headroom
    # than the shared client's fast-fail text timeout.
    response = await client.with_options(timeout=90.0).chat.completions.create(
        model=settings.azure_openai_vision_deployment,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
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
