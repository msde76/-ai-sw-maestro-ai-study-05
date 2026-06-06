import pytest

from app.api.schemas import AnalyzeRequest, Preferences
from app.graph.workflow import build_workflow, run_workflow


class FakeLLM:
    def __init__(self):
        self.calls = 0

    async def complete_json(self, messages, *, json_schema=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "projectExperiences": ["예약 API 개발"],
                "technicalSkills": ["Spring", "Redis"],
                "roleSignals": ["백엔드 개발자"],
                "strengths": ["API 성능 개선"],
                "jobDirection": "백엔드 개발자",
                "missingInformation": [],
                "isSufficient": True,
            }
        return {
            "jobs": [
                {
                    "jobId": "1",
                    "companyName": "테스트컴퍼니",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 0.8,
                    "compensation": "원문 확인 필요",
                    "deadline": "상시",
                    "originalLink": "https://example.com/jobs/1",
                    "analysis": {
                        "matchReason": "Spring API 경험이 공고와 잘 맞습니다.",
                        "missingPoints": "클라우드 운영 경험 보강이 필요합니다.",
                        "checkpointGuide": "지원 전 요구 기술을 확인하세요.",
                    },
                }
            ]
        }


class FakeSearchClient:
    def __init__(self):
        self.detail_calls = []

    async def search_jobs(self, query):
        return [
            {
                "jobId": "1",
                "companyName": "테스트컴퍼니",
                "jobTitle": "백엔드 개발자",
                "requirements": ["Spring", "Redis"],
                "originalLink": "https://example.com/jobs/1",
            }
        ]

    async def get_job_detail(self, job_id, include_full_description=True):
        self.detail_calls.append((job_id, include_full_description))
        return "[상세 내용] 테스트컴퍼니 백엔드 포지션 상세 소개입니다."


class InsufficientInfoLLM:
    def __init__(self):
        self.calls = 0

    async def complete_json(self, messages, *, json_schema=None):
        self.calls += 1
        return {
            "projectExperiences": [],
            "technicalSkills": [],
            "roleSignals": [],
            "strengths": [],
            "jobDirection": "",
            "missingInformation": ["프로젝트 경험"],
            "isSufficient": False,
        }


class TrackingSearchClient:
    def __init__(self):
        self.calls = 0
        self.detail_calls = []

    async def search_jobs(self, query):
        self.calls += 1
        return []

    async def get_job_detail(self, job_id, include_full_description=True):
        self.detail_calls.append((job_id, include_full_description))
        return ""


@pytest.mark.asyncio
async def test_workflow_returns_scored_jobs():
    request = AnalyzeRequest(
        coverLetter="Spring Boot 예약 API를 만들고 Redis 캐시로 성능을 개선했습니다.",
        preferences=Preferences(jobRole="백엔드 개발자", techStack=["Spring", "Redis"], region="서울"),
    )
    search_client = FakeSearchClient()
    workflow = build_workflow(FakeLLM(), search_client)

    jobs = await run_workflow(workflow, request)

    assert len(jobs) == 1
    assert jobs[0].jobId == "1"
    assert jobs[0].suitabilityScore == 0.8
    assert jobs[0].jobIntroduction == "테스트컴퍼니 백엔드 포지션 상세 소개입니다."
    assert search_client.detail_calls == [("1", True)]


@pytest.mark.asyncio
async def test_workflow_returns_empty_without_search_when_profile_is_insufficient():
    request = AnalyzeRequest(
        coverLetter="프로젝트 경험을 더 정리해야 합니다.",
        preferences=Preferences(
            jobRole="백엔드 개발자",
            experienceLevel="신입",
            techStack=["Spring", "Redis"],
            region="서울",
            onlyWithReward=False,
            isUrgent=False,
        ),
    )
    llm = InsufficientInfoLLM()
    search_client = TrackingSearchClient()
    workflow = build_workflow(llm, search_client)

    jobs = await run_workflow(workflow, request)

    assert jobs == []
    assert llm.calls == 1
    assert search_client.calls == 0
    assert search_client.detail_calls == []
