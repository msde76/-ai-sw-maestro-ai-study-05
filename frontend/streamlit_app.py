import time
from typing import Any

import requests
import streamlit as st


DEFAULT_BACKEND_URL = "http://localhost:8080"
POLL_INTERVAL_SECONDS = 2
MAX_WAIT_SECONDS = 60
FINISHED_STATUSES = {"COMPLETED", "EMPTY", "ERROR"}


st.set_page_config(
    page_title="자기소개서 기반 채용공고 추천",
    page_icon="💼",
    layout="wide",
)

st.markdown(
    """
    <style>
    .profile-card-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
        margin-top: 1rem;
    }
    .profile-card {
        min-height: 150px;
        height: 100%;
        border: 1px solid rgba(49, 51, 63, 0.18);
        border-radius: 12px;
        padding: 1.15rem 1.25rem;
        background: #ffffff;
        display: flex;
        flex-direction: column;
        gap: 0.85rem;
    }
    .profile-card-title {
        font-weight: 700;
        font-size: 1.05rem;
        color: #31333f;
    }
    .profile-card-body {
        color: #31333f;
        line-height: 1.55;
    }
    .stButton > button, .stLinkButton > a {
        background: #f6f7f9 !important;
        color: #31333f !important;
        border: 1px solid rgba(49, 51, 63, 0.18) !important;
        box-shadow: none !important;
    }
    .stButton > button:hover, .stLinkButton > a:hover {
        background: #eceff3 !important;
        color: #111827 !important;
        border-color: rgba(49, 51, 63, 0.28) !important;
    }
    [data-baseweb="tag"] {
        background-color: #d7dde5 !important;
        color: #1f2937 !important;
    }
    [data-baseweb="tag"] span {
        color: #1f2937 !important;
    }
    [data-baseweb="tag"] svg {
        fill: #374151 !important;
    }
    @media (max-width: 1100px) {
        .profile-card-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 700px) {
        .profile-card-grid { grid-template-columns: 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


SAMPLE_COVER_LETTER = """저는 Spring Boot 기반 백엔드 개발자로 성장하고 싶은 신입 개발자입니다.
팀 프로젝트에서 예약/결제 기능을 담당하며 REST API를 설계했고, MySQL 인덱스와 Redis 캐시를 적용해 반복 조회 API 응답 시간을 약 1.8초에서 0.4초로 개선했습니다.
AWS EC2와 Docker로 서비스를 배포했고, GitHub Actions를 이용해 테스트와 배포 과정을 자동화했습니다.
프로젝트 중 프론트엔드 팀원과 API 명세가 자주 어긋나는 문제가 있어 Swagger 문서와 에러 코드 규칙을 정리했고, 이슈 템플릿을 만들어 협업 속도를 높였습니다.
아직 대규모 트래픽 운영 경험은 부족하지만, 장애 로그를 읽고 원인을 좁혀가는 과정과 성능 개선 실험을 좋아합니다."""


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def join_optional(values: list[str]) -> str:
    return ", ".join(value for value in values if value != "상관없음")


def unwrap_response(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status", "ERROR"),
        "message": payload.get("message", "응답 메시지가 없습니다."),
        "data": payload.get("data"),
    }


def create_task(backend_url: str, request_body: dict[str, Any]) -> str:
    response = requests.post(
        f"{backend_url.rstrip('/')}/jobs/recommend/tasks",
        json=request_body,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload["data"]["taskId"]


def poll_task(backend_url: str, task_id: str) -> dict[str, Any]:
    response = requests.get(
        f"{backend_url.rstrip('/')}/jobs/recommend/tasks/{task_id}",
        timeout=30,
    )
    response.raise_for_status()
    return unwrap_response(response.json())


def render_job_card(job: dict[str, Any], rank: int) -> None:
    analysis = job.get("analysis") or {}
    score = job.get("suitabilityScore")
    score_text = f"{score:.0%}" if isinstance(score, int | float) else "점수 없음"

    with st.container(border=True):
        left, right = st.columns([4, 1])
        with left:
            st.subheader(f"{rank}. {job.get('companyName', '회사명 없음')} · {job.get('jobTitle', '직무명 없음')}")
            st.caption(f"마감: {job.get('deadline', '원문 확인 필요')} · 보상: {job.get('compensation', '원문 확인 필요')}")
        with right:
            st.metric("적합도", score_text)

        st.markdown("**공고 요약**")
        st.caption(job.get("sourceSnapshot", "공고 요약 정보가 없습니다."))

        st.markdown("**추천 이유**")
        st.write(analysis.get("matchReason", "추천 이유가 없습니다."))

        st.markdown("**보완할 점**")
        st.write(analysis.get("missingPoints", "보완점 정보가 없습니다."))

        st.markdown("**지원 전 강조 포인트**")
        st.write(analysis.get("checkpointGuide", "지원 전략 정보가 없습니다."))

        original_link = job.get("originalLink")
        if original_link:
            st.link_button("원문 공고 열기", original_link)


def render_result(result: dict[str, Any]) -> None:
    status = result.get("status")
    message = result.get("message")
    jobs = result.get("data") or []

    if status == "COMPLETED":
        st.success(message)
        st.markdown("### 추천 공고")
        for index, job in enumerate(jobs, start=1):
            render_job_card(job, index)
    elif status == "EMPTY":
        st.warning(message)
    elif status == "ERROR":
        st.error(message)
    else:
        st.info(message or "처리 중입니다.")


st.title("자기소개서 기반 채용공고 추천")
st.caption("자기소개서와 희망 조건에 맞는 채용공고를 추천합니다.")

backend_url = DEFAULT_BACKEND_URL

st.markdown("#### 1. 자기소개서 입력")
cover_letter = st.text_area("자기소개서", value=SAMPLE_COVER_LETTER, height=420)

st.markdown("#### 2. 희망 조건")

col1, col2 = st.columns(2)
with col1:
    job_role = st.text_input("희망 직무", "백엔드 개발자")
    experience_levels = st.multiselect("경력 수준", ["신입", "인턴", "경력"], default=["신입"])
with col2:
    region = st.text_input("희망 근무지", "서울, 판교, 해외 가능")
    tech_stack = st.text_input("기술 스택", "Spring, Redis, AWS")

submitted = st.button("공고 추천 받기", use_container_width=True)

if submitted:
    if not cover_letter.strip():
        st.error("자기소개서를 입력해주세요.")
        st.stop()

    request_body = {
        "coverLetter": cover_letter,
        "preferences": {
            "jobRole": job_role,
            "experienceLevel": join_optional(experience_levels),
            "techStack": split_csv(tech_stack),
            "region": region.strip(),
            "onlyWithReward": False,
            "isUrgent": False,
        },
    }

    try:
        task_id = create_task(backend_url, request_body)
        st.info("추천 결과를 준비하고 있습니다.")

        deadline = time.time() + MAX_WAIT_SECONDS
        status_area = st.empty()
        progress = st.progress(0)
        result = None

        while time.time() < deadline:
            result = poll_task(backend_url, task_id)
            elapsed_ratio = 1 - max(deadline - time.time(), 0) / MAX_WAIT_SECONDS
            progress.progress(min(elapsed_ratio, 1.0))
            status_area.info("자기소개서와 채용공고를 비교하고 있습니다.")

            if result.get("status") in FINISHED_STATUSES:
                break

            time.sleep(POLL_INTERVAL_SECONDS)

        progress.empty()
        status_area.empty()

        if result is None:
            st.error("추천 결과를 가져오지 못했습니다.")
        elif result.get("status") in FINISHED_STATUSES:
            render_result(result)
        else:
            st.warning("추천 결과 준비가 예상보다 오래 걸리고 있습니다. 잠시 후 다시 시도해주세요.")
            st.json(result)
    except requests.RequestException as exc:
        st.error("추천 서버와 연결하지 못했습니다. 잠시 후 다시 시도해주세요.")
        st.code(str(exc))
    except (KeyError, TypeError) as exc:
        st.error("추천 결과 형식이 예상과 다릅니다.")
        st.code(str(exc))
