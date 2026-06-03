import json
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.core.config import Settings


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object")
    return payload


class UpstageLLM:
    def __init__(self, settings: Settings):
        self._model = settings.upstage_model
        self._client = AsyncOpenAI(
            api_key=settings.upstage_api_key,
            base_url=str(settings.upstage_base_url),
        )

    async def complete_json(self, messages: Sequence[dict[str, str]]) -> dict[str, Any]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=list(messages),
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        return extract_json_object(content)
