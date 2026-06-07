# 채용공고 상세 소개 보강 설계

## 목표

최종 추천 채용공고 응답에 `jobIntroduction` 필드를 추가한다. 이 필드는 Spring 서버가 AI 서버의 추천 결과를 받을 때 각 공고의 소개/상세 내용을 함께 표시하기 위한 응답 필드다.

`jobIntroduction`은 최종 추천된 공고에만 채운다. 현재 응답 정책상 최종 추천은 최대 5개이므로, Pathsdog MCP 상세 조회도 최대 5개 공고에 대해서만 수행한다. `search_jobs`가 반환한 전체 `candidate_jobs`에 대해 상세 조회를 수행하지 않는다.

## 현재 구조

FastAPI AI 서버는 `POST /ai/analyze`에서 `AnalyzeRequest`를 받고 LangGraph 워크플로우를 실행한 뒤 `list[JobData]`를 반환한다.

현재 워크플로우는 아래 순서다.

```text
analyze_user
  -> build_query
  -> search_jobs
  -> score_jobs
  -> format_response
```

`search_jobs` 노드는 Pathsdog MCP의 `search_jobs` 도구를 호출한다. 실제 확인 결과, MCP 검색 응답은 `structuredContent`가 아니라 `content[0].text`의 raw text로 내려온다. AI 서버는 이 raw text를 LLM 없이 정규식으로 파싱해서 `candidate_jobs`를 만든다.

검색 결과에서 파싱되는 `candidate_jobs` 예시는 아래와 같다.

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

이 검색 결과만으로는 `jobIntroduction`을 충분히 채우기 어렵다. 검색 응답의 `sourceSnapshot`은 검색 결과 블록을 보존한 짧은 스냅샷이며, 공고 소개나 상세 본문으로 쓰기에는 부족하다.

Pathsdog MCP의 `get_job_detail` 도구를 `include_full_description=true`로 호출하면 raw text 상세 응답에 `[요약]`과 `[상세 내용]` 섹션이 포함된다. `jobIntroduction`에는 `[상세 내용]`을 우선 사용하고, 없으면 `[요약]`을 사용한다.

## 제안 구조

`score_jobs` 이후, `format_response` 이전에 상세 보강 노드를 추가한다.

```text
analyze_user
  -> build_query
  -> search_jobs
  -> score_jobs
  -> enrich_job_details
  -> format_response
```

`enrich_job_details` 노드는 다음 일을 한다.

1. `scored_jobs`를 읽는다.
2. 최종 응답 대상 공고를 최대 5개까지 선별한다.
   - `suitabilityScore >= 0.7` 공고를 우선한다.
   - 5개보다 적으면 `0.0 < suitabilityScore < 0.7` 공고를 점수순으로 보충한다.
   - 각 그룹은 점수 내림차순으로 정렬한다.
   - 최대 5개만 유지한다.
3. 선별된 각 공고의 `jobId`로 Pathsdog MCP `get_job_detail`을 호출한다.

```json
{
  "job_id": 639,
  "include_full_description": true
}
```

4. 상세 raw text에서 `jobIntroduction`을 추출한다.
   - `[상세 내용]` 섹션을 우선 사용한다.
   - `[상세 내용]`이 없거나 비어 있으면 `[요약]` 섹션을 사용한다.
   - 둘 다 없으면 `sourceSnapshot`을 fallback으로 사용한다.
   - 사용할 수 있는 값이 없으면 `"원문 확인 필요"`를 사용한다.
5. `jobIntroduction`이 추가된 공고 목록을 `enriched_jobs`에 저장한다.

`format_response`는 `enriched_jobs`가 있으면 이를 우선 사용해 `JobData`로 변환한다.

점수 필터링과 정렬 규칙은 `enrich_job_details`와 `format_response`에서 중복 구현하지 않는다. 예를 들어 `select_response_jobs(raw_jobs)` 같은 작은 공통 helper를 두고 두 노드가 같은 기준을 사용하도록 한다. 이렇게 해야 최종 추천 선별 기준이 두 곳에서 달라지는 문제를 막을 수 있다.

## DTO 변경

FastAPI 응답 DTO인 `JobData`에 아래 필드를 추가한다.

```python
jobIntroduction: str
```

Spring 서버에서 AI 서버 응답을 역직렬화하는 `JobResponseDTO.JobDataDTO`에도 아래 필드를 추가한다.

```java
private String jobIntroduction;
```

이 필드는 Spring이 AI 서버로 보내는 요청 필드가 아니다. Spring 요청 DTO인 `JobRequestDTO.TaskInfoDTO`는 기존처럼 `coverLetter`와 `preferences`를 보낸다. `jobIntroduction`은 AI 서버가 추천 결과를 만들면서 채워서 Spring으로 반환하는 응답 필드다.

만약 downstream 코드에서 "Spring에서 받는 요청 DTO"라는 표현을 쓰더라도, 실제 코드 변경 대상은 AI 서버 응답을 받는 DTO인 `JobResponseDTO.JobDataDTO`다.

## MCP 클라이언트 변경

`PathsdogMCPClient`에 상세 조회 메서드를 추가한다.

```python
async def get_job_detail(self, job_id: str | int, *, include_full_description: bool = True) -> str:
    ...
```

메서드 책임은 아래와 같다.

1. streamable HTTP MCP 세션을 연다.
2. `get_job_detail` 도구를 호출한다.
3. `job_id`는 숫자로 전달하고, `include_full_description`을 함께 전달한다.
4. 응답의 `content[0].text` raw text를 반환한다.
5. MCP 도구가 `isError`를 반환하거나 소비 가능한 text가 없으면 `PathsdogMCPError`를 발생시킨다.

검색 파싱과 상세 파싱은 분리한다. 검색은 `list[dict]`를 반환하고, 상세 조회는 raw text를 반환한 뒤 별도 parser가 하나의 `jobIntroduction` 문자열로 바꾼다.

## 상세 내용 파싱

상세 내용 파싱은 LLM을 사용하지 않고 결정적인 문자열 파싱으로 처리한다.

권장 helper 구조:

```text
extract_job_introduction(detail_text)
  -> "[상세 내용]" 섹션 추출
  -> 없으면 "[요약]" 섹션 추출
  -> 없으면 빈 문자열 반환
```

섹션 추출은 다음 섹션 헤더나 `원본:` 앞에서 멈춘다. 예를 들어 `[기본 정보]`, `[일정]`, `[혜택/복지]`, `[요약]`, `[상세 내용]` 같은 bracket 섹션이 다음에 나오면 그 직전까지만 추출한다.

## 실패 처리

상세 조회 실패 때문에 전체 추천 응답을 실패시키지 않는다.

각 최종 추천 공고마다 아래 순서로 처리한다.

1. `get_job_detail`이 성공하고 소개문 파싱도 성공하면 해당 값을 `jobIntroduction`으로 사용한다.
2. 상세 조회 또는 파싱이 실패하면 `sourceSnapshot`이 있을 때 이를 `jobIntroduction`으로 사용한다.
3. `sourceSnapshot`도 없으면 `"원문 확인 필요"`를 사용한다.

기존의 사용자 분석, 검색, 점수화 단계 실패 정책은 변경하지 않는다.

## 데이터 흐름

```text
search_jobs
  -> candidate_jobs: list[dict]

score_jobs
  -> scored_jobs: list[dict]

enrich_job_details
  -> scored_jobs 중 최종 응답 대상 최대 5개 선별
  -> get_job_detail(jobId, include_full_description=true)
  -> 각 공고에 jobIntroduction 추가
  -> enriched_jobs: list[dict]

format_response
  -> response_jobs: list[JobData]
```

최종 응답 예시는 아래와 같다.

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

## 테스트 계획

FastAPI 쪽 테스트를 추가하거나 수정한다.

1. 상세 parser가 `[상세 내용]` 섹션을 추출하는지 검증한다.
2. `[상세 내용]`이 없을 때 `[요약]`으로 fallback하는지 검증한다.
3. 알려진 섹션이 없으면 빈 문자열을 반환하는지 검증한다.
4. `enrich_job_details`가 최종 응답 대상 최대 5개에 대해서만 상세 조회를 호출하는지 검증한다.
5. 상세 조회 실패 시 `sourceSnapshot`으로 fallback하는지 검증한다.
6. `format_response`가 `JobData`에 `jobIntroduction`을 포함하는지 검증한다.
7. contract test에서 `JobData.model_dump()`에 `jobIntroduction`이 포함되는지 검증한다.
8. workflow test에서 최종 응답에 `jobIntroduction`이 포함되는지 검증한다.

Spring 쪽은 최소한 컴파일로 `JobResponseDTO.JobDataDTO`가 새 필드를 받을 수 있음을 확인한다. 기존 테스트 구조가 적합하면 Jackson 역직렬화 테스트를 추가한다.

## 범위에서 제외하는 것

- 전체 `candidate_jobs`에 대해 상세 조회하지 않는다.
- Pathsdog 상세 raw text 파싱에 LLM을 사용하지 않는다.
- 별도 요구가 생기기 전까지 Spring 요청 DTO 형태는 변경하지 않는다.
- raw `sourceSnapshot` 필드를 최종 public 응답 필드로 노출하지 않는다.
- 기존 점수 threshold나 추천 정렬 규칙을 변경하지 않는다.

## 확정된 결정사항

- 상세 조회 범위는 최종 추천 공고 최대 5개로 제한한다.
- `jobIntroduction`은 `[상세 내용]`, `[요약]`, `sourceSnapshot`, `"원문 확인 필요"` 순서로 채운다.
- 상세 조회 실패는 공고별 fallback으로 처리하며, 전체 요청 실패로 만들지 않는다.
