import json
from pathlib import Path
from typing import Protocol

from app.graph.state import GraphState


class JsonLLM(Protocol):
    async def complete_json(self, messages: list[dict[str, str]]) -> dict:
        ...


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "suitability_scoring.md"


async def score_jobs(state: GraphState, llm: JsonLLM) -> GraphState:
    candidate_jobs = state.get("candidate_jobs", [])
    if not candidate_jobs:
        return {"scored_jobs": []}

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "userProfile": state.get("user_profile", {}),
        "candidateJobs": candidate_jobs,
    }
    response = await llm.complete_json(
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Score these jobs:\n{json.dumps(payload, ensure_ascii=False)}",
            },
        ]
    )
    jobs = response.get("jobs", [])
    return {"scored_jobs": jobs if isinstance(jobs, list) else []}
