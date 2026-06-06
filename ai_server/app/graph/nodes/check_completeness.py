from app.graph.state import GraphState


def route_by_completeness(state: GraphState) -> str:
    profile = state.get("user_profile", {})
    return "build_query" if profile.get("isSufficient") is True else "format_response"
