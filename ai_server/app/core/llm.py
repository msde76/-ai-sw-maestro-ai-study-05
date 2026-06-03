import json
import re
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.core.config import Settings


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def _ensure_json_object(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object")
    return payload


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        return _ensure_json_object(json.loads(text))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON object: {exc.msg}") from exc


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Expected JSON object")

    fenced_match = _FENCED_JSON_RE.search(stripped)
    if fenced_match:
        return _parse_json_object(fenced_match.group(1).strip())

    try:
        return _parse_json_object(stripped)
    except ValueError as exc:
        parse_error = exc

    decoder = json.JSONDecoder()
    for start in (index for index, char in enumerate(stripped) if char == "{"):
        try:
            payload, _ = decoder.raw_decode(stripped, start)
        except json.JSONDecodeError as exc:
            parse_error = ValueError(f"Invalid JSON object: {exc.msg}")
            continue
        return _ensure_json_object(payload)

    raise parse_error


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
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise ValueError("Missing response content")
        return extract_json_object(content)
