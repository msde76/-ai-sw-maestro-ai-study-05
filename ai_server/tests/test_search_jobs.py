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
    select_tool_name,
)


def test_build_query_combines_profile_and_preferences():
    request = AnalyzeRequest(
        coverLetter="Spring Redis 프로젝트",
        preferences=Preferences(jobRole="백엔드 개발자", techStack=["Spring", "Redis"], region="서울"),
    )
    state = {
        "request": request,
        "user_profile": {
            "technicalSkills": ["Spring", "Redis"],
            "jobDirection": "백엔드 개발자",
        },
    }

    result = build_query(state)

    assert result["search_query"]["keyword"] == "백엔드 개발자 Spring Redis"
    assert result["search_query"]["region"] == "서울"
    assert result["search_query"]["limit"] == 10


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
