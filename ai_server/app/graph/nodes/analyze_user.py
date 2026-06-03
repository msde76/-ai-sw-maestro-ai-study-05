from pathlib import Path
from typing import Protocol

from app.graph.state import GraphState


class JsonLLM(Protocol):
    async def complete_json(self, messages: list[dict[str, str]]) -> dict:
        ...


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "user_analysis.md"


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
            {"role": "user", "content": str(payload)},
        ]
    )

    return {"user_profile": profile}
