import re
from collections.abc import Iterable

from app.graph.state import GraphState


ROLE_SKILL_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("백엔드", "서버", "backend", "server"), "Backend"),
    (("프론트엔드", "프론트", "frontend", "front"), "Frontend"),
    (("풀스택", "fullstack"), "Fullstack"),
    (("ios",), "iOS"),
    (("android",), "Android"),
    (("devops", "인프라", "infra"), "DevOps"),
    (("데이터", "data"), "Data Analysis"),
    (("ai", "머신러닝", "ml", "machine learning"), "AI"),
)

DOMAIN_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
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
    joined_text = " ".join(role_texts).lower()
    matches: list[tuple[int, int, str]] = []
    for rule_index, (needles, skill) in enumerate(ROLE_SKILL_RULES):
        positions = [_find_keyword_position(joined_text, needle) for needle in needles]
        positions = [position for position in positions if position >= 0]
        if positions:
            matches.append((min(positions), rule_index, skill))

    matched: list[str] = []
    for _, _, skill in sorted(matches):
        if not _contains_case_insensitive(matched, skill):
            matched.append(skill)
    return matched


def _domain_query(role_texts: list[str]) -> str:
    joined_text = " ".join(role_texts).lower()
    matches: list[str] = []
    for needles, keyword in DOMAIN_KEYWORDS:
        if any(_find_keyword_position(joined_text, needle) >= 0 for needle in needles):
            matches.append(keyword)
        if len(matches) >= 2:
            break
    return " ".join(matches)


def _find_keyword_position(text: str, keyword: str) -> int:
    if keyword.isascii():
        match = re.search(rf"(?<![a-z0-9]){re.escape(keyword.lower())}(?![a-z0-9])", text)
        return match.start() if match else -1
    return text.find(keyword)


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
