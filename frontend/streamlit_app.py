import time
from typing import Any

import requests
import streamlit as st


DEFAULT_BACKEND_URL = "http://localhost:8080"
POLL_INTERVAL_SECONDS = 2
MAX_WAIT_SECONDS = 60
FINISHED_STATUSES = {"COMPLETED", "EMPTY", "ERROR"}
PROCESSING_MESSAGES = [
    "자기소개서 핵심 역량을 추출하고 있습니다.",
    "희망 조건과 공고를 교차 비교하고 있습니다.",
    "추천 사유와 보완 포인트를 정리하고 있습니다.",
]


st.set_page_config(
    page_title="자기소개서 기반 채용공고 추천",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --paper: #f4efe6;
        --sand: #e5d4b8;
        --ink: #1f2933;
        --muted: #52606d;
        --accent: #ad6c34;
        --accent-deep: #7c4823;
        --card: rgba(255, 252, 247, 0.92);
        --line: rgba(73, 52, 33, 0.14);
    }
    .stApp {
        background:
            radial-gradient(circle at top left, rgba(173, 108, 52, 0.18), transparent 28%),
            radial-gradient(circle at top right, rgba(74, 124, 89, 0.12), transparent 24%),
            linear-gradient(180deg, #f9f5ee 0%, #f3ebdf 52%, #efe4d3 100%);
        color: var(--ink);
    }
    .block-container {
        padding-top: 2.2rem;
        padding-bottom: 3rem;
        max-width: 1200px;
    }
    .hero-panel {
        border: 1px solid var(--line);
        background:
            linear-gradient(135deg, rgba(255, 248, 238, 0.96), rgba(245, 234, 215, 0.9)),
            #fff;
        border-radius: 28px;
        padding: 1.45rem 1.6rem;
        margin-bottom: 1rem;
        box-shadow: 0 20px 50px rgba(79, 57, 36, 0.08);
    }
    .hero-kicker {
        display: inline-block;
        padding: 0.35rem 0.75rem;
        border-radius: 999px;
        background: rgba(173, 108, 52, 0.1);
        color: var(--accent-deep);
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin-bottom: 0.85rem;
    }
    .hero-title {
        font-size: 2rem;
        line-height: 1.12;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 0.55rem;
        color: #1f2933;
    }
    .hero-copy {
        max-width: 620px;
        color: var(--muted);
        line-height: 1.55;
        font-size: 0.98rem;
    }
    .hero-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.85fr);
        gap: 1rem;
        align-items: center;
    }
    .hero-mini-grid {
        display: grid;
        gap: 0.7rem;
    }
    .hero-mini-card {
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 0.9rem 1rem;
        background: rgba(255, 252, 247, 0.72);
    }
    .hero-mini-label {
        font-size: 0.78rem;
        color: var(--muted);
        margin-bottom: 0.25rem;
    }
    .hero-mini-copy {
        color: var(--ink);
        font-size: 0.92rem;
        line-height: 1.45;
    }
    .insight-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.9rem;
        margin: 1rem 0 1.4rem;
    }
    .insight-card {
        border: 1px solid var(--line);
        border-radius: 18px;
        background: var(--card);
        padding: 1rem 1rem 0.9rem;
    }
    .insight-label {
        color: var(--muted);
        font-size: 0.85rem;
        margin-bottom: 0.35rem;
    }
    .insight-value {
        color: var(--ink);
        font-size: 1.2rem;
        font-weight: 700;
    }
    .section-panel {
        border: 1px solid var(--line);
        background: rgba(255, 252, 247, 0.78);
        border-radius: 24px;
        padding: 1.1rem;
        height: 100%;
        box-shadow: 0 14px 36px rgba(79, 57, 36, 0.05);
    }
    .panel-title {
        font-size: 1.1rem;
        font-weight: 800;
        margin-bottom: 0.3rem;
        color: #222f3e;
    }
    .panel-copy {
        color: var(--muted);
        font-size: 0.93rem;
        line-height: 1.45;
        margin-bottom: 0.75rem;
    }
    .summary-strip {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin: 0.7rem 0 0.95rem;
    }
    .summary-pill {
        display: inline-flex;
        align-items: center;
        padding: 0.45rem 0.7rem;
        border-radius: 999px;
        background: #f3e4cf;
        color: #6d3f1c;
        font-size: 0.84rem;
        font-weight: 700;
    }
    .form-note {
        border-radius: 16px;
        border: 1px solid var(--line);
        background: rgba(255, 252, 247, 0.72);
        padding: 0.8rem 0.95rem;
        margin-top: 0.75rem;
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.45;
    }
    .result-shell {
        margin-top: 1.25rem;
    }
    .result-toolbar {
        border: 1px solid var(--line);
        background: rgba(255, 251, 245, 0.88);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        margin-bottom: 1rem;
    }
    .job-card {
        border: 1px solid var(--line);
        background: rgba(255, 252, 247, 0.9);
        border-radius: 22px;
        padding: 1.2rem 1.2rem 1rem;
        box-shadow: 0 18px 40px rgba(79, 57, 36, 0.06);
        margin-bottom: 0.95rem;
    }
    .job-card-top {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        align-items: flex-start;
        margin-bottom: 0.9rem;
    }
    .job-rank {
        display: inline-block;
        min-width: 2.2rem;
        height: 2.2rem;
        line-height: 2.2rem;
        border-radius: 999px;
        text-align: center;
        font-weight: 800;
        color: white;
        background: linear-gradient(135deg, var(--accent), var(--accent-deep));
        margin-right: 0.75rem;
    }
    .job-heading {
        font-size: 1.2rem;
        font-weight: 800;
        color: #1f2933;
    }
    .job-meta {
        color: var(--muted);
        font-size: 0.93rem;
        margin-top: 0.3rem;
    }
    .score-pill {
        padding: 0.55rem 0.85rem;
        border-radius: 999px;
        background: rgba(173, 108, 52, 0.12);
        color: var(--accent-deep);
        font-weight: 800;
        white-space: nowrap;
    }
    .detail-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.9rem;
        margin-top: 0.9rem;
    }
    .detail-box {
        border: 1px solid var(--line);
        border-radius: 16px;
        background: rgba(255, 255, 255, 0.55);
        padding: 0.85rem 0.9rem;
    }
    .detail-label {
        font-size: 0.82rem;
        color: var(--muted);
        margin-bottom: 0.35rem;
    }
    .detail-copy {
        color: var(--ink);
        line-height: 1.6;
        font-size: 0.94rem;
    }
    .empty-state {
        border: 1px dashed rgba(73, 52, 33, 0.25);
        border-radius: 18px;
        padding: 1.2rem;
        color: var(--muted);
        background: rgba(255, 255, 255, 0.42);
    }
    .stButton > button, .stDownloadButton > button, .stLinkButton > a {
        border-radius: 14px !important;
        border: 1px solid rgba(73, 52, 33, 0.16) !important;
        background: linear-gradient(180deg, #fffaf3 0%, #f5e7d4 100%) !important;
        color: #2d3748 !important;
        font-weight: 700 !important;
        box-shadow: none !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {
        border-color: rgba(73, 52, 33, 0.28) !important;
        background: linear-gradient(180deg, #fdf3e4 0%, #efd7b9 100%) !important;
        color: #1a202c !important;
    }
    div[data-testid="stButton"] > button[kind="primary"] {
        background: linear-gradient(135deg, #a95f24 0%, #7b3f19 100%) !important;
        color: #fffaf4 !important;
        border: none !important;
        min-height: 3.2rem !important;
        box-shadow: 0 14px 30px rgba(123, 63, 25, 0.24) !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #934d1b 0%, #673113 100%) !important;
        color: #fffaf4 !important;
    }
    [data-baseweb="tag"] {
        background-color: #efe1cd !important;
        color: #59381d !important;
    }
    [data-baseweb="tag"] span {
        color: #59381d !important;
    }
    [data-baseweb="tag"] svg {
        fill: #59381d !important;
    }
    @media (max-width: 1000px) {
        .hero-grid,
        .insight-grid, .detail-grid { grid-template-columns: 1fr; }
        .job-card-top { flex-direction: column; }
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


def format_score(score: Any) -> str:
    if isinstance(score, (int, float)):
        if score <= 1:
            return f"{score:.0%}"
        return f"{score:.0f}점"
    return "점수 없음"


def score_to_ratio(score: Any) -> float:
    if isinstance(score, (int, float)):
        return score if score <= 1 else score / 100
    return 0.0


def summarize_preferences(request_body: dict[str, Any]) -> tuple[str, str, str]:
    preferences = request_body["preferences"]
    experience = preferences["experienceLevel"] or "미지정"
    stack = ", ".join(preferences["techStack"][:3]) if preferences["techStack"] else "미지정"
    region = preferences["region"] or "미지정"
    return experience, stack, region


def get_result_metrics(jobs: list[dict[str, Any]]) -> tuple[str, str, str]:
    if not jobs:
        return "0건", "-", "-"

    scored_jobs = [score_to_ratio(job.get("suitabilityScore")) for job in jobs if isinstance(job.get("suitabilityScore"), (int, float))]
    avg_score = f"{(sum(scored_jobs) / len(scored_jobs)):.0%}" if scored_jobs else "-"
    top_company = jobs[0].get("companyName", "회사명 없음")
    return f"{len(jobs)}건", avg_score, top_company


def filter_jobs(
    jobs: list[dict[str, Any]],
    min_score: float,
    keyword: str,
    only_with_links: bool,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    search_term = keyword.strip().lower()

    for job in jobs:
        score_ratio = score_to_ratio(job.get("suitabilityScore"))
        if score_ratio < min_score:
            continue

        if only_with_links and not job.get("originalLink"):
            continue

        if search_term:
            haystack = " ".join(
                str(value)
                for value in [
                    job.get("companyName", ""),
                    job.get("jobTitle", ""),
                    job.get("compensation", ""),
                    (job.get("analysis") or {}).get("matchReason", ""),
                ]
            ).lower()
            if search_term not in haystack:
                continue

        filtered.append(job)

    return filtered


def render_hero() -> None:
    st.markdown(
        """
        <section class="hero-panel">
            <div class="hero-grid">
                <div>
                    <div class="hero-kicker">AI Hiring Match</div>
                    <div class="hero-title">자기소개서에서 바로<br/>지원 우선순위를 뽑아냅니다.</div>
                    <div class="hero-copy">
                        입력한 자기소개서와 희망 조건을 바탕으로 공고 적합도, 추천 이유, 보완 포인트를 한 화면에서 정리합니다.
                    </div>
                </div>
                <div class="hero-mini-grid">
                    <div class="hero-mini-card">
                        <div class="hero-mini-label">무엇이 보이나요</div>
                        <div class="hero-mini-copy">공고 적합도, 추천 이유, 보완 포인트를 바로 비교합니다.</div>
                    </div>
                    <div class="hero-mini-card">
                        <div class="hero-mini-label">어떻게 쓰나요</div>
                        <div class="hero-mini-copy">조건을 입력하고 추천을 받아 우선 지원할 공고부터 빠르게 추립니다.</div>
                    </div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_request_insights(request_body: dict[str, Any], cover_letter: str) -> None:
    experience, stack, region = summarize_preferences(request_body)
    st.markdown(
        f"""
        <div class="insight-grid">
            <div class="insight-card">
                <div class="insight-label">자기소개서 분량</div>
                <div class="insight-value">{len(cover_letter.strip())}자</div>
            </div>
            <div class="insight-card">
                <div class="insight-label">희망 경력 / 기술</div>
                <div class="insight-value">{experience} / {stack}</div>
            </div>
            <div class="insight-card">
                <div class="insight-label">희망 근무지</div>
                <div class="insight-value">{region}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_preference_pills(job_role: str, experience_levels: list[str], region: str, tech_stack: str) -> None:
    experience_text = ", ".join(experience_levels) if experience_levels else "미지정"
    tech_items = split_csv(tech_stack)
    stack_text = ", ".join(tech_items[:3]) if tech_items else "미지정"
    st.markdown(
        f"""
        <div class="summary-strip">
            <span class="summary-pill">{job_role.strip() or "직무 미지정"}</span>
            <span class="summary-pill">{experience_text}</span>
            <span class="summary-pill">{region.strip() or "근무지 미지정"}</span>
            <span class="summary-pill">{stack_text}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_job_card(job: dict[str, Any], rank: int) -> None:
    analysis = job.get("analysis") or {}
    score_text = format_score(job.get("suitabilityScore"))
    source_snapshot = job.get("sourceSnapshot", "공고 요약 정보가 없습니다.")

    st.markdown(
        f"""
        <div class="job-card">
            <div class="job-card-top">
                <div>
                    <div class="job-heading"><span class="job-rank">{rank}</span>{job.get("companyName", "회사명 없음")} · {job.get("jobTitle", "직무명 없음")}</div>
                    <div class="job-meta">마감: {job.get("deadline", "원문 확인 필요")} · 보상: {job.get("compensation", "원문 확인 필요")}</div>
                </div>
                <div class="score-pill">적합도 {score_text}</div>
            </div>
            <div class="detail-grid">
                <div class="detail-box">
                    <div class="detail-label">추천 이유</div>
                    <div class="detail-copy">{analysis.get("matchReason", "추천 이유가 없습니다.")}</div>
                </div>
                <div class="detail-box">
                    <div class="detail-label">보완할 점</div>
                    <div class="detail-copy">{analysis.get("missingPoints", "보완점 정보가 없습니다.")}</div>
                </div>
                <div class="detail-box">
                    <div class="detail-label">지원 전 강조 포인트</div>
                    <div class="detail-copy">{analysis.get("checkpointGuide", "지원 전략 정보가 없습니다.")}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("공고 요약 보기"):
        st.write(source_snapshot)

    if job.get("originalLink"):
        st.link_button("원문 공고 열기", job["originalLink"], use_container_width=True)


def render_result(result: dict[str, Any]) -> None:
    status = result.get("status")
    message = result.get("message")
    jobs = result.get("data") or []

    if status == "COMPLETED":
        total_jobs, avg_score, top_company = get_result_metrics(jobs)
        st.success(message)
        st.markdown(
            f"""
            <div class="result-shell">
                <div class="insight-grid">
                    <div class="insight-card">
                        <div class="insight-label">추천 공고 수</div>
                        <div class="insight-value">{total_jobs}</div>
                    </div>
                    <div class="insight-card">
                        <div class="insight-label">평균 적합도</div>
                        <div class="insight-value">{avg_score}</div>
                    </div>
                    <div class="insight-card">
                        <div class="insight-label">1순위 기업</div>
                        <div class="insight-value">{top_company}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        toolbar_left, toolbar_mid, toolbar_right = st.columns([1.2, 1.5, 1])
        with toolbar_left:
            min_score = st.slider("최소 적합도", min_value=0.0, max_value=1.0, value=0.0, step=0.05, format="%.0f%%")
        with toolbar_mid:
            search_keyword = st.text_input("결과 내 검색", placeholder="회사명, 직무명, 추천 이유")
        with toolbar_right:
            only_with_links = st.toggle("링크 있는 공고만", value=False)

        filtered_jobs = filter_jobs(jobs, min_score, search_keyword, only_with_links)
        st.caption(f"현재 {len(filtered_jobs)}건의 공고를 표시하고 있습니다.")

        if not filtered_jobs:
            st.markdown('<div class="empty-state">현재 필터 조건에 맞는 추천 공고가 없습니다. 최소 적합도를 낮추거나 검색어를 비워보세요.</div>', unsafe_allow_html=True)
            return

        for index, job in enumerate(filtered_jobs, start=1):
            render_job_card(job, index)
    elif status == "EMPTY":
        st.warning(message)
        st.markdown('<div class="empty-state">조건에 맞는 공고를 찾지 못했습니다. 기술 스택이나 근무지 조건을 조금 더 넓혀보는 편이 좋습니다.</div>', unsafe_allow_html=True)
    elif status == "ERROR":
        st.error(message)
    else:
        st.info(message or "처리 중입니다.")


if "latest_result" not in st.session_state:
    st.session_state.latest_result = None
if "latest_request_body" not in st.session_state:
    st.session_state.latest_request_body = None
if "latest_cover_letter" not in st.session_state:
    st.session_state.latest_cover_letter = SAMPLE_COVER_LETTER


render_hero()

backend_url = DEFAULT_BACKEND_URL
max_wait_seconds = MAX_WAIT_SECONDS
poll_interval = POLL_INTERVAL_SECONDS

with st.sidebar:
    st.markdown("### 실행 설정")
    backend_url = st.text_input("백엔드 URL", value=DEFAULT_BACKEND_URL)
    max_wait_seconds = st.slider("최대 대기 시간(초)", min_value=20, max_value=120, value=MAX_WAIT_SECONDS, step=10)
    poll_interval = st.slider("폴링 간격(초)", min_value=1, max_value=5, value=POLL_INTERVAL_SECONDS, step=1)
    st.caption("백엔드 스펙은 유지하고, 클라이언트에서만 실행 옵션을 조절합니다.")

left_col, right_col = st.columns([1.4, 1.0], gap="large")

with left_col:
    with st.container(border=True):
        st.markdown('<div class="panel-title">지원자 프로필 입력</div><div class="panel-copy">자기소개서와 희망 조건을 함께 입력하면, 추천 결과에 바로 반영됩니다.</div>', unsafe_allow_html=True)
        cover_letter = st.text_area("자기소개서", value=st.session_state.latest_cover_letter, height=340, placeholder="경험, 성과, 협업 방식, 기술 스택을 중심으로 작성해보세요.")
        st.caption(f"현재 글자 수: {len(cover_letter.strip())}자")

with right_col:
    with st.container(border=True):
        job_role = st.text_input("희망 직무", "백엔드 개발자")
        experience_levels = st.multiselect("경력 수준", ["신입", "인턴", "경력", "상관없음"], default=["신입"])
        region = st.text_input("희망 근무지", "서울, 판교, 해외 가능")
        tech_stack = st.text_input("기술 스택", "Spring, Redis, AWS")
        render_preference_pills(job_role, experience_levels, region, tech_stack)
        only_with_reward = st.toggle("보상 정보가 있는 공고 우선", value=False)
        is_urgent = st.toggle("마감 임박 공고 우선", value=False)
        submitted = st.button("공고 추천 받기", use_container_width=True, type="primary")


if submitted:
    if not cover_letter.strip():
        st.error("자기소개서를 입력해주세요.")
        st.stop()

    request_body = {
        "coverLetter": cover_letter.strip(),
        "preferences": {
            "jobRole": job_role.strip(),
            "experienceLevel": join_optional(experience_levels),
            "techStack": split_csv(tech_stack),
            "region": region.strip(),
            "onlyWithReward": only_with_reward,
            "isUrgent": is_urgent,
        },
    }

    st.session_state.latest_request_body = request_body
    st.session_state.latest_cover_letter = cover_letter

    render_request_insights(request_body, cover_letter)

    try:
        task_id = create_task(backend_url, request_body)
        st.info("추천 작업을 시작했습니다. 결과를 순차적으로 정리하고 있습니다.")

        deadline = time.time() + max_wait_seconds
        status_area = st.empty()
        progress_area = st.empty()
        result = None
        step_index = 0

        while time.time() < deadline:
            result = poll_task(backend_url, task_id)
            elapsed_ratio = 1 - max(deadline - time.time(), 0) / max_wait_seconds
            progress_area.progress(min(elapsed_ratio, 1.0), text="AI 추천 작업 진행 중")
            status_area.info(PROCESSING_MESSAGES[step_index % len(PROCESSING_MESSAGES)])
            step_index += 1

            if result.get("status") in FINISHED_STATUSES:
                break

            time.sleep(poll_interval)

        progress_area.empty()
        status_area.empty()

        if result is None:
            st.session_state.latest_result = None
            st.error("추천 결과를 가져오지 못했습니다.")
        elif result.get("status") in FINISHED_STATUSES:
            st.session_state.latest_result = result
            render_result(result)
        else:
            st.session_state.latest_result = result
            st.warning("추천 결과 준비가 예상보다 오래 걸리고 있습니다. 잠시 후 다시 시도해주세요.")
            st.json(result)
    except requests.RequestException as exc:
        st.session_state.latest_result = None
        st.error("추천 서버와 연결하지 못했습니다. 잠시 후 다시 시도해주세요.")
        st.code(str(exc))
    except (KeyError, TypeError) as exc:
        st.session_state.latest_result = None
        st.error("추천 결과 형식이 예상과 다릅니다.")
        st.code(str(exc))
elif st.session_state.latest_result is not None:
    st.markdown("### 최근 추천 결과")
    if st.session_state.latest_request_body is not None:
        render_request_insights(st.session_state.latest_request_body, st.session_state.latest_cover_letter)
    render_result(st.session_state.latest_result)
