from typing import Any, TypedDict

from app.api.schemas import AnalyzeRequest, JobData


class GraphState(TypedDict, total=False):
    request: AnalyzeRequest
    user_profile: dict[str, Any]
    search_query: dict[str, Any]
    candidate_jobs: list[dict[str, Any]]
    scored_jobs: list[dict[str, Any]]
    enriched_jobs: list[dict[str, Any]]
    response_jobs: list[JobData]
