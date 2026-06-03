# Pathsdog MCP 구조화 검색 매핑 설계

## 목표

LangGraph의 채용공고 검색 쿼리 생성 로직을 Pathsdog MCP `search_jobs` 도구 스펙에 맞게 수정한다. 검색 파라미터는 Spring에서 전달된 명시적 선호조건을 우선하고, 자소서 분석 결과는 비어 있는 검색 신호를 채우거나 보완하는 용도로 사용한다.

## 현재 동작

현재 워크플로우는 자소서를 분석해 `user_profile`에 `technicalSkills`, `roleSignals`, `jobDirection` 등을 저장한다. 이후 `build_query.py`가 `search_query` 딕셔너리를 만들고, `search_jobs.py`가 이 값을 Pathsdog MCP 클라이언트에 그대로 전달한다.

현재 쿼리 생성 로직은 일부 구조화되어 있지만, `백엔드` 같은 역할 표현을 `query`에 넣는 문제가 있다. Pathsdog MCP의 `search_jobs` 설명에 따르면 역할과 경력 수준은 전용 필드에 매핑하는 것이 좋고, `query`는 `SRE`, `머신러닝`, `게임서버`처럼 포지션이나 도메인을 구분하는 고유 키워드에만 사용하는 것이 적합하다.

## 우선순위 정책

명시적 사용자 선호조건을 먼저 사용하고, 자소서 분석 결과는 fallback 또는 보완 정보로 사용한다.

- `preferences.techStack`을 `skills`의 1차 소스로 사용한다.
- `preferences.techStack`이 비어 있으면 `user_profile.technicalSkills`를 사용한다.
- `preferences.jobRole`을 역할 매핑의 1차 소스로 사용한다.
- `preferences.jobRole`이 비어 있으면 `user_profile.jobDirection`과 `user_profile.roleSignals`를 사용한다.
- `preferences.experienceLevel`은 `experience_filter`로 매핑한다.
- `preferences.onlyWithReward`는 `has_compensation`으로 매핑한다.
- `preferences.isUrgent`는 `urgency`로 매핑한다.
- `preferences.region`은 현재 MCP 스키마에 구조화된 위치 필드가 없으므로 `search_jobs` 인자에 포함하지 않는다.

## 매핑 규칙

`skills`에는 명시적 기술스택과 역할에서 유추한 Pathsdog 기술/역할 토큰을 함께 넣는다.

역할 매핑 예시는 다음과 같다.

- `백엔드`, `서버` -> `Backend`
- `프론트엔드`, `프론트` -> `Frontend`
- `풀스택` -> `Fullstack`
- `iOS` -> `iOS`
- `Android` -> `Android`
- `DevOps`, `인프라` -> `DevOps`
- `데이터` -> `Data Analysis`
- `AI`, `머신러닝`, `ML` -> `AI`

`query`는 일반적인 역할 표현에는 사용하지 않는다. 역할 또는 자소서 분석 결과에서 Pathsdog 키워드 검색에 적합한 고유 도메인 키워드가 발견될 때만 사용한다.

`query`에 남길 수 있는 키워드는 다음과 같다.

- `SRE`
- `머신러닝`
- `게임서버`
- `LLM`
- `보안`
- `QA`

`build_query`는 최종 `search_query`를 반환하기 전에 빈 문자열, 빈 리스트, `None` 값을 제거한다.

## 데이터 흐름

1. FastAPI가 Spring의 `AnalyzeRequest`를 받는다.
2. `analyze_user`가 `coverLetter`와 `preferences`를 바탕으로 `user_profile`을 추출한다.
3. `build_query`가 우선순위 정책에 따라 `preferences`와 `user_profile`을 병합한다.
4. `search_jobs`가 생성된 딕셔너리를 `PathsdogMCPClient.search_jobs`에 그대로 전달한다.
5. `PathsdogMCPClient`가 이 딕셔너리를 MCP `search_jobs` 도구의 arguments로 전달한다.

## 예시

백엔드 선호조건이 명시된 경우:

```python
preferences = {
    "jobRole": "백엔드 개발자",
    "experienceLevel": "신입",
    "techStack": ["Java", "Spring Boot", "JPA"],
}
```

기대 MCP 인자:

```python
{
    "skills": ["Java", "Spring Boot", "JPA", "Backend"],
    "experience_filter": "신입",
    "urgency": "all",
    "status": "active",
    "limit": 10,
}
```

SRE 선호조건이 명시된 경우:

```python
preferences = {
    "jobRole": "SRE 엔지니어",
    "techStack": ["Kubernetes", "AWS"],
}
```

기대 MCP 인자:

```python
{
    "query": "SRE",
    "skills": ["Kubernetes", "AWS"],
    "urgency": "all",
    "status": "active",
    "limit": 10,
}
```

선호조건이 비어 있어 자소서 분석 결과를 사용하는 경우:

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

기대 MCP 인자:

```python
{
    "query": "LLM",
    "skills": ["Python", "LLM", "AI", "Backend"],
    "urgency": "all",
    "status": "active",
    "limit": 10,
}
```

## 오류 처리

매핑 로직은 결정적이어야 하며, 예상하지 못한 역할 문자열이 들어와도 예외를 발생시키지 않는다. 알 수 없는 역할은 역할 기반 `skills` 보강에서 제외하되, 사용자가 명시한 기술스택은 그대로 보존한다. 최종 쿼리에서는 빈 문자열, 빈 리스트, `None` 값을 제거한다.

## 테스트 계획

`ai_server/tests/test_search_jobs.py`를 수정해 다음을 검증한다.

- `preferences`가 있으면 충돌하는 `user_profile` 값보다 우선한다.
- `preferences.techStack`이 비어 있으면 `user_profile.technicalSkills`로 보완한다.
- 백엔드 같은 일반 역할은 `query`가 아니라 `skills`로 매핑한다.
- SRE 같은 고유 도메인 키워드는 `query`로 매핑한다.
- `region`은 MCP 인자에 포함하지 않는다.
- 기존 MCP 클라이언트 파싱 테스트와 검색 노드 테스트가 계속 통과한다.

## 범위

이번 변경 범위는 검색 쿼리 생성 로직과 관련 테스트로 제한한다. Spring DTO, FastAPI 요청 스키마, Pathsdog MCP 클라이언트 전송 방식, 점수화 프롬프트, 응답 DTO는 변경하지 않는다.
