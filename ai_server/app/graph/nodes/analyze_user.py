import json
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, StrictBool

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
