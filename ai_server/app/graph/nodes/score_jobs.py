import json
from pathlib import Path
from typing import Protocol

from app.graph.state import GraphState


class JsonLLM(Protocol):
    async def complete_json(self, messages: list[dict[str, str]], *, json_schema: dict | None = None) -> dict:
        ...


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "suitability_scoring.md"
JOB_LIST_KEYS = ("jobs", "recommendations", "results", "items", "scoredJobs", "topMatches")
SCORING_RESPONSE_SCHEMA = {
    "name": "job_scoring_response",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "jobs": {
                "type": "array",
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "jobId": {"type": "string"},
                        "companyName": {"type": "string"},
                        "jobTitle": {"type": "string"},
                        "suitabilityScore": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                        },
                        "compensation": {"type": "string"},
                        "deadline": {"type": "string"},
                        "originalLink": {"type": "string"},
                        "analysis": {
                            "type": "object",
                            "properties": {
                                "matchReason": {"type": "string"},
                                "missingPoints": {"type": "string"},
                                "checkpointGuide": {"type": "string"},
                            },
                            "required": ["matchReason", "missingPoints", "checkpointGuide"],
                            "additionalProperties": False,
                        },
                    },
                    "required": [
                        "jobId",
                        "companyName",
                        "jobTitle",
                        "suitabilityScore",
                        "compensation",
                        "deadline",
                        "originalLink",
                        "analysis",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["jobs"],
        "additionalProperties": False,
    },
}


def _validate_scoring_response(response: dict) -> list[dict]:
    if not isinstance(response, dict):
        raise ValueError("LLM scoring response must include a jobs list")
    if "jobId" in response:
        return [response]

    jobs = _job_list_from_response(response)
    if not isinstance(jobs, list):
        raise ValueError("LLM scoring response must include a jobs list")
    valid_jobs = [job for job in jobs if isinstance(job, dict)]
    if not valid_jobs:
        raise ValueError("LLM scoring response jobs must be objects")
    return valid_jobs


def _job_list_from_response(response: dict) -> list | None:
    for key in JOB_LIST_KEYS:
        value = response.get(key)
        if isinstance(value, list):
            return value

    list_values = [value for value in response.values() if isinstance(value, list)]
    if len(list_values) == 1:
        return list_values[0]
    return None


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
                    "적합도가 낮아도 5개 미만이면 남은 후보 중 가장 나은 공고를 낮은 점수 그대로 포함하세요. "
                    "반드시 JSON 객체의 jobs 배열로 반환하세요.\n"
                    f"Score these jobs:\n{json.dumps(payload, ensure_ascii=False)}"
                ),
            },
        ],
        json_schema=SCORING_RESPONSE_SCHEMA,
    )
    return {"scored_jobs": _validate_scoring_response(response)}
