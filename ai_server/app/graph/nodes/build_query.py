from app.graph.state import GraphState


def build_query(state: GraphState) -> GraphState:
    request = state["request"]
    profile = state.get("user_profile", {})
    role = request.preferences.jobRole or profile.get("jobDirection", "")
    skills = _search_skills(request.preferences.techStack or profile.get("technicalSkills", []))
    query = _domain_query(role)

    search_query = {
        "query": query,
        "skills": skills,
        "experience_filter": _experience_filter(request.preferences.experienceLevel),
        "has_compensation": request.preferences.onlyWithReward,
        "urgency": "closing_soon" if request.preferences.isUrgent else "all",
        "status": "active",
        "limit": 10,
    }
    return {"search_query": {key: value for key, value in search_query.items() if value not in ("", [], None)}}


def _domain_query(role: str) -> str:
    domain_keywords = ["데이터", "머신러닝", "AI", "LLM", "백엔드", "프론트엔드", "인프라", "DevOps", "SRE"]
    matches = [keyword for keyword in domain_keywords if keyword.lower() in role.lower()]
    if matches:
        return " ".join(matches[:2])

    generic_terms = ["개발자", "엔지니어", "채용", "공고", "신입", "경력"]
    query = role
    for term in generic_terms:
        query = query.replace(term, " ")
    return " ".join(query.split())


def _search_skills(skills: list[str]) -> list[str]:
    priority = ["Python", "LLM", "Java", "Spring", "Backend", "React", "SQL", "Azure", "AWS"]
    selected: list[str] = []
    for wanted in priority:
        for skill in skills:
            if skill.lower() == wanted.lower() and skill not in selected:
                selected.append(skill)
                break
        if len(selected) >= 2:
            return selected
    for skill in skills:
        if skill not in selected:
            selected.append(skill)
        if len(selected) >= 2:
            break
    return selected


def _experience_filter(experience_level: str) -> str:
    for value in ["인턴", "신입", "주니어", "미들", "시니어"]:
        if value in experience_level:
            return value
    return ""
