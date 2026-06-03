from fastapi import FastAPI


app = FastAPI(title="Job Recommendation AI Server")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
