import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.graph.state import GraphState


class JsonLLM(Protocol):
    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any] | None = None,
    ) -> dict:
        ...


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "user_analysis.md"
USER_PROFILE_JSON_SCHEMA = {
    "name": "user_profile_augmentation",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "isSufficient": {
                "type": "boolean",
                "description": "재생성을 거쳐 검색 가능한 수준이 되었으면 true, 도저히 불가능하면 false",
            },
            "internal_qa_process": {
                "type": "array",
                "items": {"type": "string"},
                "description": "부족하다고 판단 시 생성한 내부 가상 질문과 추론된 답변 요약",
            },
            "augmented_profile": {
                "type": "string",
                "description": "정제 및 재생성된 상세 프로필 텍스트",
            },
            "extracted_keywords": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 0,
                "maxItems": 3,
                "description": "검색에 활용할 핵심 기술 키워드 2~3개",
            },
        },
        "required": [
            "isSufficient",
            "internal_qa_process",
            "augmented_profile",
            "extracted_keywords",
        ],
    },
    "strict": True,
}


class UserProfile(BaseModel):
    model_config = ConfigDict(strict=True)

    isSufficient: StrictBool = True
    internal_qa_process: list[str] = Field(default_factory=list)
    augmented_profile: str = ""
    extracted_keywords: list[str] = Field(default_factory=list)

    @field_validator(
        "internal_qa_process",
        "extracted_keywords",
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
        ],
        json_schema=USER_PROFILE_JSON_SCHEMA,
    )
    validated_profile = UserProfile.model_validate(profile)
    user_profile = validated_profile.model_dump()
    user_profile["technicalSkills"] = user_profile["extracted_keywords"]

    return {"user_profile": user_profile}
