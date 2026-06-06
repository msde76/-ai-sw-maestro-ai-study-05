# Full Job Description Design

## Goal

Add `jobIntroduction` to the final job recommendation response so the Spring server can receive a human-readable job introduction for each recommended posting.

The field should be populated only for the final recommended jobs, up to 5 items. The feature should not fetch full descriptions for every `candidate_jobs` item returned by `search_jobs`.

## Current State

The FastAPI AI server receives `AnalyzeRequest`, runs a LangGraph workflow, and returns `list[JobData]` from `POST /ai/analyze`.

Current workflow:

```text
analyze_user
  -> build_query
  -> search_jobs
  -> score_jobs
  -> format_response
```

`search_jobs` calls Pathsdog MCP `search_jobs`. In the observed response, Pathsdog returns raw text in `content[0].text`, not `structuredContent`. The AI server parses that raw text with regex into `candidate_jobs`.

The search response includes fields such as:

```json
{
  "jobId": "639",
  "companyName": "김캐디",
  "jobTitle": "백엔드 개발자 포지션 (신입~3년차, 병특)",
  "sourceSnapshot": "[ID:639] 김캐디 - 백엔드 개발자 포지션...",
  "skills": ["Java", "Spring Boot", "Backend"],
  "experience": "신입~3년차",
  "location": "김캐디 본사",
  "deadline": "상시채용",
  "originalLink": "https://kimcaddie.career.greetinghr.com/ko/o/206177"
}
```

This is not enough for `jobIntroduction`. Pathsdog MCP `get_job_detail` with `include_full_description=true` returns a raw text detail response containing `[요약]` and `[상세 내용]`. `[상세 내용]` is the best source for `jobIntroduction`; `[요약]` is the fallback.

## Proposed Architecture

Add a post-scoring enrichment step:

```text
analyze_user
  -> build_query
  -> search_jobs
  -> score_jobs
  -> enrich_job_details
  -> format_response
```

`enrich_job_details` will:

1. Read `scored_jobs`.
2. Select the same final recommendation candidates that `format_response` would return, using a shared helper so ranking rules do not drift:
   - Include jobs with `suitabilityScore >= 0.7` first.
   - Backfill with jobs where `0.0 < suitabilityScore < 0.7`.
   - Sort each group by score descending.
   - Keep at most 5.
3. For each selected job, call Pathsdog MCP `get_job_detail` with:

```json
{
  "job_id": 639,
  "include_full_description": true
}
```

4. Extract `jobIntroduction` from the raw detail text:
   - Prefer text after `[상세 내용]`.
   - If `[상세 내용]` is missing or empty, use text after `[요약]`.
   - If both are missing, fall back to `sourceSnapshot` when available.
   - If no usable text exists, use `"원문 확인 필요"`.
5. Store enriched selected jobs in a new state field, `enriched_jobs`.

`format_response` will prefer `enriched_jobs` when present and convert them to `JobData`.

The existing score filtering and sorting logic should be moved into a small reusable helper, for example `select_response_jobs(raw_jobs)`, used by both `enrich_job_details` and `format_response`.

## DTO Changes

FastAPI `JobData` adds:

```python
jobIntroduction: str
```

Spring `JobResponseDTO.JobDataDTO` adds:

```java
private String jobIntroduction;
```

This is a response field. The existing Spring request DTO (`JobRequestDTO.TaskInfoDTO`) does not need this field because Spring sends the cover letter and preferences to the AI server; the AI server returns `jobIntroduction`.

If downstream naming calls the object received from FastAPI a "request DTO" from Spring's perspective, the concrete code change is still the same: add the field to the DTO class that deserializes AI server job recommendation results.

## MCP Client Changes

Extend `PathsdogMCPClient` with:

```python
async def get_job_detail(self, job_id: str | int, *, include_full_description: bool = True) -> str:
    ...
```

The method should:

1. Open a streamable HTTP MCP session.
2. Select or call the `get_job_detail` tool.
3. Pass numeric `job_id` and `include_full_description`.
4. Return the raw text from `content[0].text`.
5. Raise `PathsdogMCPError` if the tool reports `isError` or returns no consumable text.

Keep search parsing and detail parsing separate. Search returns `list[dict]`; detail returns raw text that is parsed into a single introduction string.

## Detail Parsing

Create small parser helpers that are easy to test:

```text
extract_job_introduction(detail_text)
  -> extract section "[상세 내용]"
  -> else extract section "[요약]"
  -> else ""
```

Section extraction should stop at the next bracket section such as `[기본 정보]`, `[일정]`, `[혜택/복지]`, `[요약]`, or at `원본:` when appropriate.

Do not use an LLM for detail parsing. This should be deterministic string parsing.

## Error Handling

The recommendation response should not fail just because one detail lookup fails.

For each selected job:

1. If `get_job_detail` succeeds and an introduction is parsed, use it.
2. If lookup or parsing fails, set `jobIntroduction` from `sourceSnapshot` if present.
3. If no snapshot exists, set `jobIntroduction` to `"원문 확인 필요"`.

Existing workflow-level failures for user analysis, search, and scoring remain unchanged.

## Data Flow

```text
search_jobs
  -> candidate_jobs: list[dict]

score_jobs
  -> scored_jobs: list[dict]

enrich_job_details
  -> selected top max 5 scored jobs
  -> get_job_detail(jobId, include_full_description=true)
  -> jobIntroduction added per selected job
  -> enriched_jobs: list[dict]

format_response
  -> response_jobs: list[JobData]
```

Final response example:

```json
[
  {
    "jobId": "639",
    "companyName": "김캐디",
    "jobTitle": "백엔드 개발자 포지션 (신입~3년차, 병특)",
    "jobIntroduction": "회사 소개 및 포지션 상세\n\n- 김캐디는 골프를 더 쉽고 편리하게 즐길 수 있도록 돕는 골프 플랫폼입니다...",
    "suitabilityScore": 0.94,
    "compensation": "원문 확인 필요",
    "deadline": "상시채용",
    "originalLink": "https://kimcaddie.career.greetinghr.com/ko/o/206177",
    "analysis": {
      "matchReason": "Java, Spring Boot 등 핵심 기술 스택과 역할이 일치합니다.",
      "missingPoints": "프로젝트 규모와 운영 경험은 추가 확인이 필요합니다.",
      "checkpointGuide": "Spring Boot, Redis, AWS 관련 경험을 정리하세요."
    }
  }
]
```

## Testing Plan

Add or update FastAPI tests:

1. `PathsdogMCPClient` detail parser extracts `[상세 내용]`.
2. Detail parser falls back to `[요약]`.
3. Detail parser returns empty text when no known section exists.
4. `enrich_job_details` calls detail lookup only for max 5 final selected jobs.
5. `enrich_job_details` falls back to `sourceSnapshot` when detail lookup fails.
6. `format_response` includes `jobIntroduction` in `JobData`.
7. Contract test confirms `JobData.model_dump()` includes `jobIntroduction`.
8. Workflow test confirms final response contains `jobIntroduction`.

Add or update Spring tests if existing coverage supports it. At minimum, compile should verify `JobResponseDTO.JobDataDTO` accepts the new field through Jackson/Lombok.

## Non-Goals

- Do not fetch full descriptions for every `candidate_jobs` item.
- Do not use an LLM to parse Pathsdog detail raw text.
- Do not change Spring request DTO shape unless a separate UI/API workflow needs to send this field.
- Do not expose raw `sourceSnapshot` as a public response field.
- Do not alter the scoring threshold or ranking rules.

## Open Decisions Resolved

- Detail lookup scope: final recommended jobs only, maximum 5.
- `jobIntroduction` source: prefer `get_job_detail(include_full_description=true)` `[상세 내용]`, then `[요약]`, then `sourceSnapshot`, then `"원문 확인 필요"`.
- Failure policy: per-job fallback, not whole-request failure.
