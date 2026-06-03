from app.graph.state import GraphState


def build_query(state: GraphState) -> GraphState:
    request = state["request"]
    profile = state.get("user_profile", {})
    role = request.preferences.jobRole or profile.get("jobDirection", "")
    skills = request.preferences.techStack or profile.get("technicalSkills", [])
    keyword_parts = [role, *skills]
    keyword = " ".join(part.strip() for part in keyword_parts if part and part.strip())

    return {
        "search_query": {
            "keyword": keyword,
            "region": request.preferences.region,
            "experienceLevel": request.preferences.experienceLevel,
            "onlyWithReward": request.preferences.onlyWithReward,
            "isUrgent": request.preferences.isUrgent,
            "limit": 10,
        }
    }
