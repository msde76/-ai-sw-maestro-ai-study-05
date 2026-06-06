import math

from app.api.schemas import Analysis, JobData
from app.graph.state import GraphState


DEFAULT_TEXT = "원문 확인 필요"
DEFAULT_MATCH_REASON = "추천 이유가 충분히 생성되지 않았습니다."
DEFAULT_MISSING_POINTS = "보완점 정보가 충분히 생성되지 않았습니다."
DEFAULT_CHECKPOINT_GUIDE = "지원 전 원문 공고를 확인하세요."


def _score(raw: dict) -> float:
    try:
        score = float(raw.get("suitabilityScore") or 0.0)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(score):
        return 0.0
    return max(0.0, min(score, 1.0))


def _original_link(raw: dict) -> str | None:
    value = raw.get("originalLink")
    return value if isinstance(value, str) else None


def select_response_jobs(raw_jobs: list[dict]) -> list[dict]:
    valid_items = [item for item in raw_jobs if isinstance(item, dict)]
    strong_matches = [item for item in valid_items if _score(item) >= 0.7]
    backfill_matches = [item for item in valid_items if 0.0 < _score(item) < 0.7]
    strong_matches.sort(key=_score, reverse=True)
    backfill_matches.sort(key=_score, reverse=True)
    return [*strong_matches, *backfill_matches][:5]


def _to_job_data(raw: dict) -> JobData:
    analysis = raw.get("analysis") if isinstance(raw.get("analysis"), dict) else {}
    original_link = _original_link(raw)
    return JobData(
        jobId=str(raw.get("jobId") or raw.get("id") or original_link or "unknown"),
        companyName=str(raw.get("companyName") or DEFAULT_TEXT),
        jobTitle=str(raw.get("jobTitle") or DEFAULT_TEXT),
        jobIntroduction=str(raw.get("jobIntroduction") or raw.get("sourceSnapshot") or DEFAULT_TEXT),
        suitabilityScore=_score(raw),
        compensation=str(raw.get("compensation") or DEFAULT_TEXT),
        deadline=str(raw.get("deadline") or DEFAULT_TEXT),
        originalLink=original_link,
        analysis=Analysis(
            matchReason=str(analysis.get("matchReason") or DEFAULT_MATCH_REASON),
            missingPoints=str(analysis.get("missingPoints") or DEFAULT_MISSING_POINTS),
            checkpointGuide=str(analysis.get("checkpointGuide") or DEFAULT_CHECKPOINT_GUIDE),
        ),
    )


def format_response(state: GraphState) -> GraphState:
    raw_jobs = state.get("enriched_jobs") or state.get("scored_jobs", [])
    selected = select_response_jobs(raw_jobs)
    return {"response_jobs": [_to_job_data(item) for item in selected]}
