import json
import re
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class PathsdogMCPError(Exception):
    """Raised when the Pathsdog MCP response cannot be safely consumed."""


def select_tool_name(tool_names: list[str], required_terms: list[str]) -> str:
    lowered_terms = [term.lower() for term in required_terms]
    names_by_lower = {name.lower(): name for name in tool_names}
    known_exact_names = ["search_jobs", "get_job_detail"]
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
                parsed_jobs = _parse_search_jobs_text(text)
                if parsed_jobs is not None:
                    return {"items": parsed_jobs}
                raise PathsdogMCPError("Invalid JSON returned by Pathsdog MCP tool") from exc
            if isinstance(payload, dict):
                return payload
            return {"items": payload}

    return {}


def _parse_search_jobs_text(text: str) -> list[dict[str, Any]] | None:
    if "검색 결과가 없습니다" in text:
        return []
    if "[ID:" not in text:
        return None

    jobs: list[dict[str, Any]] = []
    blocks = re.split(r"\n(?=\[ID:)", text)
    for block in blocks:
        header_match = re.search(r"\[ID:(?P<id>\d+)\]\s*(?P<company>.+?)\s*-\s*(?P<title>.+)", block)
        if not header_match:
            continue

        job = {
            "jobId": header_match.group("id"),
            "companyName": header_match.group("company").strip(),
            "jobTitle": header_match.group("title").strip(),
            "sourceSnapshot": block.strip(),
        }

        tech_match = re.search(r"기술:\s*(?P<skills>.+)", block)
        if tech_match:
            job["skills"] = [skill.strip() for skill in tech_match.group("skills").split(",") if skill.strip()]

        experience_match = re.search(r"경력:\s*(?P<experience>.+?)(?:\s*\|\s*근무지:|\n)", block, re.DOTALL)
        if experience_match:
            job["experience"] = " ".join(experience_match.group("experience").split())

        location_match = re.search(r"근무지:\s*(?P<location>.+?)(?:\s*\||\n)", block, re.DOTALL)
        if location_match:
            job["location"] = " ".join(location_match.group("location").split())

        deadline_match = re.search(r"(마감:\s*(?P<deadline>.+)|(?P<always>상시채용))", block)
        if deadline_match:
            job["deadline"] = (deadline_match.group("deadline") or deadline_match.group("always") or "").strip()

        link_match = re.search(r"링크:\s*(?P<link>\S+)", block)
        if link_match:
            job["originalLink"] = link_match.group("link").strip()

        jobs.append(job)

    return jobs


def _extract_payload_from_result(result: Any) -> dict[str, Any]:
    if getattr(result, "isError", False):
        raise PathsdogMCPError("Pathsdog MCP tool returned an error")
    return _content_to_dict(result)


def _content_text(result: Any) -> str:
    if getattr(result, "isError", False):
        raise PathsdogMCPError("Pathsdog MCP tool returned an error")

    content = getattr(result, "content", None)
    if content:
        for item in content:
            text = getattr(item, "text", "")
            if isinstance(text, str) and text:
                return text

    raise PathsdogMCPError("No text returned by Pathsdog MCP tool")


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

    async def get_job_detail(self, job_id: str | int, *, include_full_description: bool = True) -> str:
        try:
            numeric_job_id = int(job_id)
        except (TypeError, ValueError) as exc:
            raise PathsdogMCPError(f"Invalid Pathsdog job id: {job_id}") from exc

        async with streamablehttp_client(self._url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                detail_tool = select_tool_name(tool_names, ["job", "detail"])
                result = await session.call_tool(
                    detail_tool,
                    {
                        "job_id": numeric_job_id,
                        "include_full_description": include_full_description,
                    },
                )

        return _content_text(result)
