# LangGraph FastAPI AI Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate FastAPI server that implements `POST /ai/analyze`, runs a LangGraph workflow with two LLM-powered agents, calls Pathsdog remote MCP directly, and returns Spring-compatible `JobDataDTO[]`.

**Architecture:** FastAPI owns HTTP validation and response serialization. LangGraph owns the workflow state and node transitions. Upstage is called through the OpenAI-compatible SDK, while Pathsdog MCP is called through the Python MCP client as a deterministic integration node.

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, LangGraph, OpenAI Python SDK, MCP Python SDK, pytest, pytest-asyncio, httpx, Uvicorn.

---

## File Map

- Create `ai_server/requirements.txt`: Python dependencies for the AI server.
- Create `ai_server/.env.example`: required runtime environment variables without secrets.
- Create `ai_server/main.py`: FastAPI app entrypoint.
- Create `ai_server/app/api/schemas.py`: Spring request and response Pydantic models.
- Create `ai_server/app/api/routes.py`: `/ai/analyze` route.
- Create `ai_server/app/core/config.py`: environment-driven settings.
- Create `ai_server/app/core/llm.py`: Upstage OpenAI-compatible client wrapper and JSON helper.
- Create `ai_server/app/graph/state.py`: LangGraph state and internal typed models.
- Create `ai_server/app/graph/workflow.py`: graph construction and invocation.
- Create `ai_server/app/graph/nodes/analyze_user.py`: Agent 1, user analysis.
- Create `ai_server/app/graph/nodes/check_completeness.py`: deterministic completeness router.
- Create `ai_server/app/graph/nodes/build_query.py`: deterministic Pathsdog query builder.
- Create `ai_server/app/graph/nodes/search_jobs.py`: graph node wrapper for Pathsdog search.
- Create `ai_server/app/graph/nodes/score_jobs.py`: Agent 2, suitability scoring.
- Create `ai_server/app/graph/nodes/format_response.py`: thresholding, top 5 selection, DTO formatting.
- Create `ai_server/app/integrations/pathsdog_mcp.py`: direct remote MCP integration.
- Create prompt files in `ai_server/app/prompts/`.
- Create tests under `ai_server/tests/`.

## References

- LangGraph Python docs: use `StateGraph`, `add_node`, conditional edges, and `compile`.
- MCP Python SDK docs: use `streamablehttp_client` and `ClientSession` for remote Streamable HTTP MCP servers.
- Upstage docs: use OpenAI-compatible chat client with `base_url=https://api.upstage.ai/v1`; keep API key in `UPSTAGE_API_KEY`.

---

### Task 1: Scaffold AI Server Package and Health Endpoint

**Files:**
- Create: `ai_server/requirements.txt`
- Create: `ai_server/.env.example`
- Create: `ai_server/app/__init__.py`
- Create: `ai_server/app/api/__init__.py`
- Create: `ai_server/app/core/__init__.py`
- Create: `ai_server/app/graph/__init__.py`
- Create: `ai_server/app/graph/nodes/__init__.py`
- Create: `ai_server/app/integrations/__init__.py`
- Create: `ai_server/main.py`
- Create: `ai_server/tests/test_health.py`

- [ ] **Step 1: Create dependency file**

Write `ai_server/requirements.txt`:

```text
fastapi==0.116.1
uvicorn[standard]==0.35.0
pydantic==2.11.7
pydantic-settings==2.10.1
langgraph==0.5.4
openai==1.97.1
mcp==1.12.2
python-dotenv==1.1.1
pytest==8.4.1
pytest-asyncio==1.1.0
httpx==0.28.1
```

- [ ] **Step 2: Create environment example**

Write `ai_server/.env.example`:

```env
UPSTAGE_API_KEY=replace-with-your-upstage-api-key
UPSTAGE_BASE_URL=https://api.upstage.ai/v1
UPSTAGE_MODEL=solar-pro3
PATHSDOG_MCP_URL=https://jobs.pathsdog.com/mcp
AI_SERVER_HOST=0.0.0.0
AI_SERVER_PORT=8000
```

- [ ] **Step 3: Create package directories**

Create empty `__init__.py` files:

```text
ai_server/app/__init__.py
ai_server/app/api/__init__.py
ai_server/app/core/__init__.py
ai_server/app/graph/__init__.py
ai_server/app/graph/nodes/__init__.py
ai_server/app/integrations/__init__.py
```

- [ ] **Step 4: Write failing health test**

Write `ai_server/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from main import app


def test_health_returns_ok():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 5: Run the health test and verify it fails**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pytest tests/test_health.py -v
```

Expected: FAIL because `main.py` does not exist yet.

- [ ] **Step 6: Implement FastAPI entrypoint**

Write `ai_server/main.py`:

```python
from fastapi import FastAPI


app = FastAPI(title="Job Recommendation AI Server")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: Run the health test and verify it passes**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit scaffold**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/requirements.txt ai_server/.env.example ai_server/main.py ai_server/app ai_server/tests/test_health.py
git commit -m "feat: scaffold FastAPI AI server"
```

---

### Task 2: Add Spring-Compatible Schemas and `/ai/analyze` Route

**Files:**
- Create: `ai_server/app/api/schemas.py`
- Create: `ai_server/app/api/routes.py`
- Modify: `ai_server/main.py`
- Create: `ai_server/tests/test_analyze_route.py`

- [ ] **Step 1: Write failing route contract test**

Write `ai_server/tests/test_analyze_route.py`:

```python
from fastapi.testclient import TestClient

from main import app


def test_analyze_accepts_spring_payload_and_returns_list():
    client = TestClient(app)
    payload = {
        "coverLetter": "Spring Boot 프로젝트에서 예약 API와 Redis 캐시를 구현했습니다.",
        "preferences": {
            "jobRole": "백엔드 개발자",
            "experienceLevel": "신입",
            "techStack": ["Spring", "Redis"],
            "region": "서울",
            "onlyWithReward": False,
            "isUrgent": False,
        },
    }

    response = client.post("/ai/analyze", json=payload)

    assert response.status_code == 200
    assert response.json() == []


def test_analyze_rejects_missing_cover_letter():
    client = TestClient(app)
    payload = {
        "preferences": {
            "jobRole": "백엔드 개발자",
            "experienceLevel": "신입",
            "techStack": ["Spring"],
            "region": "서울",
            "onlyWithReward": False,
            "isUrgent": False,
        }
    }

    response = client.post("/ai/analyze", json=payload)

    assert response.status_code == 422
```

- [ ] **Step 2: Run the route test and verify it fails**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_analyze_route.py -v
```

Expected: FAIL because `/ai/analyze` is not registered.

- [ ] **Step 3: Implement schemas**

Write `ai_server/app/api/schemas.py`:

```python
from pydantic import BaseModel, Field, HttpUrl


class Preferences(BaseModel):
    jobRole: str = Field(default="")
    experienceLevel: str = Field(default="")
    techStack: list[str] = Field(default_factory=list)
    region: str = Field(default="")
    onlyWithReward: bool = False
    isUrgent: bool = False


class AnalyzeRequest(BaseModel):
    coverLetter: str = Field(min_length=1)
    preferences: Preferences = Field(default_factory=Preferences)


class Analysis(BaseModel):
    matchReason: str
    missingPoints: str
    checkpointGuide: str


class JobData(BaseModel):
    jobId: str
    companyName: str
    jobTitle: str
    suitabilityScore: float = Field(ge=0.0, le=1.0)
    compensation: str
    deadline: str
    originalLink: str | None = None
    analysis: Analysis
```

- [ ] **Step 4: Implement temporary analyze route**

Write `ai_server/app/api/routes.py`:

```python
from fastapi import APIRouter

from app.api.schemas import AnalyzeRequest, JobData


router = APIRouter()


@router.post("/ai/analyze", response_model=list[JobData])
async def analyze_jobs(request: AnalyzeRequest) -> list[JobData]:
    return []
```

Modify `ai_server/main.py`:

```python
from fastapi import FastAPI

from app.api.routes import router as api_router


app = FastAPI(title="Job Recommendation AI Server")
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5: Run route tests and verify they pass**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_analyze_route.py tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit schemas and route**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/app/api ai_server/main.py ai_server/tests/test_analyze_route.py
git commit -m "feat: add Spring-compatible analyze route"
```

---

### Task 3: Add Settings and Upstage LLM Wrapper

**Files:**
- Create: `ai_server/app/core/config.py`
- Create: `ai_server/app/core/llm.py`
- Create: `ai_server/tests/test_llm.py`

- [ ] **Step 1: Write failing config and JSON parsing tests**

Write `ai_server/tests/test_llm.py`:

```python
import pytest

from app.core.config import Settings
from app.core.llm import extract_json_object


def test_settings_defaults_use_upstage_and_pathsdog(monkeypatch):
    monkeypatch.setenv("UPSTAGE_API_KEY", "test-key")
    settings = Settings()

    assert str(settings.upstage_base_url) == "https://api.upstage.ai/v1"
    assert settings.upstage_model == "solar-pro3"
    assert str(settings.pathsdog_mcp_url) == "https://jobs.pathsdog.com/mcp"


def test_extract_json_object_handles_markdown_fence():
    text = '```json\\n{"ok": true, "count": 2}\\n```'

    assert extract_json_object(text) == {"ok": True, "count": 2}


def test_extract_json_object_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        extract_json_object("[1, 2, 3]")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_llm.py -v
```

Expected: FAIL because config and LLM modules do not exist.

- [ ] **Step 3: Implement settings**

Write `ai_server/app/core/config.py`:

```python
from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    upstage_api_key: str = Field(alias="UPSTAGE_API_KEY")
    upstage_base_url: AnyHttpUrl = Field(default="https://api.upstage.ai/v1", alias="UPSTAGE_BASE_URL")
    upstage_model: str = Field(default="solar-pro3", alias="UPSTAGE_MODEL")
    pathsdog_mcp_url: AnyHttpUrl = Field(default="https://jobs.pathsdog.com/mcp", alias="PATHSDOG_MCP_URL")
    ai_server_host: str = Field(default="0.0.0.0", alias="AI_SERVER_HOST")
    ai_server_port: int = Field(default=8000, alias="AI_SERVER_PORT")
```

- [ ] **Step 4: Implement LLM wrapper**

Write `ai_server/app/core/llm.py`:

```python
import json
from collections.abc import Sequence
from typing import Any

from openai import AsyncOpenAI

from app.core.config import Settings


def extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\\n".join(lines).strip()

    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object")
    return payload


class UpstageLLM:
    def __init__(self, settings: Settings):
        self._model = settings.upstage_model
        self._client = AsyncOpenAI(
            api_key=settings.upstage_api_key,
            base_url=str(settings.upstage_base_url),
        )

    async def complete_json(self, messages: Sequence[dict[str, str]]) -> dict[str, Any]:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=list(messages),
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        return extract_json_object(content)
```

- [ ] **Step 5: Run tests and verify they pass**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_llm.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit config and LLM wrapper**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/app/core ai_server/tests/test_llm.py
git commit -m "feat: add Upstage LLM configuration"
```

---

### Task 4: Implement User Analysis Agent and Completeness Router

**Files:**
- Create: `ai_server/app/graph/state.py`
- Create: `ai_server/app/graph/nodes/analyze_user.py`
- Create: `ai_server/app/graph/nodes/check_completeness.py`
- Create: `ai_server/app/prompts/user_analysis.md`
- Create: `ai_server/tests/test_user_analysis.py`

- [ ] **Step 1: Write failing tests**

Write `ai_server/tests/test_user_analysis.py`:

```python
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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_user_analysis.py -v
```

Expected: FAIL because graph state and nodes do not exist.

- [ ] **Step 3: Implement graph state**

Write `ai_server/app/graph/state.py`:

```python
from typing import Any, TypedDict

from app.api.schemas import AnalyzeRequest, JobData


class GraphState(TypedDict, total=False):
    request: AnalyzeRequest
    user_profile: dict[str, Any]
    search_query: dict[str, Any]
    candidate_jobs: list[dict[str, Any]]
    scored_jobs: list[dict[str, Any]]
    response_jobs: list[JobData]
```

- [ ] **Step 4: Add user analysis prompt**

Write `ai_server/app/prompts/user_analysis.md`:

```text
You are a career-analysis router for a Korean junior tech job recommendation service.

Analyze the user's self-introduction and preferences. Return only a JSON object with:
- projectExperiences: array of concrete project/work experiences
- technicalSkills: array of technical skills found in the self-introduction or preferences
- roleSignals: array of desired or implied roles
- strengths: array of concrete strengths
- jobDirection: concise target job direction
- missingInformation: array of missing information that would improve recommendation quality
- isSufficient: boolean

Set isSufficient to true only when the input has at least one concrete project/work experience,
at least one technical skill signal, and a recognizable job direction.
Do not include markdown.
```

- [ ] **Step 5: Implement analysis node**

Write `ai_server/app/graph/nodes/analyze_user.py`:

```python
from pathlib import Path
from typing import Protocol

from app.graph.state import GraphState


class JsonLLM(Protocol):
    async def complete_json(self, messages: list[dict[str, str]]) -> dict:
        ...


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "user_analysis.md"


async def analyze_user(state: GraphState, llm: JsonLLM) -> GraphState:
    request = state["request"]
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "coverLetter": request.coverLetter,
        "preferences": request.preferences.model_dump(),
    }

    profile = await llm.complete_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": str(payload)},
        ]
    )

    return {"user_profile": profile}
```

- [ ] **Step 6: Implement completeness router**

Write `ai_server/app/graph/nodes/check_completeness.py`:

```python
from app.graph.state import GraphState


def route_by_completeness(state: GraphState) -> str:
    profile = state.get("user_profile", {})
    return "build_query" if profile.get("isSufficient") is True else "format_response"
```

- [ ] **Step 7: Run tests and verify they pass**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_user_analysis.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit user analysis agent**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/app/graph ai_server/app/prompts/user_analysis.md ai_server/tests/test_user_analysis.py
git commit -m "feat: add user analysis agent"
```

---

### Task 5: Implement Query Builder and Pathsdog MCP Client

**Files:**
- Create: `ai_server/app/graph/nodes/build_query.py`
- Create: `ai_server/app/integrations/pathsdog_mcp.py`
- Create: `ai_server/app/graph/nodes/search_jobs.py`
- Create: `ai_server/tests/test_search_jobs.py`

- [ ] **Step 1: Write failing query and client tests**

Write `ai_server/tests/test_search_jobs.py`:

```python
import pytest

from app.api.schemas import AnalyzeRequest, Preferences
from app.graph.nodes.build_query import build_query
from app.graph.nodes.search_jobs import search_jobs
from app.integrations.pathsdog_mcp import select_tool_name


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


def test_select_tool_name_raises_when_missing():
    with pytest.raises(ValueError, match="No MCP tool"):
        select_tool_name(["list_companies"], ["search", "job"])


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
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_search_jobs.py -v
```

Expected: FAIL because query builder and MCP modules do not exist.

- [ ] **Step 3: Implement query builder**

Write `ai_server/app/graph/nodes/build_query.py`:

```python
from app.graph.state import GraphState


def build_query(state: GraphState) -> GraphState:
    request = state["request"]
    profile = state.get("user_profile", {})
    role = request.preferences.jobRole or profile.get("jobDirection", "")
    skills = request.preferences.techStack or profile.get("technicalSkills", [])
    keyword_parts = [role, *skills]
    keyword = " ".join(part.strip() for part in keyword_parts if part and part.strip())

    return {
        "search_query": {
            "keyword": keyword,
            "region": request.preferences.region,
            "experienceLevel": request.preferences.experienceLevel,
            "onlyWithReward": request.preferences.onlyWithReward,
            "isUrgent": request.preferences.isUrgent,
            "limit": 10,
        }
    }
```

- [ ] **Step 4: Implement Pathsdog MCP integration**

Write `ai_server/app/integrations/pathsdog_mcp.py`:

```python
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def select_tool_name(tool_names: list[str], required_terms: list[str]) -> str:
    lowered_terms = [term.lower() for term in required_terms]
    for name in tool_names:
        lowered = name.lower()
        if all(term in lowered for term in lowered_terms):
            return name
    raise ValueError(f"No MCP tool matches required terms: {required_terms}")


def _content_to_dict(result: Any) -> dict[str, Any]:
    if hasattr(result, "structuredContent") and result.structuredContent:
        return dict(result.structuredContent)
    if hasattr(result, "content") and result.content:
        first = result.content[0]
        text = getattr(first, "text", "")
        if text:
            import json

            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
            return {"items": payload}
    return {}


class PathsdogMCPClient:
    def __init__(self, url: str):
        self._url = url

    async def search_jobs(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        async with streamablehttp_client(self._url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                search_tool = select_tool_name(tool_names, ["search", "job"])
                result = await session.call_tool(search_tool, query)
                payload = _content_to_dict(result)

        items = payload.get("jobs") or payload.get("items") or payload.get("results") or []
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]
```

- [ ] **Step 5: Implement search node**

Write `ai_server/app/graph/nodes/search_jobs.py`:

```python
from typing import Protocol

from app.graph.state import GraphState


class JobSearchClient(Protocol):
    async def search_jobs(self, query: dict) -> list[dict]:
        ...


async def search_jobs(state: GraphState, client: JobSearchClient) -> GraphState:
    candidates = await client.search_jobs(state["search_query"])
    return {"candidate_jobs": candidates}
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_search_jobs.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit query and MCP client**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/app/graph/nodes/build_query.py ai_server/app/graph/nodes/search_jobs.py ai_server/app/integrations/pathsdog_mcp.py ai_server/tests/test_search_jobs.py
git commit -m "feat: add Pathsdog MCP search node"
```

---

### Task 6: Implement Suitability Agent, Filtering, and Formatting

**Files:**
- Create: `ai_server/app/graph/nodes/score_jobs.py`
- Create: `ai_server/app/graph/nodes/format_response.py`
- Create: `ai_server/app/prompts/suitability_scoring.md`
- Create: `ai_server/tests/test_scoring_and_formatting.py`

- [ ] **Step 1: Write failing scoring and formatting tests**

Write `ai_server/tests/test_scoring_and_formatting.py`:

```python
import pytest

from app.graph.nodes.format_response import format_response
from app.graph.nodes.score_jobs import score_jobs


class FakeScoringLLM:
    async def complete_json(self, messages):
        return {
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


def test_format_response_filters_and_sorts_top_five():
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
            for i, score in enumerate([0.95, 0.91, 0.88, 0.8, 0.7, 0.69], start=1)
        ]
    }

    result = format_response(state)

    jobs = result["response_jobs"]
    assert len(jobs) == 5
    assert [job.suitabilityScore for job in jobs] == [0.95, 0.91, 0.88, 0.8, 0.7]
    assert jobs[0].compensation == "원문 확인 필요"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_scoring_and_formatting.py -v
```

Expected: FAIL because scoring and formatting nodes do not exist.

- [ ] **Step 3: Add scoring prompt**

Write `ai_server/app/prompts/suitability_scoring.md`:

```text
You are a Korean career matching analyst.

Compare the analyzed user profile with candidate job postings.
Return only a JSON object with a "jobs" array.
Each job must include:
- jobId
- companyName
- jobTitle
- suitabilityScore: number from 0.0 to 1.0
- compensation
- deadline
- originalLink
- analysis.matchReason
- analysis.missingPoints
- analysis.checkpointGuide

Do not claim the user will pass or be accepted.
Frame the score as relevance between the self-introduction and the posting.
Use "원문 확인 필요" for missing compensation or deadline.
Do not include markdown.
```

- [ ] **Step 4: Implement scoring node**

Write `ai_server/app/graph/nodes/score_jobs.py`:

```python
from pathlib import Path
from typing import Protocol

from app.graph.state import GraphState


class JsonLLM(Protocol):
    async def complete_json(self, messages: list[dict[str, str]]) -> dict:
        ...


PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "suitability_scoring.md"


async def score_jobs(state: GraphState, llm: JsonLLM) -> GraphState:
    if not state.get("candidate_jobs"):
        return {"scored_jobs": []}

    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    payload = {
        "userProfile": state.get("user_profile", {}),
        "candidateJobs": state.get("candidate_jobs", []),
    }
    response = await llm.complete_json(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": str(payload)},
        ]
    )
    jobs = response.get("jobs", [])
    return {"scored_jobs": jobs if isinstance(jobs, list) else []}
```

- [ ] **Step 5: Implement formatting node**

Write `ai_server/app/graph/nodes/format_response.py`:

```python
from app.api.schemas import Analysis, JobData
from app.graph.state import GraphState


DEFAULT_TEXT = "원문 확인 필요"


def _to_job_data(raw: dict) -> JobData:
    analysis = raw.get("analysis") or {}
    return JobData(
        jobId=str(raw.get("jobId") or raw.get("id") or raw.get("originalLink") or "unknown"),
        companyName=str(raw.get("companyName") or DEFAULT_TEXT),
        jobTitle=str(raw.get("jobTitle") or DEFAULT_TEXT),
        suitabilityScore=float(raw.get("suitabilityScore") or 0.0),
        compensation=str(raw.get("compensation") or DEFAULT_TEXT),
        deadline=str(raw.get("deadline") or DEFAULT_TEXT),
        originalLink=raw.get("originalLink"),
        analysis=Analysis(
            matchReason=str(analysis.get("matchReason") or "추천 이유가 충분히 생성되지 않았습니다."),
            missingPoints=str(analysis.get("missingPoints") or "보완점 정보가 충분히 생성되지 않았습니다."),
            checkpointGuide=str(analysis.get("checkpointGuide") or "지원 전 원문 공고를 확인하세요."),
        ),
    )


def format_response(state: GraphState) -> GraphState:
    scored = state.get("scored_jobs", [])
    filtered = [
        item for item in scored
        if isinstance(item, dict) and float(item.get("suitabilityScore") or 0.0) >= 0.7
    ]
    filtered.sort(key=lambda item: float(item.get("suitabilityScore") or 0.0), reverse=True)
    return {"response_jobs": [_to_job_data(item) for item in filtered[:5]]}
```

- [ ] **Step 6: Run tests and verify they pass**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_scoring_and_formatting.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit scoring and formatting**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/app/graph/nodes/score_jobs.py ai_server/app/graph/nodes/format_response.py ai_server/app/prompts/suitability_scoring.md ai_server/tests/test_scoring_and_formatting.py
git commit -m "feat: add suitability scoring workflow nodes"
```

---

### Task 7: Wire LangGraph Workflow into FastAPI

**Files:**
- Create: `ai_server/app/graph/workflow.py`
- Modify: `ai_server/app/api/routes.py`
- Create: `ai_server/tests/test_workflow.py`

- [ ] **Step 1: Write failing workflow tests**

Write `ai_server/tests/test_workflow.py`:

```python
import pytest

from app.api.schemas import AnalyzeRequest, Preferences
from app.graph.workflow import build_workflow, run_workflow


class FakeLLM:
    def __init__(self):
        self.calls = 0

    async def complete_json(self, messages):
        self.calls += 1
        if self.calls == 1:
            return {
                "projectExperiences": ["Spring API 개발"],
                "technicalSkills": ["Spring", "Redis"],
                "roleSignals": ["백엔드 개발자"],
                "strengths": ["성능 개선"],
                "jobDirection": "백엔드 개발자",
                "missingInformation": [],
                "isSufficient": True,
            }
        return {
            "jobs": [
                {
                    "jobId": "1",
                    "companyName": "테스트회사",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 0.8,
                    "compensation": "원문 확인 필요",
                    "deadline": "원문 확인 필요",
                    "originalLink": "https://example.com/1",
                    "analysis": {
                        "matchReason": "Spring API 경험과 관련성이 높습니다.",
                        "missingPoints": "운영 경험 보완이 필요합니다.",
                        "checkpointGuide": "Redis 성능 개선 사례를 강조하세요.",
                    },
                }
            ]
        }


class FakeSearchClient:
    async def search_jobs(self, query):
        return [{"jobId": "1", "companyName": "테스트회사", "jobTitle": "백엔드 개발자"}]


@pytest.mark.asyncio
async def test_workflow_returns_job_data_list():
    request = AnalyzeRequest(
        coverLetter="Spring API와 Redis 캐시를 구현했습니다.",
        preferences=Preferences(jobRole="백엔드 개발자", techStack=["Spring", "Redis"], region="서울"),
    )
    workflow = build_workflow(FakeLLM(), FakeSearchClient())

    result = await run_workflow(workflow, request)

    assert len(result) == 1
    assert result[0].jobId == "1"
    assert result[0].suitabilityScore == 0.8
```

- [ ] **Step 2: Run workflow test and verify it fails**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_workflow.py -v
```

Expected: FAIL because workflow module does not exist.

- [ ] **Step 3: Implement workflow**

Write `ai_server/app/graph/workflow.py`:

```python
from typing import Protocol

from langgraph.graph import END, StateGraph

from app.api.schemas import AnalyzeRequest, JobData
from app.graph.nodes.analyze_user import analyze_user
from app.graph.nodes.build_query import build_query
from app.graph.nodes.check_completeness import route_by_completeness
from app.graph.nodes.format_response import format_response
from app.graph.nodes.score_jobs import score_jobs
from app.graph.nodes.search_jobs import search_jobs
from app.graph.state import GraphState


class JsonLLM(Protocol):
    async def complete_json(self, messages: list[dict[str, str]]) -> dict:
        ...


class JobSearchClient(Protocol):
    async def search_jobs(self, query: dict) -> list[dict]:
        ...


def build_workflow(llm: JsonLLM, search_client: JobSearchClient):
    graph = StateGraph(GraphState)

    async def analyze_user_node(state: GraphState) -> GraphState:
        return await analyze_user(state, llm)

    async def search_jobs_node(state: GraphState) -> GraphState:
        return await search_jobs(state, search_client)

    async def score_jobs_node(state: GraphState) -> GraphState:
        return await score_jobs(state, llm)

    graph.add_node("analyze_user", analyze_user_node)
    graph.add_node("build_query", build_query)
    graph.add_node("search_jobs", search_jobs_node)
    graph.add_node("score_jobs", score_jobs_node)
    graph.add_node("format_response", format_response)

    graph.set_entry_point("analyze_user")
    graph.add_conditional_edges(
        "analyze_user",
        route_by_completeness,
        {
            "build_query": "build_query",
            "format_response": "format_response",
        },
    )
    graph.add_edge("build_query", "search_jobs")
    graph.add_edge("search_jobs", "score_jobs")
    graph.add_edge("score_jobs", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()


async def run_workflow(workflow, request: AnalyzeRequest) -> list[JobData]:
    result = await workflow.ainvoke({"request": request})
    return result.get("response_jobs", [])
```

- [ ] **Step 4: Modify route to use real workflow**

Modify `ai_server/app/api/routes.py`:

```python
from fastapi import APIRouter, HTTPException

from app.api.schemas import AnalyzeRequest, JobData
from app.core.config import Settings
from app.core.llm import UpstageLLM
from app.graph.workflow import build_workflow, run_workflow
from app.integrations.pathsdog_mcp import PathsdogMCPClient


router = APIRouter()


@router.post("/ai/analyze", response_model=list[JobData])
async def analyze_jobs(request: AnalyzeRequest) -> list[JobData]:
    try:
        settings = Settings()
        llm = UpstageLLM(settings)
        search_client = PathsdogMCPClient(str(settings.pathsdog_mcp_url))
        workflow = build_workflow(llm, search_client)
        return await run_workflow(workflow, request)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI workflow failed") from exc
```

- [ ] **Step 5: Run workflow and existing tests**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
UPSTAGE_API_KEY=test-key .venv/bin/pytest tests/test_workflow.py tests/test_analyze_route.py tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit workflow wiring**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/app/graph/workflow.py ai_server/app/api/routes.py ai_server/tests/test_workflow.py
git commit -m "feat: wire LangGraph workflow into FastAPI"
```

---

### Task 8: Add Contract Test and Run Full Verification

**Files:**
- Create: `ai_server/tests/test_contract.py`

- [ ] **Step 1: Write contract test for Spring response shape**

Write `ai_server/tests/test_contract.py`:

```python
from app.api.schemas import Analysis, JobData


def test_job_data_serializes_to_spring_dto_shape():
    job = JobData(
        jobId="1",
        companyName="회사",
        jobTitle="백엔드 개발자",
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

- [ ] **Step 2: Run all AI server tests**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
UPSTAGE_API_KEY=test-key .venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 3: Run Spring tests to ensure existing backend still builds**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/backend/AI
./gradlew test
```

Expected: BUILD SUCCESSFUL.

- [ ] **Step 4: Start FastAPI server locally**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
test -n "$UPSTAGE_API_KEY"
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
```

Expected: Uvicorn starts on `http://0.0.0.0:8000`.

- [ ] **Step 5: Smoke test health endpoint**

In a second terminal:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status":"ok"}
```

- [ ] **Step 6: Commit contract test and verification**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/tests/test_contract.py
git commit -m "test: add AI server contract coverage"
```

---

## Self-Review Notes

- Spec coverage: The plan covers FastAPI `/ai/analyze`, two LangGraph agents, Upstage configuration, direct Pathsdog MCP integration, score thresholding, max 5 output, Spring-compatible response shape, and tests.
- Scope check: The plan excludes file uploads, PDF/DOCX parsing, frontend changes, Spring DTO changes, and AI server persistence, matching the approved spec.
- Type consistency: The request uses `coverLetter` and `preferences`; response fields match Spring `JobDataDTO` and nested `AnalysisDTO`.
- Secret handling: Upstage API key is only referenced through `UPSTAGE_API_KEY`; no key is written into files.
