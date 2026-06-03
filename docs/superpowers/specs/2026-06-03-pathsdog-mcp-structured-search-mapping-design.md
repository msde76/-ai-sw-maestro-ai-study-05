# Pathsdog MCP Structured Search Mapping Design

## Goal

Update the LangGraph job-search query builder so it sends Pathsdog `search_jobs` arguments in the structured form expected by the MCP tool. The mapping should prioritize explicit Spring `preferences` and use cover-letter analysis only to fill or enrich missing search signals.

## Current Behavior

The workflow already analyzes the cover letter and stores a `user_profile` with `technicalSkills`, `roleSignals`, and `jobDirection`. `build_query.py` then creates a `search_query` dict and `search_jobs.py` passes it directly to the Pathsdog MCP client.

The current query builder is partially structured, but it still places role terms such as `백엔드` into `query`. Pathsdog's tool description says role and career-level terms should usually be mapped to dedicated fields, while `query` should be reserved for distinctive position or domain keywords such as `SRE`, `머신러닝`, or `게임서버`.

## Priority Policy

Use explicit user preferences first, then cover-letter analysis as fallback or enrichment:

- `preferences.techStack` is the primary source for `skills`.
- If `preferences.techStack` is empty, use `user_profile.technicalSkills`.
- `preferences.jobRole` is the primary source for role mapping.
- If `preferences.jobRole` is empty, use `user_profile.jobDirection` and `user_profile.roleSignals`.
- `preferences.experienceLevel` maps to `experience_filter`.
- `preferences.onlyWithReward` maps to `has_compensation`.
- `preferences.isUrgent` maps to `urgency`.
- `preferences.region` is not sent to `search_jobs` because the current MCP schema does not expose a structured location field.

## Mapping Rules

`skills` should include normalized technical stack values plus role-derived Pathsdog skill tokens when useful.

Role mapping examples:

- `백엔드`, `서버` -> `Backend`
- `프론트엔드`, `프론트` -> `Frontend`
- `풀스택` -> `Fullstack`
- `iOS` -> `iOS`
- `Android` -> `Android`
- `DevOps`, `인프라` -> `DevOps`
- `데이터` -> `Data Analysis`
- `AI`, `머신러닝`, `ML` -> `AI`

`query` should be omitted for generic role terms. It should be set only when the role or analyzed profile contains distinctive domain keywords that Pathsdog recommends for keyword search:

- `SRE`
- `머신러닝`
- `게임서버`
- `LLM`
- `보안`
- `QA`

The query builder should remove empty values before returning `search_query`.

## Data Flow

1. FastAPI receives Spring's `AnalyzeRequest`.
2. `analyze_user` extracts `user_profile` from `coverLetter` and `preferences`.
3. `build_query` merges `preferences` and `user_profile` using the priority policy.
4. `search_jobs` passes the resulting dict directly to `PathsdogMCPClient.search_jobs`.
5. `PathsdogMCPClient` calls the MCP `search_jobs` tool with that dict as tool arguments.

## Examples

Backend preference:

```python
preferences = {
    "jobRole": "백엔드 개발자",
    "experienceLevel": "신입",
    "techStack": ["Java", "Spring Boot", "JPA"],
}
```

Expected MCP arguments:

```python
{
    "skills": ["Java", "Spring Boot", "JPA", "Backend"],
    "experience_filter": "신입",
    "urgency": "all",
    "status": "active",
    "limit": 10,
}
```

SRE preference:

```python
preferences = {
    "jobRole": "SRE 엔지니어",
    "techStack": ["Kubernetes", "AWS"],
}
```

Expected MCP arguments:

```python
{
    "query": "SRE",
    "skills": ["Kubernetes", "AWS"],
    "urgency": "all",
    "status": "active",
    "limit": 10,
}
```

Cover-letter fallback:

```python
preferences = {
    "jobRole": "",
    "techStack": [],
}
user_profile = {
    "technicalSkills": ["Python", "LLM"],
    "jobDirection": "AI 백엔드 엔지니어",
    "roleSignals": ["LLM 서비스 개발"],
}
```

Expected MCP arguments:

```python
{
    "query": "LLM",
    "skills": ["Python", "LLM", "AI", "Backend"],
    "urgency": "all",
    "status": "active",
    "limit": 10,
}
```

## Error Handling

The mapping layer should stay deterministic and should not raise errors for unusual text. Unknown roles remain ignored for role-derived skills, while explicit technical skills are preserved. Empty strings, empty lists, and `None` values are removed from the final query.

## Testing

Update `ai_server/tests/test_search_jobs.py` to cover:

- Preferences override conflicting `user_profile` values.
- Empty `preferences.techStack` falls back to `user_profile.technicalSkills`.
- Generic roles such as backend map to `skills`, not `query`.
- Distinctive domains such as SRE map to `query`.
- `region` is not included in MCP arguments.
- Existing MCP client parsing and search-node tests still pass.

## Scope

This change is limited to query construction and related tests. It does not change the Spring DTO, FastAPI request schema, Pathsdog MCP client transport, scoring prompt, or response DTO.
