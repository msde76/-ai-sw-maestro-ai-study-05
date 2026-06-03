from typing import Protocol

from app.graph.state import GraphState


class JobSearchClient(Protocol):
    async def search_jobs(self, query: dict) -> list[dict]:
        ...


async def search_jobs(state: GraphState, client: JobSearchClient) -> GraphState:
    candidates = await client.search_jobs(state["search_query"])
    return {"candidate_jobs": candidates}
