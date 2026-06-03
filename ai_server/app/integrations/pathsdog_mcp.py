import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class PathsdogMCPError(Exception):
    """Raised when the Pathsdog MCP response cannot be safely consumed."""


def select_tool_name(tool_names: list[str], required_terms: list[str]) -> str:
    lowered_terms = [term.lower() for term in required_terms]
    names_by_lower = {name.lower(): name for name in tool_names}
    known_exact_names = ["search_jobs"]
    for known_name in known_exact_names:
        if known_name in names_by_lower and all(term in known_name for term in lowered_terms):
            return names_by_lower[known_name]

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
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise PathsdogMCPError("Invalid JSON returned by Pathsdog MCP tool") from exc
            if isinstance(payload, dict):
                return payload
            return {"items": payload}

    return {}


def _extract_payload_from_result(result: Any) -> dict[str, Any]:
    if getattr(result, "isError", False):
        raise PathsdogMCPError("Pathsdog MCP tool returned an error")
    return _content_to_dict(result)


def _extract_items_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("jobs") or payload.get("items") or payload.get("results") or []
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


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
                payload = _extract_payload_from_result(result)

        return _extract_items_from_payload(payload)
