import pytest

from app.api.schemas import AnalyzeRequest, Preferences
from app.graph.workflow import build_workflow, run_workflow


class FakeLLM:
    def __init__(self):
        self.calls = 0

    async def complete_json(self, messages, *, json_schema=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "projectExperiences": ["예약 API 개발"],
                "technicalSkills": ["Spring", "Redis"],
                "roleSignals": ["백엔드 개발자"],
                "strengths": ["API 성능 개선"],
                "jobDirection": "백엔드 개발자",
                "missingInformation": [],
                "isSufficient": True,
            }
        return {
            "jobs": [
                {
                    "jobId": "1",
                    "companyName": "테스트컴퍼니",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 0.8,
                    "compensation": "원문 확인 필요",
                    "deadline": "상시",
                    "originalLink": "https://example.com/jobs/1",
                    "analysis": {
                        "matchReason": "Spring API 경험이 공고와 잘 맞습니다.",
                        "missingPoints": "클라우드 운영 경험 보강이 필요합니다.",
                        "checkpointGuide": "지원 전 요구 기술을 확인하세요.",
                    },
                }
            ]
        }


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
                "originalLink": "https://example.com/jobs/1",
            }
        ]

    async def get_job_detail(self, job_id, include_full_description=True):
        self.detail_calls.append((job_id, include_full_description))
        return "[상세 내용] 테스트컴퍼니 백엔드 포지션 상세 소개입니다."


class InsufficientInfoLLM:
    def __init__(self):
        self.calls = 0

    async def complete_json(self, messages, *, json_schema=None):
        self.calls += 1
        return {
            "projectExperiences": [],
            "technicalSkills": [],
            "roleSignals": [],
            "strengths": [],
            "jobDirection": "",
            "missingInformation": ["프로젝트 경험"],
            "isSufficient": False,
        }


class TrackingSearchClient:
    def __init__(self):
        self.calls = 0
        self.detail_calls = []

    async def search_jobs(self, query):
        self.calls += 1
        return []

    async def get_job_detail(self, job_id, include_full_description=True):
        self.detail_calls.append((job_id, include_full_description))
        return ""


class ReadmeExampleLLM:
    def __init__(self):
        self.calls = 0

    async def complete_json(self, messages, *, json_schema=None):
        self.calls += 1
        if self.calls == 1:
            return {
                "projectExperiences": [
                    "REST API 설계",
                    "JPA 엔티티 관계 설계",
                    "Redis 캐시 적용",
                    "AWS EC2 배포",
                ],
                "technicalSkills": ["Java", "Spring Boot", "JPA", "MySQL", "Redis", "Docker", "AWS"],
                "roleSignals": ["백엔드 개발자"],
                "strengths": ["API 성능 개선", "테스트 작성", "배포 경험"],
                "jobDirection": "백엔드 개발자",
                "missingInformation": [],
                "isSufficient": True,
            }
        return {
            "jobs": [
                _scored_job("529", "토스", "Server Developer [병역특례] (Product)", 0.98),
                _scored_job("530", "토스", "Server Developer (Product)", 0.97),
                _scored_job("531", "토스인컴", "Server Developer (Product)", 0.96),
                _scored_job("639", "김캐디", "백엔드 개발자 포지션 (신입~3년차, 병특)", 0.94),
                _scored_job("1606", "HYBE", "[Weverse Company] Back-end (경력 무관)", 0.92),
                _scored_job("1548", "두잇", "[전문연구요원] Software Engineer(신규, 전직)", 0.6),
            ]
        }


class ReadmeExampleSearchClient:
    def __init__(self):
        self.search_queries = []
        self.detail_calls = []

    async def search_jobs(self, query):
        self.search_queries.append(query)
        return [
            {
                "jobId": "639",
                "companyName": "김캐디",
                "jobTitle": "백엔드 개발자 포지션 (신입~3년차, 병특)",
                "skills": ["Java", "Kotlin", "Spring Boot", "Spring", "JPA", "Backend"],
                "experience": "신입~3년차",
                "location": "김캐디 본사",
                "deadline": "상시채용",
                "sourceSnapshot": "[ID:639] 김캐디 - 백엔드 개발자 포지션 (신입~3년차, 병특)",
                "originalLink": "https://kimcaddie.career.greetinghr.com/ko/o/206177",
            },
            {
                "jobId": "1548",
                "companyName": "두잇",
                "jobTitle": "[전문연구요원] Software Engineer(신규, 전직)",
                "skills": ["Backend", "Frontend", "Java", "Spring", "Kotlin", "React"],
                "sourceSnapshot": "[ID:1548] 두잇 - [전문연구요원] Software Engineer(신규, 전직)",
                "originalLink": "https://teamdoeat.career.greetinghr.com/ko/o/127704",
            },
            {
                "jobId": "529",
                "companyName": "토스",
                "jobTitle": "Server Developer [병역특례] (Product)",
                "skills": ["Kotlin", "Java", "Spring Boot", "Backend"],
                "sourceSnapshot": "[ID:529] 토스 - Server Developer [병역특례] (Product)",
                "originalLink": "https://toss.im/career/job-detail?job_id=4773428003",
            },
            {
                "jobId": "530",
                "companyName": "토스",
                "jobTitle": "Server Developer (Product)",
                "skills": ["Kotlin", "Java", "Spring Boot", "Backend"],
                "sourceSnapshot": "[ID:530] 토스 - Server Developer (Product)",
                "originalLink": "https://toss.im/career/job-detail?job_id=4071141003",
            },
            {
                "jobId": "531",
                "companyName": "토스인컴",
                "jobTitle": "Server Developer (Product)",
                "skills": ["Kotlin", "Java", "Spring Boot", "Backend"],
                "sourceSnapshot": "[ID:531] 토스인컴 - Server Developer (Product)",
                "originalLink": "https://toss.im/career/job-detail?job_id=4071141003&sub_position_id=6027071003",
            },
            {
                "jobId": "1606",
                "companyName": "HYBE",
                "jobTitle": "[Weverse Company] Back-end (경력 무관)",
                "skills": ["Backend", "Java", "Spring", "Kotlin", "Kafka", "Redis"],
                "sourceSnapshot": "[ID:1606] HYBE - [Weverse Company] Back-end (경력 무관)",
                "originalLink": "https://careers.hybecorp.com/ko/o/210534",
            },
        ]

    async def get_job_detail(self, job_id, include_full_description=True):
        self.detail_calls.append((job_id, include_full_description))
        return {
            "529": "[상세 내용]\n토스 제품 조직의 서버 개발자는 사용자 경험을 안정적으로 뒷받침하는 제품 서버를 설계하고 운영합니다.\n원본: https://toss.im",
            "530": "[상세 내용]\n토스의 Product Server Developer는 제품 문제를 빠르게 발견하고 서버 시스템으로 해결합니다.\n원본: https://toss.im",
            "531": "[상세 내용]\n토스인컴 서버 개발자는 보험과 금융 사용자 경험을 위한 백엔드 시스템을 만듭니다.\n원본: https://toss.im",
            "639": "[요약]\n김캐디 팀이 다루는 서비스 전 분야의 백엔드 시스템을 설계하고 개발합니다.\n[상세 내용]\n회사 소개 및 포지션 상세\n\n- 김캐디는 골프를 더 쉽고 편리하게 즐길 수 있도록 돕는 골프 플랫폼입니다.\n\n주요업무\n\n김캐디 팀이 다루는 서비스 전 분야의 백엔드 시스템을 설계하고 개발합니다.\n원본: https://kimcaddie.career.greetinghr.com/ko/o/206177",
            "1606": "[상세 내용]\nWeverse Company의 Back-end 포지션은 글로벌 팬덤 플랫폼의 대규모 트래픽을 처리하는 서버 시스템을 개발합니다.\n원본: https://careers.hybecorp.com/ko/o/210534",
        }[str(job_id)]


def _scored_job(job_id, company_name, job_title, score):
    return {
        "jobId": job_id,
        "companyName": company_name,
        "jobTitle": job_title,
        "suitabilityScore": score,
        "compensation": "원문 확인 필요",
        "deadline": "상시채용",
        "originalLink": f"https://example.com/jobs/{job_id}",
        "analysis": {
            "matchReason": "README 예시 자기소개서와 백엔드 기술 스택 관련성이 높습니다.",
            "missingPoints": "프로젝트 규모와 운영 경험은 추가 확인이 필요합니다.",
            "checkpointGuide": "Spring Boot, Redis, AWS 경험을 구체적으로 정리하세요.",
        },
    }


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


@pytest.mark.asyncio
async def test_workflow_returns_empty_without_search_when_profile_is_insufficient():
    request = AnalyzeRequest(
        coverLetter="프로젝트 경험을 더 정리해야 합니다.",
        preferences=Preferences(
            jobRole="백엔드 개발자",
            experienceLevel="신입",
            techStack=["Spring", "Redis"],
            region="서울",
            onlyWithReward=False,
            isUrgent=False,
        ),
    )
    llm = InsufficientInfoLLM()
    search_client = TrackingSearchClient()
    workflow = build_workflow(llm, search_client)

    jobs = await run_workflow(workflow, request)

    assert jobs == []
    assert llm.calls == 1
    assert search_client.calls == 0
    assert search_client.detail_calls == []


@pytest.mark.asyncio
async def test_readme_example_workflow_returns_detailed_job_introductions():
    request = AnalyzeRequest(
        coverLetter=(
            "저는 Java와 Spring Boot를 중심으로 웹 서비스 백엔드 개발을 학습하고 프로젝트를 진행해 온 "
            "신입 백엔드 개발자입니다. 팀 프로젝트에서 REST API 설계, JWT 인증, 일정 CRUD, 댓글, "
            "알림 API를 담당했습니다. JPA로 엔티티 관계를 설계했고 MySQL 인덱스를 적용해 목록 조회 "
            "API의 응답 속도를 개선했습니다. Redis를 활용해 조회수 중복 집계와 캐시를 적용했고 "
            "Docker Compose로 Spring Boot, MySQL, Redis 로컬 개발 환경을 구성했습니다. AWS EC2에 "
            "애플리케이션을 배포하고 Nginx를 리버스 프록시로 설정했습니다. GitHub Pull Request 기반 "
            "코드 리뷰와 이슈 관리로 협업했으며, Service 단위 테스트와 Controller MockMvc 테스트를 작성했습니다."
        ),
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
            onlyWithReward=False,
            isUrgent=False,
        ),
    )
    search_client = ReadmeExampleSearchClient()
    workflow = build_workflow(ReadmeExampleLLM(), search_client)

    jobs = await run_workflow(workflow, request)

    assert search_client.search_queries == [
        {
            "skills": ["Java", "Spring Boot", "Backend"],
            "experience_filter": "신입",
            "has_compensation": False,
            "urgency": "all",
            "status": "active",
            "limit": 20,
        }
    ]
    assert [job.jobId for job in jobs] == ["529", "530", "531", "639", "1606"]
    assert search_client.detail_calls == [
        ("529", True),
        ("530", True),
        ("531", True),
        ("639", True),
        ("1606", True),
    ]
    assert len(jobs) == 5
    assert all(job.jobIntroduction for job in jobs)
    assert jobs[0].jobIntroduction == "토스 제품 조직의 서버 개발자는 사용자 경험을 안정적으로 뒷받침하는 제품 서버를 설계하고 운영합니다."
    assert jobs[3].jobIntroduction.startswith("회사 소개 및 포지션 상세")
    assert "[상세 내용]" not in jobs[3].jobIntroduction
