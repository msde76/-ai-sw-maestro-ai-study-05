from fastapi import FastAPI

from app.api.routes import router as api_router


app = FastAPI(title="Job Recommendation AI Server")
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
