from langgraph.graph import END, StateGraph

from app.api.schemas import AnalyzeRequest, JobData
from app.graph.nodes.analyze_user import analyze_user
from app.graph.nodes.build_query import build_query
from app.graph.nodes.check_completeness import route_by_completeness
from app.graph.nodes.enrich_job_details import enrich_job_details
from app.graph.nodes.format_response import format_response
from app.graph.nodes.score_jobs import score_jobs
from app.graph.nodes.search_jobs import search_jobs
from app.graph.state import GraphState


def build_workflow(llm, search_client):
    async def analyze_user_node(state: GraphState) -> GraphState:
        return await analyze_user(state, llm)

    async def search_jobs_node(state: GraphState) -> GraphState:
        return await search_jobs(state, search_client)

    async def score_jobs_node(state: GraphState) -> GraphState:
        return await score_jobs(state, llm)

    async def enrich_job_details_node(state: GraphState) -> GraphState:
        return await enrich_job_details(state, search_client)

    graph = StateGraph(GraphState)

    graph.add_node("analyze_user", analyze_user_node)
    graph.add_node("build_query", build_query)
    graph.add_node("search_jobs", search_jobs_node)
    graph.add_node("score_jobs", score_jobs_node)
    graph.add_node("enrich_job_details", enrich_job_details_node)
    graph.add_node("format_response", format_response)

    graph.set_entry_point("analyze_user")
    graph.add_conditional_edges(
        "analyze_user",
        route_by_completeness,
        {
            "build_query": "build_query",
            "format_response": "format_response",
        },
    )
    graph.add_edge("build_query", "search_jobs")
    graph.add_edge("search_jobs", "score_jobs")
    graph.add_edge("score_jobs", "enrich_job_details")
    graph.add_edge("enrich_job_details", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()


async def run_workflow(workflow, request: AnalyzeRequest) -> list[JobData]:
    result = await workflow.ainvoke({"request": request})
    return result.get("response_jobs", [])
