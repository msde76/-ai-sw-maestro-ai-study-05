import json

import pytest

from app.api.schemas import AnalyzeRequest, Preferences
from app.graph.nodes.analyze_user import analyze_user
from app.graph.nodes.check_completeness import route_by_completeness


class FakeLLM:
    def __init__(self, response=None):
        self.messages = None
        self.response = response or {
            "projectExperiences": ["예약 API 개발"],
            "technicalSkills": ["Spring", "Redis"],
            "roleSignals": ["백엔드 개발자"],
            "strengths": ["API 성능 개선"],
            "jobDirection": "백엔드 개발자",
            "missingInformation": [],
            "isSufficient": True,
        }

    async def complete_json(self, messages):
        self.messages = messages
        return self.response


@pytest.mark.asyncio
async def test_analyze_user_extracts_profile():
    request = AnalyzeRequest(
        coverLetter="Spring Boot 예약 API를 만들고 Redis 캐시로 성능을 개선했습니다.",
        preferences=Preferences(jobRole="백엔드 개발자", techStack=["Spring", "Redis"], region="서울"),
    )
    state = {"request": request}

    llm = FakeLLM()
    result = await analyze_user(state, llm)

    assert result["user_profile"]["technicalSkills"] == ["Spring", "Redis"]
    assert result["user_profile"]["isSufficient"] is True


@pytest.mark.asyncio
async def test_analyze_user_sends_valid_json_with_korean_text():
    request = AnalyzeRequest(
        coverLetter="Spring Boot 예약 API를 만들고 Redis 캐시로 성능을 개선했습니다.",
        preferences=Preferences(jobRole="백엔드 개발자", techStack=["Spring", "Redis"], region="서울"),
    )
    llm = FakeLLM()

    await analyze_user({"request": request}, llm)

    user_message = llm.messages[1]["content"]
    label, json_payload = user_message.split("\n", 1)
    parsed_payload = json.loads(json_payload)

    assert label == "Analyze this JSON input:"
    assert parsed_payload["coverLetter"] == "Spring Boot 예약 API를 만들고 Redis 캐시로 성능을 개선했습니다."
    assert parsed_payload["preferences"]["jobRole"] == "백엔드 개발자"
    assert "'coverLetter'" not in user_message


@pytest.mark.asyncio
async def test_analyze_user_rejects_string_bool_sufficiency():
    response = {
        "projectExperiences": ["예약 API 개발"],
        "technicalSkills": ["Spring", "Redis"],
        "roleSignals": ["백엔드 개발자"],
        "strengths": ["API 성능 개선"],
        "jobDirection": "백엔드 개발자",
        "missingInformation": [],
        "isSufficient": "true",
    }
    request = AnalyzeRequest(
        coverLetter="Spring Boot 예약 API를 만들고 Redis 캐시로 성능을 개선했습니다.",
        preferences=Preferences(jobRole="백엔드 개발자", techStack=["Spring", "Redis"], region="서울"),
    )

    with pytest.raises(ValueError):
        await analyze_user({"request": request}, FakeLLM(response))


@pytest.mark.asyncio
async def test_analyze_user_normalizes_object_experience_items():
    response = {
        "projectExperiences": [
            {
                "title": "USG AI 데이터 문제해결 제조 혁신 경진 대회",
                "summary": "LED 숫자 이미지 분류와 모델 재현성 관리",
            }
        ],
        "technicalSkills": ["CNN", {"tool": "k-cross validation"}],
        "roleSignals": ["제조 DX"],
        "strengths": [{"name": "실험 관리", "evidence": "모델명에 하이퍼파라미터와 성능 저장"}],
        "jobDirection": "제조 DX 데이터 엔지니어",
        "missingInformation": [],
        "isSufficient": True,
    }
    request = AnalyzeRequest(
        coverLetter="제조 데이터 경진대회에서 CNN 모델 실험을 관리했습니다.",
        preferences=Preferences(jobRole="제조 DX 데이터 엔지니어", techStack=["CNN"], region="포항"),
    )

    result = await analyze_user({"request": request}, FakeLLM(response))

    assert result["user_profile"]["projectExperiences"] == [
        "USG AI 데이터 문제해결 제조 혁신 경진 대회 / LED 숫자 이미지 분류와 모델 재현성 관리"
    ]
    assert result["user_profile"]["technicalSkills"] == ["CNN", "k-cross validation"]
    assert result["user_profile"]["strengths"] == ["실험 관리 / 모델명에 하이퍼파라미터와 성능 저장"]


@pytest.mark.asyncio
async def test_analyze_user_defaults_optional_planning_fields_when_llm_omits_them():
    response = {
        "projectExperiences": ["제조 데이터 분류 프로젝트"],
        "technicalSkills": ["Python", "CNN"],
        "roleSignals": ["제조 DX"],
        "strengths": ["실험 관리"],
    }
    request = AnalyzeRequest(
        coverLetter="제조 데이터 경진대회에서 CNN 모델 실험을 관리했습니다.",
        preferences=Preferences(jobRole="제조 DX 데이터 엔지니어", techStack=["CNN"], region="포항"),
    )

    result = await analyze_user({"request": request}, FakeLLM(response))

    assert result["user_profile"]["jobDirection"] == ""
    assert result["user_profile"]["missingInformation"] == []
    assert result["user_profile"]["isSufficient"] is True


def test_route_by_completeness_continues_when_sufficient():
    state = {"user_profile": {"isSufficient": True}}

    assert route_by_completeness(state) == "build_query"


def test_route_by_completeness_stops_when_insufficient():
    state = {"user_profile": {"isSufficient": False}}

    assert route_by_completeness(state) == "format_response"
