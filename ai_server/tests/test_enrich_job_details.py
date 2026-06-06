import pytest

from app.graph.nodes.enrich_job_details import (
    DEFAULT_JOB_INTRODUCTION,
    enrich_job_details,
    extract_job_introduction,
)


def test_extract_job_introduction_prefers_detail_section():
    detail_text = """[요약]
짧은 요약
[상세 내용]
상세 소개입니다.
추가 설명입니다.
\n원본:
원문 링크"""

    assert extract_job_introduction(detail_text) == "상세 소개입니다.\n추가 설명입니다."


def test_extract_job_introduction_falls_back_to_summary_section():
    detail_text = """[기타]
무관한 내용
[요약]
요약 소개입니다.
원본:
원문 링크"""

    assert extract_job_introduction(detail_text) == "요약 소개입니다."


def test_extract_job_introduction_returns_empty_string_for_unknown_text():
    assert extract_job_introduction("설명 없음") == ""


class FakeDetailClient:
    def __init__(self, details_by_job_id: dict[str, str | Exception]):
        self.details_by_job_id = details_by_job_id
        self.calls: list[tuple[str, bool]] = []

    async def get_job_detail(self, job_id: str | int, include_full_description: bool = True) -> str:
        self.calls.append((str(job_id), include_full_description))
        result = self.details_by_job_id[str(job_id)]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.asyncio
async def test_enrich_job_details_fetches_only_final_top_five_jobs_in_selected_order():
    state = {
        "scored_jobs": [
            {"jobId": "1", "suitabilityScore": 0.95, "sourceSnapshot": "s1"},
            {"jobId": "2", "suitabilityScore": 0.91, "sourceSnapshot": "s2"},
            {"jobId": "3", "suitabilityScore": 0.68, "sourceSnapshot": "s3"},
            {"jobId": "4", "suitabilityScore": 0.8, "sourceSnapshot": "s4"},
            {"jobId": "5", "suitabilityScore": 0.4, "sourceSnapshot": "s5"},
            {"jobId": "6", "suitabilityScore": 0.69, "sourceSnapshot": "s6"},
        ]
    }
    client = FakeDetailClient(
        {
            "1": "[상세 내용]\n소개 1",
            "2": "[상세 내용]\n소개 2",
            "4": "[상세 내용]\n소개 4",
            "6": "[상세 내용]\n소개 6",
            "3": "[상세 내용]\n소개 3",
        }
    )

    result = await enrich_job_details(state, client)

    assert [job["jobId"] for job in result["enriched_jobs"]] == ["1", "2", "4", "6", "3"]
    assert client.calls == [
        ("1", True),
        ("2", True),
        ("4", True),
        ("6", True),
        ("3", True),
    ]
    assert [job["jobIntroduction"] for job in result["enriched_jobs"]] == [
        "소개 1",
        "소개 2",
        "소개 4",
        "소개 6",
        "소개 3",
    ]


@pytest.mark.asyncio
async def test_enrich_job_details_falls_back_to_source_snapshot_when_detail_fails():
    state = {
        "scored_jobs": [
            {"jobId": "1", "suitabilityScore": 0.95, "sourceSnapshot": "스냅샷 소개"},
        ]
    }
    client = FakeDetailClient({"1": RuntimeError("detail failed")})

    result = await enrich_job_details(state, client)

    assert result["enriched_jobs"][0]["jobIntroduction"] == "스냅샷 소개"


@pytest.mark.asyncio
async def test_enrich_job_details_falls_back_to_default_without_snapshot():
    state = {
        "scored_jobs": [
            {"jobId": "1", "suitabilityScore": 0.95},
        ]
    }
    client = FakeDetailClient({"1": RuntimeError("detail failed")})

    result = await enrich_job_details(state, client)

    assert result["enriched_jobs"][0]["jobIntroduction"] == DEFAULT_JOB_INTRODUCTION
