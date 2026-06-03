from fastapi import APIRouter

from app.api.schemas import AnalyzeRequest, JobData


router = APIRouter()


@router.post("/ai/analyze", response_model=list[JobData])
async def analyze_jobs(request: AnalyzeRequest) -> list[JobData]:
    return []
