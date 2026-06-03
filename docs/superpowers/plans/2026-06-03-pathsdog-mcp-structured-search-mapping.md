# Pathsdog MCP Structured Search Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `build_query.py` generate Pathsdog MCP `search_jobs` arguments using structured fields, with Spring preferences first and cover-letter analysis as fallback or enrichment.

**Architecture:** Keep the MCP client and graph wiring unchanged. Replace the query-building heuristics with deterministic helpers that select source signals, map roles into Pathsdog skill tokens, reserve `query` for distinctive domain keywords, and strip empty values before returning `search_query`.

**Tech Stack:** Python 3.13, Pydantic v2 request models, LangGraph state dicts, pytest.

---

## File Structure

- Modify: `ai_server/app/graph/nodes/build_query.py`
  - Owns deterministic conversion from `AnalyzeRequest` plus `user_profile` into Pathsdog MCP `search_jobs` arguments.
  - Will contain focused helpers for role text collection, role-to-skill mapping, domain keyword extraction, skill normalization, experience mapping, and empty-value cleanup.
- Modify: `ai_server/tests/test_search_jobs.py`
  - Owns unit coverage for the query builder and existing MCP parsing/search-node behavior.
  - Existing MCP client parsing tests remain unchanged.

No new production files are needed. `ai_server/app/integrations/pathsdog_mcp.py` and `ai_server/app/graph/nodes/search_jobs.py` already accept and forward a query dict, so their behavior does not change.

---

### Task 1: Lock Structured Mapping Behavior With Tests

**Files:**
- Modify: `ai_server/tests/test_search_jobs.py`

- [ ] **Step 1: Replace the current query-builder tests**

In `ai_server/tests/test_search_jobs.py`, replace `test_build_query_combines_profile_and_preferences` and `test_build_query_keeps_pathsdog_search_broad_for_many_skills` with these tests:

```python
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
    assert result["search_query"]["limit"] == 10
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
    assert result["search_query"]["limit"] == 10


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
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_search_jobs.py::test_build_query_maps_generic_role_to_skills_not_query tests/test_search_jobs.py::test_build_query_uses_preferences_before_conflicting_profile tests/test_search_jobs.py::test_build_query_falls_back_to_profile_skills_and_roles tests/test_search_jobs.py::test_build_query_keeps_distinctive_domain_keyword_in_query -v
```

Expected: FAIL. The current implementation still places generic role terms in `query`, limits skills to two values, and does not add role-derived skill tokens.

- [ ] **Step 3: Commit the failing tests**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/tests/test_search_jobs.py
git commit -m "test: lock Pathsdog structured search mapping"
```

---

### Task 2: Implement Structured Pathsdog Query Mapping

**Files:**
- Modify: `ai_server/app/graph/nodes/build_query.py`
- Test: `ai_server/tests/test_search_jobs.py`

- [ ] **Step 1: Replace `build_query.py` with structured mapping helpers**

Replace the full contents of `ai_server/app/graph/nodes/build_query.py` with:

```python
from collections.abc import Iterable

from app.graph.state import GraphState


ROLE_SKILL_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("백엔드", "서버"), "Backend"),
    (("프론트엔드", "프론트"), "Frontend"),
    (("풀스택",), "Fullstack"),
    (("ios",), "iOS"),
    (("android",), "Android"),
    (("devops", "인프라"), "DevOps"),
    (("데이터",), "Data Analysis"),
    (("ai", "머신러닝", "ml"), "AI"),
)

DOMAIN_KEYWORDS: tuple[tuple[str, str], ...] = (
    (("sre",), "SRE"),
    (("머신러닝",), "머신러닝"),
    (("게임서버",), "게임서버"),
    (("llm",), "LLM"),
    (("보안",), "보안"),
    (("qa",), "QA"),
)


def build_query(state: GraphState) -> GraphState:
    request = state["request"]
    profile = state.get("user_profile", {})

    role_texts = _role_texts(request.preferences.jobRole, profile)
    skills = _skills_with_role_tokens(
        request.preferences.techStack or profile.get("technicalSkills", []),
        role_texts,
    )
    query = _domain_query(role_texts)

    search_query = {
        "query": query,
        "skills": skills,
        "experience_filter": _experience_filter(request.preferences.experienceLevel),
        "has_compensation": request.preferences.onlyWithReward,
        "urgency": "closing_soon" if request.preferences.isUrgent else "all",
        "status": "active",
        "limit": 10,
    }
    return {"search_query": _without_empty_values(search_query)}


def _role_texts(preferred_role: str, profile: dict) -> list[str]:
    if preferred_role.strip():
        return [preferred_role.strip()]

    texts: list[str] = []
    job_direction = str(profile.get("jobDirection", "")).strip()
    if job_direction:
        texts.append(job_direction)

    role_signals = profile.get("roleSignals", [])
    if isinstance(role_signals, list):
        texts.extend(str(signal).strip() for signal in role_signals if str(signal).strip())

    return texts


def _skills_with_role_tokens(base_skills: Iterable[str], role_texts: list[str]) -> list[str]:
    skills = _unique_texts(base_skills)
    for role_skill in _role_skills(role_texts):
        if not _contains_case_insensitive(skills, role_skill):
            skills.append(role_skill)
    return skills


def _role_skills(role_texts: list[str]) -> list[str]:
    matched: list[str] = []
    joined_text = " ".join(role_texts).lower()
    for needles, skill in ROLE_SKILL_RULES:
        if any(needle in joined_text for needle in needles) and not _contains_case_insensitive(matched, skill):
            matched.append(skill)
    return matched


def _domain_query(role_texts: list[str]) -> str:
    joined_text = " ".join(role_texts).lower()
    matches: list[str] = []
    for needles, keyword in DOMAIN_KEYWORDS:
        if any(needle in joined_text for needle in needles):
            matches.append(keyword)
        if len(matches) >= 2:
            break
    return " ".join(matches)


def _experience_filter(experience_level: str) -> str:
    for value in ["인턴", "신입", "주니어", "미들", "시니어"]:
        if value in experience_level:
            return value
    return ""


def _unique_texts(values: Iterable[str]) -> list[str]:
    unique: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and not _contains_case_insensitive(unique, text):
            unique.append(text)
    return unique


def _contains_case_insensitive(values: list[str], target: str) -> bool:
    lowered_target = target.lower()
    return any(value.lower() == lowered_target for value in values)


def _without_empty_values(search_query: dict) -> dict:
    return {key: value for key, value in search_query.items() if value not in ("", [], None)}
```

- [ ] **Step 2: Run the focused query-builder tests**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_search_jobs.py::test_build_query_maps_generic_role_to_skills_not_query tests/test_search_jobs.py::test_build_query_uses_preferences_before_conflicting_profile tests/test_search_jobs.py::test_build_query_falls_back_to_profile_skills_and_roles tests/test_search_jobs.py::test_build_query_keeps_distinctive_domain_keyword_in_query -v
```

Expected: PASS.

- [ ] **Step 3: Run all search job tests**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_search_jobs.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit the implementation**

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/app/graph/nodes/build_query.py
git commit -m "feat: map Pathsdog search arguments structurally"
```

---

### Task 3: Verify Workflow Compatibility

**Files:**
- Test: `ai_server/tests/test_workflow.py`
- Test: `ai_server/tests/test_analyze_route.py`
- Test: `ai_server/tests/test_search_jobs.py`

- [ ] **Step 1: Run workflow and route tests that exercise the query path**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest tests/test_search_jobs.py tests/test_workflow.py tests/test_analyze_route.py -v
```

Expected: PASS. If a test fails because it asserted the old `query` behavior, update that test to assert the new structured mapping from this plan.

- [ ] **Step 2: Run the full AI server test suite**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05/ai_server
.venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 3: Inspect the final diff**

Run:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git diff --stat HEAD
git diff HEAD -- ai_server/app/graph/nodes/build_query.py ai_server/tests/test_search_jobs.py
```

Expected: The diff is limited to query-builder implementation and search-query tests.

- [ ] **Step 4: Commit any compatibility-only test updates**

If Step 1 required test-only updates outside `tests/test_search_jobs.py`, commit them:

```bash
cd /Users/kanghyoseung/Documents/aisw_maestro_05
git add ai_server/tests/test_workflow.py ai_server/tests/test_analyze_route.py
git commit -m "test: align workflow expectations with structured search"
```

If Step 1 did not require additional test updates, do not create this commit.

---

## Self-Review

- Spec coverage: The plan covers preference priority, cover-letter fallback, role-to-skill mapping, domain-only `query`, region omission, empty-value cleanup, and tests.
- Completion scan: No incomplete markers or unspecified implementation steps remain.
- Type consistency: The plan uses existing `AnalyzeRequest`, `Preferences`, `GraphState`, `build_query`, and `search_query` names. The MCP client remains unchanged because it already accepts `dict[str, Any]` arguments.
