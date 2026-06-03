from fastapi import APIRouter, HTTPException

from app.api.schemas import AnalyzeRequest, JobData
from app.core.config import Settings
from app.core.llm import UpstageLLM
from app.graph.workflow import build_workflow, run_workflow
from app.integrations.pathsdog_mcp import PathsdogMCPClient, PathsdogMCPError


router = APIRouter()


def create_workflow():
    settings = Settings()
    llm = UpstageLLM(settings)
    search_client = PathsdogMCPClient(str(settings.pathsdog_mcp_url))
    return build_workflow(llm, search_client)


@router.post("/ai/analyze", response_model=list[JobData])
async def analyze_jobs(request: AnalyzeRequest) -> list[JobData]:
    try:
        workflow = create_workflow()
        return await run_workflow(workflow, request)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except PathsdogMCPError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI workflow failed") from exc
