import json
from pathlib import Path
from typing import Protocol

from app.graph.state import GraphState


class JsonLLM(Protocol):
    async def complete_json(self, messages: list[dict[str, str]]) -> dict:
        ...


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "suitability_scoring.md"


def _validate_scoring_response(response: dict) -> list[dict]:
    jobs = response.get("jobs") if isinstance(response, dict) else None
    if jobs is None and isinstance(response, dict) and "jobId" in response:
        return [response]
    if not isinstance(jobs, list):
        raise ValueError("LLM scoring response must include a jobs list")
    if not all(isinstance(job, dict) for job in jobs):
        raise ValueError("LLM scoring response jobs must be objects")
    return jobs


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
                "content": (
                    "candidateJobs의 모든 공고를 평가한 뒤 suitabilityScore 내림차순으로 최대 5개를 반환하세요. "
                    "적합도가 낮아도 5개 미만이면 남은 후보 중 가장 나은 공고를 낮은 점수 그대로 포함하세요.\n"
                    f"Score these jobs:\n{json.dumps(payload, ensure_ascii=False)}"
                ),
            },
        ]
    )
    return {"scored_jobs": _validate_scoring_response(response)}
