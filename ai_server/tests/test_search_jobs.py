from types import SimpleNamespace

import pytest

from app.api.schemas import AnalyzeRequest, Preferences
from app.graph.nodes.build_query import build_query
from app.graph.nodes.search_jobs import search_jobs
from app.integrations.pathsdog_mcp import (
    PathsdogMCPError,
    _content_text,
    _content_to_dict,
    _extract_items_from_payload,
    _extract_payload_from_result,
    _parse_search_jobs_text,
    select_tool_name,
)


def test_build_query_maps_generic_role_to_skills_not_query():
    request = AnalyzeRequest(
        coverLetter="Spring Redis 프로젝트",
        preferences=Preferences(
            jobRole="백엔드 개발자",
            experienceLevel="신입",
            techStack=["Java", "Spring Boot", "JPA"],
            region="서울",
        ),
    )
    state = {
        "request": request,
        "user_profile": {
            "technicalSkills": ["React"],
            "jobDirection": "프론트엔드 개발자",
            "roleSignals": ["프론트엔드"],
        },
    }

    result = build_query(state)

    assert "query" not in result["search_query"]
    assert result["search_query"]["skills"] == ["Java", "Spring Boot", "JPA", "Backend"]
    assert result["search_query"]["experience_filter"] == "신입"
    assert result["search_query"]["urgency"] == "all"
    assert result["search_query"]["status"] == "active"
    assert result["search_query"]["limit"] == 20
    assert "region" not in result["search_query"]


def test_build_query_limits_large_tech_stack_for_broad_mcp_search():
    request = AnalyzeRequest(
        coverLetter="Java Spring Boot 백엔드 프로젝트",
        preferences=Preferences(
            jobRole="백엔드 개발자",
            experienceLevel="신입",
            techStack=[
                "Java",
                "Spring",
                "Spring Boot",
                "JPA",
                "MySQL",
                "SQL",
                "Redis",
                "Docker",
                "AWS",
                "Nginx",
                "REST API",
                "JWT",
                "GitHub",
            ],
            region="서울, 경기, 판교",
        ),
    )

    result = build_query({"request": request, "user_profile": {}})

    assert result["search_query"]["skills"] == ["Java", "Spring Boot", "Backend"]
    assert result["search_query"]["experience_filter"] == "신입"
    assert "region" not in result["search_query"]


def test_build_query_uses_preferences_before_conflicting_profile():
    request = AnalyzeRequest(
        coverLetter="React 프로젝트와 Spring 프로젝트를 모두 경험했습니다.",
        preferences=Preferences(
            jobRole="프론트엔드 개발자",
            experienceLevel="주니어",
            techStack=["React", "TypeScript"],
            onlyWithReward=True,
            isUrgent=True,
        ),
    )
    state = {
        "request": request,
        "user_profile": {
            "technicalSkills": ["Java", "Spring Boot"],
            "jobDirection": "백엔드 개발자",
            "roleSignals": ["백엔드"],
        },
    }

    result = build_query(state)

    assert "query" not in result["search_query"]
    assert result["search_query"]["skills"] == ["React", "TypeScript", "Frontend"]
    assert result["search_query"]["experience_filter"] == "주니어"
    assert result["search_query"]["has_compensation"] is True
    assert result["search_query"]["urgency"] == "closing_soon"


def test_build_query_falls_back_to_profile_skills_and_roles():
    request = AnalyzeRequest(
        coverLetter="Python과 LLM으로 AI 백엔드 서비스를 만들었습니다.",
        preferences=Preferences(),
    )
    state = {
        "request": request,
        "user_profile": {
            "technicalSkills": ["Python", "LLM"],
            "jobDirection": "AI 백엔드 엔지니어",
            "roleSignals": ["LLM 서비스 개발"],
        },
    }

    result = build_query(state)

    assert result["search_query"]["query"] == "LLM"
    assert result["search_query"]["skills"] == ["Python", "LLM", "AI", "Backend"]
    assert result["search_query"]["urgency"] == "all"
    assert result["search_query"]["status"] == "active"
    assert result["search_query"]["limit"] == 20


def test_build_query_keeps_distinctive_domain_keyword_in_query():
    request = AnalyzeRequest(
        coverLetter="Kubernetes와 AWS 운영 경험이 있습니다.",
        preferences=Preferences(
            jobRole="SRE 엔지니어",
            techStack=["Kubernetes", "AWS"],
        ),
    )

    result = build_query({"request": request, "user_profile": {}})

    assert result["search_query"]["query"] == "SRE"
    assert result["search_query"]["skills"] == ["Kubernetes", "AWS"]


def test_build_query_maps_english_role_aliases_to_skills():
    request = AnalyzeRequest(
        coverLetter="Worked across product surfaces and platform APIs.",
        preferences=Preferences(jobRole="backend frontend fullstack"),
    )
    state = {
        "request": request,
        "user_profile": {
            "technicalSkills": ["TypeScript"],
            "jobDirection": "backend server",
        },
    }

    result = build_query(state)

    assert "query" not in result["search_query"]
    assert result["search_query"]["skills"] == ["TypeScript", "Backend", "Frontend", "Fullstack"]


@pytest.mark.parametrize("role", ["HTML 퍼블리셔", "Mainframe developer", "frontier engineer"])
def test_build_query_does_not_match_english_aliases_inside_words(role):
    request = AnalyzeRequest(
        coverLetter="Publication and enterprise systems experience.",
        preferences=Preferences(jobRole=role, techStack=["CSS"]),
    )

    result = build_query({"request": request, "user_profile": {}})

    assert "query" not in result["search_query"]
    assert result["search_query"]["skills"] == ["CSS"]


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


def test_content_text_returns_first_text_content():
    result = SimpleNamespace(
        isError=False,
        content=[SimpleNamespace(text="job detail text"), SimpleNamespace(text="ignored")],
    )

    assert _content_text(result) == "job detail text"


def test_content_text_skips_empty_and_non_text_items_before_returning_later_text():
    result = SimpleNamespace(
        isError=False,
        content=[
            SimpleNamespace(text=""),
            SimpleNamespace(),
            SimpleNamespace(text=None),
            SimpleNamespace(text="detail text"),
        ],
    )

    assert _content_text(result) == "detail text"


def test_content_text_raises_pathsdog_error_for_tool_error():
    result = SimpleNamespace(isError=True, content=[SimpleNamespace(text="upstream exploded")])

    with pytest.raises(PathsdogMCPError, match="Pathsdog MCP tool returned an error"):
        _content_text(result)


def test_content_text_raises_pathsdog_error_when_text_missing():
    result = SimpleNamespace(isError=False, content=[SimpleNamespace(text="")])

    with pytest.raises(PathsdogMCPError, match="No text returned by Pathsdog MCP tool"):
        _content_text(result)


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


class FakeStreamableHTTPClient:
    def __init__(self, url):
        self.url = url

    async def __aenter__(self):
        return ("read-stream", "write-stream", None)

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeClientSession:
    instances = []

    def __init__(self, read_stream, write_stream):
        self.read_stream = read_stream
        self.write_stream = write_stream
        self.initialized = False
        self.call_tool_calls = []
        self.list_tools_calls = 0
        FakeClientSession.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def initialize(self):
        self.initialized = True

    async def list_tools(self):
        self.list_tools_calls += 1
        return SimpleNamespace(
            tools=[
                SimpleNamespace(name="search_jobs"),
                SimpleNamespace(name="job_detail_lookup"),
            ]
        )

    async def call_tool(self, tool_name, payload):
        self.call_tool_calls.append((tool_name, payload))
        return SimpleNamespace(isError=False, content=[SimpleNamespace(text="detail payload")])


@pytest.mark.asyncio
async def test_get_job_detail_uses_listed_tool_and_passes_payload(monkeypatch):
    FakeClientSession.instances.clear()
    monkeypatch.setattr("app.integrations.pathsdog_mcp.streamablehttp_client", FakeStreamableHTTPClient)
    monkeypatch.setattr("app.integrations.pathsdog_mcp.ClientSession", FakeClientSession)

    from app.integrations.pathsdog_mcp import PathsdogMCPClient

    client = PathsdogMCPClient("http://example.test")
    result = await client.get_job_detail("42", include_full_description=False)

    assert result == "detail payload"
    assert len(FakeClientSession.instances) == 1
    session = FakeClientSession.instances[0]
    assert session.initialized is True
    assert session.list_tools_calls == 1
    assert session.call_tool_calls == [
        (
            "job_detail_lookup",
            {"job_id": 42, "include_full_description": False},
        )
    ]


@pytest.mark.asyncio
async def test_get_job_detail_raises_for_invalid_job_id(monkeypatch):
    monkeypatch.setattr("app.integrations.pathsdog_mcp.streamablehttp_client", FakeStreamableHTTPClient)
    monkeypatch.setattr("app.integrations.pathsdog_mcp.ClientSession", FakeClientSession)

    from app.integrations.pathsdog_mcp import PathsdogMCPClient

    client = PathsdogMCPClient("http://example.test")

    with pytest.raises(PathsdogMCPError, match="Invalid Pathsdog job id: invalid"):
        await client.get_job_detail("invalid")


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
