import pytest

from app.graph.nodes.format_response import format_response, select_response_jobs
from app.graph.nodes.score_jobs import score_jobs


class FakeScoringLLM:
    def __init__(self, response=None):
        self.response = response
        self.calls = 0
        self.messages = None
        self.json_schema = None

    async def complete_json(self, messages, *, json_schema=None):
        self.calls += 1
        self.messages = messages
        self.json_schema = json_schema
        return self.response or {
            "jobs": [
                {
                    "jobId": "1",
                    "companyName": "A",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 0.9,
                    "compensation": "원문 확인 필요",
                    "deadline": "원문 확인 필요",
                    "originalLink": "https://example.com/1",
                    "analysis": {
                        "matchReason": "Spring API 경험이 주요 업무와 관련성이 높습니다.",
                        "missingPoints": "대규모 운영 경험은 보완이 필요합니다.",
                        "checkpointGuide": "Redis 캐시 성능 개선 경험을 강조하세요.",
                    },
                },
                {
                    "jobId": "2",
                    "companyName": "B",
                    "jobTitle": "프론트엔드 개발자",
                    "suitabilityScore": 0.4,
                    "compensation": "원문 확인 필요",
                    "deadline": "원문 확인 필요",
                    "originalLink": "https://example.com/2",
                    "analysis": {
                        "matchReason": "일부 웹 경험만 관련됩니다.",
                        "missingPoints": "React 경험이 부족합니다.",
                        "checkpointGuide": "프론트엔드 경험을 보완하세요.",
                    },
                },
            ]
        }


@pytest.mark.asyncio
async def test_score_jobs_stores_scored_jobs():
    state = {
        "user_profile": {"technicalSkills": ["Spring", "Redis"]},
        "candidate_jobs": [{"jobId": "1", "jobTitle": "백엔드 개발자"}],
    }

    result = await score_jobs(state, FakeScoringLLM())

    assert len(result["scored_jobs"]) == 2
    assert result["scored_jobs"][0]["suitabilityScore"] == 0.9


@pytest.mark.asyncio
async def test_score_jobs_prompt_requests_all_candidates_and_top_five():
    llm = FakeScoringLLM()
    candidate_jobs = [{"jobId": str(i), "jobTitle": f"공고{i}"} for i in range(1, 8)]

    await score_jobs({"user_profile": {}, "candidate_jobs": candidate_jobs}, llm)

    user_message = llm.messages[1]["content"]
    assert "candidateJobs의 모든 공고를 평가" in user_message
    assert "최대 5개" in user_message
    assert "적합도가 낮아도" in user_message
    assert "jobs 배열" in user_message


@pytest.mark.asyncio
async def test_score_jobs_requests_structured_output_schema():
    llm = FakeScoringLLM()

    await score_jobs({"user_profile": {}, "candidate_jobs": [{"jobId": "1"}]}, llm)

    assert llm.json_schema["name"] == "job_scoring_response"
    assert llm.json_schema["strict"] is True
    schema = llm.json_schema["schema"]
    assert schema["required"] == ["jobs"]
    assert schema["properties"]["jobs"]["maxItems"] == 5
    job_schema = schema["properties"]["jobs"]["items"]
    assert "jobId" in job_schema["required"]
    assert "suitabilityScore" in job_schema["required"]


@pytest.mark.asyncio
async def test_score_jobs_returns_empty_without_llm_call_when_candidate_jobs_empty():
    llm = FakeScoringLLM()

    result = await score_jobs({"candidate_jobs": []}, llm)

    assert result == {"scored_jobs": []}
    assert llm.calls == 0


@pytest.mark.asyncio
async def test_score_jobs_accepts_single_top_level_job_payload():
    llm = FakeScoringLLM(
        response={
            "jobId": "1",
            "companyName": "A",
            "jobTitle": "LLM 모델 데이터 관리",
            "suitabilityScore": 0.85,
            "analysis": {},
        }
    )

    result = await score_jobs({"candidate_jobs": [{"jobId": "1"}]}, llm)

    assert len(result["scored_jobs"]) == 1
    assert result["scored_jobs"][0]["jobId"] == "1"


@pytest.mark.asyncio
async def test_score_jobs_accepts_common_list_payload_aliases():
    llm = FakeScoringLLM(
        response={
            "recommendations": [
                {
                    "jobId": "1",
                    "companyName": "A",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 0.85,
                    "analysis": {},
                }
            ]
        }
    )

    result = await score_jobs({"candidate_jobs": [{"jobId": "1"}]}, llm)

    assert len(result["scored_jobs"]) == 1
    assert result["scored_jobs"][0]["jobId"] == "1"


@pytest.mark.asyncio
async def test_score_jobs_accepts_single_list_value_payload():
    llm = FakeScoringLLM(
        response={
            "topMatches": [
                {
                    "jobId": "1",
                    "companyName": "A",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 0.85,
                    "analysis": {},
                }
            ]
        }
    )

    result = await score_jobs({"candidate_jobs": [{"jobId": "1"}]}, llm)

    assert len(result["scored_jobs"]) == 1
    assert result["scored_jobs"][0]["jobId"] == "1"


@pytest.mark.asyncio
async def test_score_jobs_raises_value_error_for_non_list_jobs_payload():
    llm = FakeScoringLLM(response={"jobs": {"jobId": "1"}})

    with pytest.raises(ValueError, match="jobs"):
        await score_jobs({"candidate_jobs": [{"jobId": "1"}]}, llm)


@pytest.mark.asyncio
async def test_score_jobs_ignores_non_object_items_when_valid_jobs_exist():
    llm = FakeScoringLLM(response={"jobs": [{"jobId": "1"}, "bad-job"]})

    result = await score_jobs({"candidate_jobs": [{"jobId": "1"}]}, llm)

    assert len(result["scored_jobs"]) == 1
    assert result["scored_jobs"][0]["jobId"] == "1"


@pytest.mark.asyncio
async def test_score_jobs_raises_value_error_when_no_valid_job_objects_exist():
    llm = FakeScoringLLM(response={"jobs": ["bad-job"]})

    with pytest.raises(ValueError, match="jobs"):
        await score_jobs({"candidate_jobs": [{"jobId": "1"}]}, llm)


def test_format_response_prioritizes_threshold_and_backfills_to_five():
    state = {
        "scored_jobs": [
            {
                "jobId": str(i),
                "companyName": f"회사{i}",
                "jobTitle": "백엔드 개발자",
                "suitabilityScore": score,
                "compensation": "",
                "deadline": "",
                "originalLink": None,
                "analysis": {
                    "matchReason": "관련성이 높습니다.",
                    "missingPoints": "보완점입니다.",
                    "checkpointGuide": "강조 포인트입니다.",
                },
            }
            for i, score in enumerate([0.95, 0.91, 0.68, 0.8, 0.4, 0.69], start=1)
        ]
    }

    result = format_response(state)

    jobs = result["response_jobs"]
    assert len(jobs) == 5
    assert [job.suitabilityScore for job in jobs] == [0.95, 0.91, 0.8, 0.69, 0.68]
    assert jobs[0].compensation == "원문 확인 필요"


def test_select_response_jobs_prioritizes_threshold_and_backfills_to_five():
    raw_jobs = [
        {"jobId": "1", "suitabilityScore": 0.95},
        {"jobId": "2", "suitabilityScore": 0.0},
        {"jobId": "3", "suitabilityScore": 0.68},
        {"jobId": "4", "suitabilityScore": 0.91},
        {"jobId": "5", "suitabilityScore": 0.8},
        {"jobId": "6", "suitabilityScore": 0.69},
        "ignore-me",
        {"jobId": "7", "suitabilityScore": 0.4},
    ]

    selected = select_response_jobs(raw_jobs)

    assert [job["jobId"] for job in selected] == ["1", "4", "5", "6", "3"]


def test_format_response_clamps_out_of_range_score_before_formatting():
    result = format_response(
        {
            "scored_jobs": [
                {
                    "jobId": "1",
                    "companyName": "A",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 1.2,
                    "originalLink": "https://example.com/1",
                    "analysis": {},
                }
            ]
        }
    )

    assert len(result["response_jobs"]) == 1
    assert result["response_jobs"][0].suitabilityScore == 1.0


def test_format_response_treats_non_finite_and_invalid_scores_as_zero():
    result = format_response(
        {
            "scored_jobs": [
                {"jobId": "nan", "suitabilityScore": float("nan")},
                {"jobId": "inf", "suitabilityScore": float("inf")},
                {"jobId": "bad", "suitabilityScore": "not-a-number"},
            ]
        }
    )

    assert result["response_jobs"] == []


def test_format_response_normalizes_non_string_original_link_to_none():
    result = format_response(
        {
            "scored_jobs": [
                {
                    "jobId": "1",
                    "suitabilityScore": 0.8,
                    "originalLink": {"href": "https://example.com/1"},
                }
            ]
        }
    )

    assert result["response_jobs"][0].originalLink is None


def test_format_response_uses_fallback_defaults_for_missing_analysis():
    result = format_response(
        {
            "scored_jobs": [
                {
                    "jobId": "1",
                    "suitabilityScore": 0.8,
                }
            ]
        }
    )

    analysis = result["response_jobs"][0].analysis
    assert analysis.matchReason == "추천 이유가 충분히 생성되지 않았습니다."
    assert analysis.missingPoints == "보완점 정보가 충분히 생성되지 않았습니다."
    assert analysis.checkpointGuide == "지원 전 원문 공고를 확인하세요."


def test_format_response_includes_job_introduction_from_enriched_jobs():
    result = format_response(
        {
            "scored_jobs": [
                {
                    "jobId": "1",
                    "companyName": "A",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 0.8,
                    "sourceSnapshot": "검색 스냅샷",
                }
            ],
            "enriched_jobs": [
                {
                    "jobId": "1",
                    "companyName": "A",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 0.8,
                    "jobIntroduction": "상세 소개입니다.",
                }
            ],
        }
    )

    job = result["response_jobs"][0]
    assert job.jobIntroduction == "상세 소개입니다."


def test_format_response_prefers_empty_enriched_jobs_over_scored_jobs():
    result = format_response(
        {
            "enriched_jobs": [],
            "scored_jobs": [{"jobId": "1", "suitabilityScore": 0.8}],
        }
    )

    assert result == {"response_jobs": []}
