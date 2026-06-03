import pytest

from app.api.schemas import AnalyzeRequest, Preferences
from app.graph.nodes.analyze_user import analyze_user
from app.graph.nodes.check_completeness import route_by_completeness


class FakeLLM:
    async def complete_json(self, messages):
        return {
            "projectExperiences": ["예약 API 개발"],
            "technicalSkills": ["Spring", "Redis"],
            "roleSignals": ["백엔드 개발자"],
            "strengths": ["API 성능 개선"],
            "jobDirection": "백엔드 개발자",
            "missingInformation": [],
            "isSufficient": True,
        }


@pytest.mark.asyncio
async def test_analyze_user_extracts_profile():
    request = AnalyzeRequest(
        coverLetter="Spring Boot 예약 API를 만들고 Redis 캐시로 성능을 개선했습니다.",
        preferences=Preferences(jobRole="백엔드 개발자", techStack=["Spring", "Redis"], region="서울"),
    )
    state = {"request": request}

    result = await analyze_user(state, FakeLLM())

    assert result["user_profile"]["technicalSkills"] == ["Spring", "Redis"]
    assert result["user_profile"]["isSufficient"] is True


def test_route_by_completeness_continues_when_sufficient():
    state = {"user_profile": {"isSufficient": True}}

    assert route_by_completeness(state) == "build_query"


def test_route_by_completeness_stops_when_insufficient():
    state = {"user_profile": {"isSufficient": False}}

    assert route_by_completeness(state) == "format_response"
