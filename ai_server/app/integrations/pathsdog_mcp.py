import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def select_tool_name(tool_names: list[str], required_terms: list[str]) -> str:
    lowered_terms = [term.lower() for term in required_terms]
    for name in tool_names:
        lowered_name = name.lower()
        if all(term in lowered_name for term in lowered_terms):
            return name
    raise ValueError(f"No MCP tool matches required terms: {required_terms}")


def _content_to_dict(result: Any) -> dict[str, Any]:
    structured_content = getattr(result, "structuredContent", None)
    if structured_content:
        return dict(structured_content)

    content = getattr(result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", "")
        if text:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload
            return {"items": payload}

    return {}


class PathsdogMCPClient:
    def __init__(self, url: str):
        self._url = url

    async def search_jobs(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        async with streamablehttp_client(self._url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                search_tool = select_tool_name(tool_names, ["search", "job"])
                result = await session.call_tool(search_tool, query)
                payload = _content_to_dict(result)

        items = payload.get("jobs") or payload.get("items") or payload.get("results") or []
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]
