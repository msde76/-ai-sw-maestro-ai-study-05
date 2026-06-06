# Full Job Description Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 최종 추천된 최대 5개 채용공고에 Pathsdog MCP 상세 내용을 붙여 `jobIntroduction` 필드로 Spring 서버에 반환한다.

**Architecture:** `score_jobs` 이후 `enrich_job_details` LangGraph 노드를 추가한다. 이 노드는 최종 응답 대상 공고만 선별하고 `get_job_detail(include_full_description=true)`를 호출해 `[상세 내용]` 또는 `[요약]`을 `jobIntroduction`으로 채운다. `format_response`는 보강된 `enriched_jobs`를 `JobData` DTO로 변환한다.

**Tech Stack:** FastAPI, Pydantic, LangGraph, MCP streamable HTTP client, pytest, Spring Boot, Lombok, Jackson.

---

## 파일 구조

- Modify: `ai_server/app/api/schemas.py`
  - `JobData`에 `jobIntroduction: str` 응답 필드를 추가한다.
- Modify: `ai_server/app/graph/state.py`
  - `enriched_jobs: list[dict[str, Any]]` state 필드를 추가한다.
- Modify: `ai_server/app/graph/nodes/format_response.py`
  - 최종 공고 선별 helper를 분리하고, `jobIntroduction`을 DTO에 포함한다.
- Create: `ai_server/app/graph/nodes/enrich_job_details.py`
  - 상세 조회, 상세 raw text 파싱, per-job fallback을 담당한다.
- Modify: `ai_server/app/graph/workflow.py`
  - `score_jobs -> enrich_job_details -> format_response` 흐름으로 그래프를 연결한다.
- Modify: `ai_server/app/integrations/pathsdog_mcp.py`
  - `get_job_detail()` 메서드와 detail text 추출 helper를 추가한다.
- Modify: `ai_server/tests/test_contract.py`
  - FastAPI 응답 DTO 계약에 `jobIntroduction`을 추가한다.
- Modify: `ai_server/tests/test_scoring_and_formatting.py`
  - 공통 선별 helper와 `format_response`의 `jobIntroduction` 변환을 검증한다.
- Modify: `ai_server/tests/test_search_jobs.py`
  - MCP detail text 추출 helper를 검증한다.
- Create: `ai_server/tests/test_enrich_job_details.py`
  - 상세 보강 노드의 파싱, 최대 5개 호출, fallback 동작을 검증한다.
- Modify: `ai_server/tests/test_workflow.py`
  - 전체 workflow가 상세 보강 후 `jobIntroduction`을 반환하는지 검증한다.
- Modify: `backend/AI/src/main/java/Job/AI/domain/jobs/dto/JobResponseDTO.java`
  - Spring 응답 DTO에 `jobIntroduction` 필드를 추가한다.
- Modify: `ai_server/README.md`
  - 이미 추가된 MCP raw 응답 설명에 최종 구현 흐름과 `jobIntroduction` 응답 예시를 반영한다.

## Task 1: FastAPI 응답 DTO와 format helper 준비

**Files:**
- Modify: `ai_server/app/api/schemas.py`
- Modify: `ai_server/app/graph/nodes/format_response.py`
- Modify: `ai_server/tests/test_contract.py`
- Modify: `ai_server/tests/test_scoring_and_formatting.py`

- [ ] **Step 1: `JobData` 계약 실패 테스트 작성**

Modify `ai_server/tests/test_contract.py` so the existing test includes `jobIntroduction`.

```python
from app.api.schemas import Analysis, JobData


def test_job_data_serializes_to_spring_dto_shape():
    job = JobData(
        jobId="1",
        companyName="회사",
        jobTitle="백엔드 개발자",
        jobIntroduction="회사와 포지션 상세 소개입니다.",
        suitabilityScore=0.87,
        compensation="원문 확인 필요",
        deadline="원문 확인 필요",
        originalLink="https://example.com/1",
        analysis=Analysis(
            matchReason="Spring 경험과 관련성이 높습니다.",
            missingPoints="운영 경험 보완이 필요합니다.",
            checkpointGuide="API 성능 개선 경험을 강조하세요.",
        ),
    )

    assert job.model_dump() == {
        "jobId": "1",
        "companyName": "회사",
        "jobTitle": "백엔드 개발자",
        "jobIntroduction": "회사와 포지션 상세 소개입니다.",
        "suitabilityScore": 0.87,
        "compensation": "원문 확인 필요",
        "deadline": "원문 확인 필요",
        "originalLink": "https://example.com/1",
        "analysis": {
            "matchReason": "Spring 경험과 관련성이 높습니다.",
            "missingPoints": "운영 경험 보완이 필요합니다.",
            "checkpointGuide": "API 성능 개선 경험을 강조하세요.",
        },
    }
```

- [ ] **Step 2: 계약 테스트 실패 확인**

Run:

```bash
cd ai_server
.venv/bin/pytest tests/test_contract.py -q
```

Expected: FAIL with a Pydantic validation error mentioning `jobIntroduction`.

- [ ] **Step 3: `JobData`에 필드 추가**

Modify `ai_server/app/api/schemas.py`:

```python
class JobData(BaseModel):
    jobId: str
    companyName: str
    jobTitle: str
    jobIntroduction: str
    suitabilityScore: float = Field(ge=0.0, le=1.0)
    compensation: str
    deadline: str
    originalLink: str | None = None
    analysis: Analysis
```

- [ ] **Step 4: `format_response` 테스트 확장**

Add these tests to `ai_server/tests/test_scoring_and_formatting.py`.

```python
from app.graph.nodes.format_response import format_response, select_response_jobs


def test_select_response_jobs_prioritizes_threshold_and_backfills_to_five():
    raw_jobs = [
        {"jobId": str(i), "suitabilityScore": score}
        for i, score in enumerate([0.95, 0.91, 0.68, 0.8, 0.4, 0.69], start=1)
    ]

    selected = select_response_jobs(raw_jobs)

    assert [job["jobId"] for job in selected] == ["1", "2", "4", "6", "3"]


def test_format_response_includes_job_introduction():
    result = format_response(
        {
            "enriched_jobs": [
                {
                    "jobId": "1",
                    "companyName": "A",
                    "jobTitle": "백엔드 개발자",
                    "jobIntroduction": "상세 소개입니다.",
                    "suitabilityScore": 0.8,
                    "compensation": "원문 확인 필요",
                    "deadline": "상시채용",
                    "originalLink": "https://example.com/1",
                    "analysis": {
                        "matchReason": "관련성이 높습니다.",
                        "missingPoints": "보완점입니다.",
                        "checkpointGuide": "강조 포인트입니다.",
                    },
                }
            ]
        }
    )

    assert result["response_jobs"][0].jobIntroduction == "상세 소개입니다."
```

- [ ] **Step 5: format 테스트 실패 확인**

Run:

```bash
cd ai_server
.venv/bin/pytest tests/test_scoring_and_formatting.py::test_select_response_jobs_prioritizes_threshold_and_backfills_to_five tests/test_scoring_and_formatting.py::test_format_response_includes_job_introduction -q
```

Expected: FAIL because `select_response_jobs` and `jobIntroduction` support do not exist yet.

- [ ] **Step 6: `format_response.py` 구현**

Modify `ai_server/app/graph/nodes/format_response.py` to expose `select_response_jobs`, prefer `enriched_jobs`, and include `jobIntroduction`.

```python
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


def select_response_jobs(raw_jobs: list[dict]) -> list[dict]:
    valid_items = [item for item in raw_jobs if isinstance(item, dict)]
    strong_matches = [item for item in valid_items if _score(item) >= 0.7]
    backfill_matches = [item for item in valid_items if 0.0 < _score(item) < 0.7]
    strong_matches.sort(key=_score, reverse=True)
    backfill_matches.sort(key=_score, reverse=True)
    return [*strong_matches, *backfill_matches][:5]


def _original_link(raw: dict) -> str | None:
    value = raw.get("originalLink")
    return value if isinstance(value, str) else None


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
    selected = raw_jobs if state.get("enriched_jobs") is not None else select_response_jobs(raw_jobs)
    return {"response_jobs": [_to_job_data(item) for item in selected if isinstance(item, dict)]}
```

- [ ] **Step 7: Task 1 테스트 통과 확인**

Run:

```bash
cd ai_server
.venv/bin/pytest tests/test_contract.py tests/test_scoring_and_formatting.py -q
```

Expected: PASS.

- [ ] **Step 8: Task 1 커밋**

```bash
git add ai_server/app/api/schemas.py ai_server/app/graph/nodes/format_response.py ai_server/tests/test_contract.py ai_server/tests/test_scoring_and_formatting.py
git commit -m "feat: add job introduction response field"
```

## Task 2: MCP 상세 조회와 상세 텍스트 추출 추가

**Files:**
- Modify: `ai_server/app/integrations/pathsdog_mcp.py`
- Modify: `ai_server/tests/test_search_jobs.py`

- [ ] **Step 1: detail text helper 테스트 작성**

Add imports and tests in `ai_server/tests/test_search_jobs.py`.

```python
from app.integrations.pathsdog_mcp import (
    PathsdogMCPError,
    _content_text,
    _content_to_dict,
    _extract_items_from_payload,
    _extract_payload_from_result,
    _parse_search_jobs_text,
    select_tool_name,
)


def test_content_text_returns_first_text_content():
    result = SimpleNamespace(
        isError=False,
        content=[SimpleNamespace(text="상세 내용입니다.")],
    )

    assert _content_text(result) == "상세 내용입니다."


def test_content_text_raises_for_tool_error():
    result = SimpleNamespace(
        isError=True,
        content=[SimpleNamespace(text="upstream exploded")],
    )

    with pytest.raises(PathsdogMCPError, match="Pathsdog MCP tool returned an error"):
        _content_text(result)


def test_content_text_raises_for_missing_text():
    result = SimpleNamespace(isError=False, content=[])

    with pytest.raises(PathsdogMCPError, match="No text returned"):
        _content_text(result)
```

- [ ] **Step 2: helper 테스트 실패 확인**

Run:

```bash
cd ai_server
.venv/bin/pytest tests/test_search_jobs.py::test_content_text_returns_first_text_content tests/test_search_jobs.py::test_content_text_raises_for_tool_error tests/test_search_jobs.py::test_content_text_raises_for_missing_text -q
```

Expected: FAIL because `_content_text` does not exist.

- [ ] **Step 3: `_content_text`와 `get_job_detail` 구현**

Modify `ai_server/app/integrations/pathsdog_mcp.py`.

```python
def _content_text(result: Any) -> str:
    if getattr(result, "isError", False):
        raise PathsdogMCPError("Pathsdog MCP tool returned an error")

    content = getattr(result, "content", None) or []
    if content:
        text = getattr(content[0], "text", "")
        if isinstance(text, str) and text.strip():
            return text

    raise PathsdogMCPError("No text returned by Pathsdog MCP tool")
```

Add method inside `PathsdogMCPClient`:

```python
    async def get_job_detail(self, job_id: str | int, *, include_full_description: bool = True) -> str:
        try:
            numeric_job_id = int(job_id)
        except (TypeError, ValueError) as exc:
            raise PathsdogMCPError(f"Invalid Pathsdog job id: {job_id}") from exc

        async with streamablehttp_client(self._url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    "get_job_detail",
                    {
                        "job_id": numeric_job_id,
                        "include_full_description": include_full_description,
                    },
                )

        return _content_text(result)
```

- [ ] **Step 4: helper 테스트 통과 확인**

Run:

```bash
cd ai_server
.venv/bin/pytest tests/test_search_jobs.py -q
```

Expected: PASS.

- [ ] **Step 5: Task 2 커밋**

```bash
git add ai_server/app/integrations/pathsdog_mcp.py ai_server/tests/test_search_jobs.py
git commit -m "feat: add Pathsdog job detail client"
```

## Task 3: 상세 보강 노드 구현

**Files:**
- Create: `ai_server/app/graph/nodes/enrich_job_details.py`
- Modify: `ai_server/app/graph/state.py`
- Create: `ai_server/tests/test_enrich_job_details.py`

- [ ] **Step 1: 상세 parser와 enrich 노드 테스트 작성**

Create `ai_server/tests/test_enrich_job_details.py`.

```python
import pytest

from app.graph.nodes.enrich_job_details import enrich_job_details, extract_job_introduction


class FakeDetailClient:
    def __init__(self, details=None, fail_ids=None):
        self.details = details or {}
        self.fail_ids = set(fail_ids or [])
        self.calls = []

    async def get_job_detail(self, job_id, *, include_full_description=True):
        self.calls.append((str(job_id), include_full_description))
        if str(job_id) in self.fail_ids:
            raise RuntimeError("detail failed")
        return self.details[str(job_id)]


def _scored_job(job_id, score, source_snapshot=None):
    job = {
        "jobId": str(job_id),
        "companyName": f"회사{job_id}",
        "jobTitle": "백엔드 개발자",
        "suitabilityScore": score,
        "compensation": "원문 확인 필요",
        "deadline": "상시채용",
        "originalLink": f"https://example.com/{job_id}",
        "analysis": {
            "matchReason": "관련성이 높습니다.",
            "missingPoints": "보완점입니다.",
            "checkpointGuide": "가이드입니다.",
        },
    }
    if source_snapshot is not None:
        job["sourceSnapshot"] = source_snapshot
    return job


def test_extract_job_introduction_prefers_detail_section():
    text = """📋 김캐디 - 백엔드 개발자

[요약]
요약 문장입니다.

[상세 내용]
회사 소개 및 포지션 상세

주요업무 본문입니다.

원본: https://example.com
"""

    assert extract_job_introduction(text) == "회사 소개 및 포지션 상세\n\n주요업무 본문입니다."


def test_extract_job_introduction_falls_back_to_summary():
    text = """📋 김캐디 - 백엔드 개발자

[요약]
요약 문장입니다.

원본: https://example.com
"""

    assert extract_job_introduction(text) == "요약 문장입니다."


def test_extract_job_introduction_returns_empty_for_unknown_text():
    assert extract_job_introduction("상세 섹션이 없는 텍스트") == ""


@pytest.mark.asyncio
async def test_enrich_job_details_fetches_only_final_top_five_jobs():
    scored_jobs = [
        _scored_job(1, 0.95),
        _scored_job(2, 0.91),
        _scored_job(3, 0.68),
        _scored_job(4, 0.8),
        _scored_job(5, 0.4),
        _scored_job(6, 0.69),
    ]
    details = {
        str(job_id): f"[상세 내용]\n상세 {job_id}\n원본: https://example.com/{job_id}"
        for job_id in [1, 2, 3, 4, 6]
    }
    client = FakeDetailClient(details)

    result = await enrich_job_details({"scored_jobs": scored_jobs}, client)

    assert [job["jobId"] for job in result["enriched_jobs"]] == ["1", "2", "4", "6", "3"]
    assert client.calls == [
        ("1", True),
        ("2", True),
        ("4", True),
        ("6", True),
        ("3", True),
    ]
    assert result["enriched_jobs"][0]["jobIntroduction"] == "상세 1"


@pytest.mark.asyncio
async def test_enrich_job_details_falls_back_to_source_snapshot_when_detail_fails():
    client = FakeDetailClient(details={}, fail_ids={"1"})

    result = await enrich_job_details(
        {"scored_jobs": [_scored_job(1, 0.8, source_snapshot="검색 스냅샷")]},
        client,
    )

    assert result["enriched_jobs"][0]["jobIntroduction"] == "검색 스냅샷"


@pytest.mark.asyncio
async def test_enrich_job_details_uses_default_text_without_snapshot():
    client = FakeDetailClient(details={}, fail_ids={"1"})

    result = await enrich_job_details({"scored_jobs": [_scored_job(1, 0.8)]}, client)

    assert result["enriched_jobs"][0]["jobIntroduction"] == "원문 확인 필요"
```

- [ ] **Step 2: enrich 테스트 실패 확인**

Run:

```bash
cd ai_server
.venv/bin/pytest tests/test_enrich_job_details.py -q
```

Expected: FAIL because `app.graph.nodes.enrich_job_details` does not exist.

- [ ] **Step 3: `GraphState`에 `enriched_jobs` 추가**

Modify `ai_server/app/graph/state.py`:

```python
class GraphState(TypedDict, total=False):
    request: AnalyzeRequest
    user_profile: dict[str, Any]
    search_query: dict[str, Any]
    candidate_jobs: list[dict[str, Any]]
    scored_jobs: list[dict[str, Any]]
    enriched_jobs: list[dict[str, Any]]
    response_jobs: list[JobData]
```

- [ ] **Step 4: `enrich_job_details.py` 구현**

Create `ai_server/app/graph/nodes/enrich_job_details.py`.

```python
import re
from typing import Protocol

from app.graph.nodes.format_response import select_response_jobs
from app.graph.state import GraphState


DEFAULT_JOB_INTRODUCTION = "원문 확인 필요"


class JobDetailClient(Protocol):
    async def get_job_detail(self, job_id: str | int, *, include_full_description: bool = True) -> str:
        ...


def extract_job_introduction(detail_text: str) -> str:
    detail = _extract_section(detail_text, "상세 내용")
    if detail:
        return detail
    return _extract_section(detail_text, "요약")


def _extract_section(text: str, title: str) -> str:
    pattern = rf"\[{re.escape(title)}\]\s*(?P<body>.*?)(?=\n\[[^\]]+\]|\n원본:|\Z)"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return ""
    return match.group("body").strip()


def _fallback_introduction(job: dict) -> str:
    snapshot = job.get("sourceSnapshot")
    if isinstance(snapshot, str) and snapshot.strip():
        return snapshot.strip()
    return DEFAULT_JOB_INTRODUCTION


async def _with_job_introduction(job: dict, client: JobDetailClient) -> dict:
    enriched = dict(job)
    try:
        detail_text = await client.get_job_detail(job["jobId"], include_full_description=True)
        introduction = extract_job_introduction(detail_text)
    except Exception:
        introduction = ""

    enriched["jobIntroduction"] = introduction or _fallback_introduction(job)
    return enriched


async def enrich_job_details(state: GraphState, client: JobDetailClient) -> GraphState:
    selected_jobs = select_response_jobs(state.get("scored_jobs", []))
    enriched_jobs = [
        await _with_job_introduction(job, client)
        for job in selected_jobs
    ]
    return {"enriched_jobs": enriched_jobs}
```

- [ ] **Step 5: enrich 테스트 통과 확인**

Run:

```bash
cd ai_server
.venv/bin/pytest tests/test_enrich_job_details.py -q
```

Expected: PASS.

- [ ] **Step 6: Task 3 커밋**

```bash
git add ai_server/app/graph/state.py ai_server/app/graph/nodes/enrich_job_details.py ai_server/tests/test_enrich_job_details.py
git commit -m "feat: enrich final jobs with detail introductions"
```

## Task 4: LangGraph workflow에 상세 보강 노드 연결

**Files:**
- Modify: `ai_server/app/graph/workflow.py`
- Modify: `ai_server/tests/test_workflow.py`

- [ ] **Step 1: workflow 테스트 수정**

Modify `FakeSearchClient` in `ai_server/tests/test_workflow.py` to support detail lookup.

```python
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
                "sourceSnapshot": "검색 결과 스냅샷",
                "originalLink": "https://example.com/jobs/1",
            }
        ]

    async def get_job_detail(self, job_id, *, include_full_description=True):
        self.detail_calls.append((str(job_id), include_full_description))
        return """📋 테스트컴퍼니 - 백엔드 개발자

[요약]
요약입니다.

[상세 내용]
테스트컴퍼니 백엔드 포지션 상세 소개입니다.

원본: https://example.com/jobs/1
"""
```

Modify `test_workflow_returns_scored_jobs`:

```python
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
```

- [ ] **Step 2: workflow 테스트 실패 확인**

Run:

```bash
cd ai_server
.venv/bin/pytest tests/test_workflow.py::test_workflow_returns_scored_jobs -q
```

Expected: FAIL because the workflow does not call `enrich_job_details` yet.

- [ ] **Step 3: workflow에 노드 연결**

Modify `ai_server/app/graph/workflow.py`.

```python
from app.graph.nodes.enrich_job_details import enrich_job_details
```

Inside `build_workflow`:

```python
    async def enrich_job_details_node(state: GraphState) -> GraphState:
        return await enrich_job_details(state, search_client)
```

Register and connect the node:

```python
    graph.add_node("enrich_job_details", enrich_job_details_node)

    graph.add_edge("search_jobs", "score_jobs")
    graph.add_edge("score_jobs", "enrich_job_details")
    graph.add_edge("enrich_job_details", "format_response")
```

Remove the old direct edge:

```python
    graph.add_edge("score_jobs", "format_response")
```

- [ ] **Step 4: workflow 테스트 통과 확인**

Run:

```bash
cd ai_server
.venv/bin/pytest tests/test_workflow.py -q
```

Expected: PASS. The insufficient-info test should still skip search and detail lookup because it routes directly from `analyze_user` to `format_response`.

- [ ] **Step 5: Task 4 커밋**

```bash
git add ai_server/app/graph/workflow.py ai_server/tests/test_workflow.py
git commit -m "feat: wire job detail enrichment into workflow"
```

## Task 5: Spring 응답 DTO에 `jobIntroduction` 추가

**Files:**
- Modify: `backend/AI/src/main/java/Job/AI/domain/jobs/dto/JobResponseDTO.java`

- [ ] **Step 1: Spring DTO 필드 추가**

Modify `backend/AI/src/main/java/Job/AI/domain/jobs/dto/JobResponseDTO.java`.

```java
    @Builder
    @Getter
    @NoArgsConstructor
    @AllArgsConstructor
    public static class JobDataDTO {
        private String jobId;
        private String companyName;
        private String jobTitle;
        private String jobIntroduction;
        private Double suitabilityScore;
        private String compensation;
        private String deadline;
        private String originalLink;
        private AnalysisDTO analysis;
    }
```

- [ ] **Step 2: Spring 컴파일 테스트**

Run:

```bash
cd backend/AI
./gradlew test
```

Expected: PASS.

- [ ] **Step 3: Task 5 커밋**

```bash
git add backend/AI/src/main/java/Job/AI/domain/jobs/dto/JobResponseDTO.java
git commit -m "feat: add job introduction to Spring response dto"
```

## Task 6: README와 전체 검증

**Files:**
- Modify: `ai_server/README.md`

- [ ] **Step 1: README 구현 흐름 정리**

Update the existing Pathsdog MCP section in `ai_server/README.md` so it states the implemented flow:

````markdown
구현된 상세 소개 보강 흐름:

```text
score_jobs
  -> 최종 응답 대상 최대 5개 선별
  -> get_job_detail(include_full_description=true)
  -> [상세 내용] 우선 추출
  -> 없으면 [요약]
  -> 없으면 sourceSnapshot
  -> response JobData.jobIntroduction
```
````

Also update the response JSON examples to include:

```json
"jobIntroduction": "회사 소개 및 포지션 상세..."
```

- [ ] **Step 2: FastAPI 전체 테스트**

Run:

```bash
cd ai_server
.venv/bin/pytest -q
```

Expected: PASS.

- [ ] **Step 3: Spring 전체 테스트**

Run:

```bash
cd backend/AI
./gradlew test
```

Expected: PASS.

- [ ] **Step 4: Git 상태 확인**

Run:

```bash
git status --short
```

Expected: only intentional modified files from Task 6 should be listed before the commit.

- [ ] **Step 5: Task 6 커밋**

```bash
git add ai_server/README.md
git commit -m "docs: document job introduction enrichment"
```

## Task 7: 최종 통합 점검

**Files:**
- No file changes expected.

- [ ] **Step 1: 전체 diff 점검**

Run:

```bash
git log --oneline -8
git status --short
```

Expected:
- Recent commits include the Task 1-6 commits.
- `git status --short` is empty.

- [ ] **Step 2: 선택적 실제 MCP smoke test**

This requires network access and a valid `.env` for the AI server. Run only when network access is available.

```bash
cd ai_server
.venv/bin/python - <<'PY'
import asyncio
from app.integrations.pathsdog_mcp import PathsdogMCPClient
from app.graph.nodes.enrich_job_details import extract_job_introduction

async def main():
    client = PathsdogMCPClient("https://jobs.pathsdog.com/mcp")
    text = await client.get_job_detail(639, include_full_description=True)
    intro = extract_job_introduction(text)
    print(intro[:300])
    assert intro

asyncio.run(main())
PY
```

Expected: prints a non-empty introduction beginning with the detail or summary content for job `639`.

- [ ] **Step 3: 최종 테스트 명령 재실행**

Run:

```bash
cd ai_server
.venv/bin/pytest -q
cd ../backend/AI
./gradlew test
```

Expected: PASS for both commands.

## Self-Review

- Spec coverage: `jobIntroduction` DTO 추가, 최종 최대 5개 상세 조회, `[상세 내용]`/`[요약]` 파싱, fallback, workflow 연결, Spring DTO 반영, 테스트 계획이 모두 Task 1-7에 포함되어 있다.
- Placeholder scan: 이 계획에는 비어 있는 작업이나 빈 구현 지시가 없다. 각 코드 변경 단계는 구체적인 파일과 코드 조각을 포함한다.
- Type consistency: `jobIntroduction`, `enriched_jobs`, `get_job_detail`, `extract_job_introduction`, `select_response_jobs` 이름이 전 Task에서 동일하게 사용된다.
