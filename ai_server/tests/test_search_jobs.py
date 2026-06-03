from types import SimpleNamespace

import pytest

from app.api.schemas import AnalyzeRequest, Preferences
from app.graph.nodes.build_query import build_query
from app.graph.nodes.search_jobs import search_jobs
from app.integrations.pathsdog_mcp import (
    PathsdogMCPError,
    _content_to_dict,
    _extract_items_from_payload,
    _extract_payload_from_result,
    _parse_search_jobs_text,
    select_tool_name,
)


def test_build_query_combines_profile_and_preferences():
    request = AnalyzeRequest(
        coverLetter="Spring Redis 프로젝트",
        preferences=Preferences(
            jobRole="백엔드 개발자",
            experienceLevel="신입",
            techStack=["Spring", "Redis"],
            region="서울",
        ),
    )
    state = {
        "request": request,
        "user_profile": {
            "technicalSkills": ["Spring", "Redis"],
            "jobDirection": "백엔드 개발자",
        },
    }

    result = build_query(state)

    assert result["search_query"]["query"] == "백엔드"
    assert result["search_query"]["skills"] == ["Spring", "Redis"]
    assert result["search_query"]["experience_filter"] == "신입"
    assert result["search_query"]["status"] == "active"
    assert result["search_query"]["limit"] == 10


def test_build_query_keeps_pathsdog_search_broad_for_many_skills():
    request = AnalyzeRequest(
        coverLetter="제조 데이터와 LLM 경험",
        preferences=Preferences(
            jobRole="제조 DX 데이터 엔지니어 Level 2 시스템 개발자",
            experienceLevel="신입",
            techStack=[
                "Python",
                "CNN",
                "Azure",
                "Event Hub",
                "Stream Analytics",
                "Databricks",
                "Blob Storage",
                "Parquet",
                "LLM",
                "Llama",
                "Gemini",
            ],
            region="포항, 광양, 판교, 서울",
        ),
    )

    result = build_query({"request": request, "user_profile": {}})

    assert result["search_query"]["query"] == "데이터"
    assert result["search_query"]["skills"] == ["Python", "LLM"]
    assert result["search_query"]["experience_filter"] == "신입"


def test_select_tool_name_prefers_search_tool():
    tools = ["get_job_detail", "search_jobs", "list_companies"]

    assert select_tool_name(tools, ["search", "job"]) == "search_jobs"


def test_select_tool_name_prefers_exact_known_name_before_substring_match():
    tools = ["search_job_filters", "search_jobs"]

    assert select_tool_name(tools, ["search", "job"]) == "search_jobs"


def test_select_tool_name_raises_when_missing():
    with pytest.raises(ValueError, match="No MCP tool"):
        select_tool_name(["list_companies"], ["search", "job"])


def test_content_to_dict_returns_structured_content_dict():
    result = SimpleNamespace(structuredContent={"jobs": [{"jobId": "1"}]}, content=None)

    assert _content_to_dict(result) == {"jobs": [{"jobId": "1"}]}


def test_content_to_dict_wraps_json_text_list_payload():
    result = SimpleNamespace(
        structuredContent=None,
        content=[SimpleNamespace(text='[{"jobId": "1"}, {"jobId": "2"}]')],
    )

    assert _content_to_dict(result) == {"items": [{"jobId": "1"}, {"jobId": "2"}]}


def test_content_to_dict_raises_pathsdog_error_for_malformed_json_text():
    result = SimpleNamespace(structuredContent=None, content=[SimpleNamespace(text='{"broken"')])

    with pytest.raises(PathsdogMCPError, match="Invalid JSON"):
        _content_to_dict(result)


def test_content_to_dict_returns_empty_items_for_no_search_results_text():
    result = SimpleNamespace(
        structuredContent=None,
        content=[SimpleNamespace(text="검색 결과가 없습니다. 키워드를 줄이거나 다른 조합으로 재시도해보세요.")],
    )

    assert _content_to_dict(result) == {"items": []}


def test_parse_search_jobs_text_extracts_job_rows():
    text = """이번 페이지 2개 채용공고:

[ID:395] SK실트론 - LLM 모델 데이터 관리
  기술: Python, Java, LLM, Data Management
  경력: 경력무관 (신입~시니어) | 근무지: 서울 | 정규직
  마감: 2026-04-12
  링크: https://www.skcareers.com/Recruit/Detail/R260672

[ID:485] 캐시워크 (넛지헬스케어) - [병역특례] 데이터분석 산업기능요원
  기술: SQL, Python, Data Analysis
  경력: 경력 무관 | 근무지: 넛지캠퍼스빌딩 | 전문연구요원
  상시채용 | 근무형태: 오피스
  링크: https://cashwalk12.career.greetinghr.com/ko/o/30833
"""

    jobs = _parse_search_jobs_text(text)

    assert jobs is not None
    assert jobs[0]["jobId"] == "395"
    assert jobs[0]["companyName"] == "SK실트론"
    assert jobs[0]["jobTitle"] == "LLM 모델 데이터 관리"
    assert jobs[0]["skills"] == ["Python", "Java", "LLM", "Data Management"]
    assert jobs[0]["deadline"] == "2026-04-12"
    assert jobs[1]["deadline"] == "상시채용"


def test_extract_items_from_payload_returns_empty_list_for_non_list_items():
    assert _extract_items_from_payload({"jobs": {"jobId": "1"}}) == []
    assert _extract_items_from_payload({"items": {"jobId": "1"}}) == []
    assert _extract_items_from_payload({"results": {"jobId": "1"}}) == []


def test_extract_payload_from_result_raises_pathsdog_error_for_tool_error():
    result = SimpleNamespace(isError=True, content=[SimpleNamespace(text="upstream exploded")])

    with pytest.raises(PathsdogMCPError, match="Pathsdog MCP tool returned an error"):
        _extract_payload_from_result(result)


class FakePathsdogClient:
    async def search_jobs(self, query):
        return [
            {
                "jobId": "1",
                "companyName": "테스트회사",
                "jobTitle": "백엔드 개발자",
                "sourceSnapshot": "Spring API 개발",
                "originalLink": "https://example.com/jobs/1",
            }
        ]


@pytest.mark.asyncio
async def test_search_jobs_node_stores_candidates():
    state = {"search_query": {"keyword": "백엔드 Spring", "limit": 10}}

    result = await search_jobs(state, FakePathsdogClient())

    assert result["candidate_jobs"][0]["companyName"] == "테스트회사"
