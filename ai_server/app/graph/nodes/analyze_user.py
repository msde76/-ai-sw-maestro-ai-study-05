import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator

from app.graph.state import GraphState


class JsonLLM(Protocol):
    async def complete_json(self, messages: list[dict[str, str]]) -> dict:
        ...


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "user_analysis.md"


class UserProfile(BaseModel):
    model_config = ConfigDict(strict=True)

    projectExperiences: list[str]
    technicalSkills: list[str]
    roleSignals: list[str]
    strengths: list[str]
    jobDirection: str
    missingInformation: list[str]
    isSufficient: StrictBool

    @field_validator(
        "projectExperiences",
        "technicalSkills",
        "roleSignals",
        "strengths",
        "missingInformation",
        mode="before",
    )
    @classmethod
    def normalize_text_items(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("Expected a list")
        normalized = [_text_item(item) for item in value]
        return [item for item in normalized if item]


def _text_item(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        parts = [str(value).strip() for value in item.values() if value not in (None, "")]
        return " / ".join(part for part in parts if part)
    raise ValueError("Expected a string or object item")


async def analyze_user(state: GraphState, llm: JsonLLM) -> GraphState:
    request = state["request"]
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "coverLetter": request.coverLetter,
        "preferences": request.preferences.model_dump(),
    }

    profile = await llm.complete_json(
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Analyze this JSON input:\n{json.dumps(payload, ensure_ascii=False)}",
            },
        ]
    )
    validated_profile = UserProfile.model_validate(profile)

    return {"user_profile": validated_profile.model_dump()}
