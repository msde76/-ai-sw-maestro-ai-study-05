import logging
import re
from typing import Any, Protocol

from app.graph.nodes.format_response import select_response_jobs
from app.graph.state import GraphState


DEFAULT_JOB_INTRODUCTION = "원문 확인 필요"
logger = logging.getLogger(__name__)


class JobDetailClient(Protocol):
    async def get_job_detail(self, job_id: str | int, include_full_description: bool = True) -> str:
        ...


def extract_job_introduction(detail_text: str) -> str:
    if not detail_text:
        return ""

    detail = _extract_section(detail_text, "상세 내용")
    if detail:
        return detail
    return _extract_section(detail_text, "요약")


def _extract_section(text: str, title: str) -> str:
    section_match = re.search(rf"\[{re.escape(title)}\]", text)
    if not section_match:
        return ""

    start = section_match.end()
    remainder = text[start:]
    stop_positions = []

    original_match = re.search(r"\n원본:", remainder)
    if original_match:
        stop_positions.append(original_match.start())

    next_section_match = re.search(r"\n\[[^\]\n]+\]", remainder)
    if next_section_match:
        stop_positions.append(next_section_match.start())

    end = min(stop_positions) if stop_positions else len(remainder)
    return remainder[:end].strip()


async def enrich_job_details(state: GraphState, client: JobDetailClient) -> GraphState:
    selected_jobs = select_response_jobs(state.get("scored_jobs", []))
    enriched_jobs: list[dict[str, Any]] = []

    for job in selected_jobs:
        enriched_job = dict(job)
        introduction = ""

        try:
            detail_text = await client.get_job_detail(job["jobId"], include_full_description=True)
            introduction = extract_job_introduction(detail_text)
        except Exception as exc:
            logger.warning(
                "Failed to enrich Pathsdog job detail for jobId=%s",
                job.get("jobId"),
                exc_info=True,
            )
            introduction = ""

        if not introduction:
            introduction = str(job.get("sourceSnapshot") or DEFAULT_JOB_INTRODUCTION)

        enriched_job["jobIntroduction"] = introduction
        enriched_jobs.append(enriched_job)

    return {"enriched_jobs": enriched_jobs}
