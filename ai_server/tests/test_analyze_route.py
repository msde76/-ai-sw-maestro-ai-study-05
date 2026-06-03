from fastapi.testclient import TestClient

from app.integrations.pathsdog_mcp import PathsdogMCPError
from main import app


def _valid_payload():
    return {
        "coverLetter": "Spring Boot 프로젝트에서 예약 API와 Redis 캐시를 구현했습니다.",
        "preferences": {
            "jobRole": "백엔드 개발자",
            "experienceLevel": "신입",
            "techStack": ["Spring", "Redis"],
            "region": "서울",
            "onlyWithReward": False,
            "isUrgent": False,
        },
    }


def test_analyze_accepts_spring_payload_and_returns_list(monkeypatch):
    async def fake_run_workflow(workflow, request):
        return []

    app.state.workflow = object()
    monkeypatch.setattr("app.api.routes.run_workflow", fake_run_workflow)
    client = TestClient(app)

    response = client.post("/ai/analyze", json=_valid_payload())

    assert response.status_code == 200
    assert response.json() == []


def test_analyze_rejects_missing_cover_letter():
    client = TestClient(app)
    payload = {
        "preferences": {
            "jobRole": "백엔드 개발자",
            "experienceLevel": "신입",
            "techStack": ["Spring"],
            "region": "서울",
            "onlyWithReward": False,
            "isUrgent": False,
        }
    }

    response = client.post("/ai/analyze", json=payload)

    assert response.status_code == 422


def test_analyze_returns_bad_gateway_for_value_error(monkeypatch):
    async def fake_run_workflow(workflow, request):
        raise ValueError("bad llm")

    app.state.workflow = object()
    monkeypatch.setattr("app.api.routes.run_workflow", fake_run_workflow)
    client = TestClient(app)

    response = client.post("/ai/analyze", json=_valid_payload())

    assert response.status_code == 502
    assert response.json() == {"detail": "bad llm"}


def test_analyze_returns_bad_gateway_for_pathsdog_mcp_error(monkeypatch):
    async def fake_run_workflow(workflow, request):
        raise PathsdogMCPError("mcp failed")

    app.state.workflow = object()
    monkeypatch.setattr("app.api.routes.run_workflow", fake_run_workflow)
    client = TestClient(app)

    response = client.post("/ai/analyze", json=_valid_payload())

    assert response.status_code == 502
    assert response.json() == {"detail": "mcp failed"}


def test_analyze_returns_generic_bad_gateway_for_unexpected_error(monkeypatch):
    async def fake_run_workflow(workflow, request):
        raise RuntimeError("unexpected")

    app.state.workflow = object()
    monkeypatch.setattr("app.api.routes.run_workflow", fake_run_workflow)
    client = TestClient(app)

    response = client.post("/ai/analyze", json=_valid_payload())

    assert response.status_code == 502
    assert response.json() == {"detail": "AI workflow failed"}


def test_analyze_reuses_startup_workflow(monkeypatch):
    workflow = object()
    calls = 0

    async def fake_run_workflow(received_workflow, request):
        nonlocal calls
        calls += 1
        assert received_workflow is workflow
        return []

    app.state.workflow = workflow
    monkeypatch.setattr("app.api.routes.run_workflow", fake_run_workflow)
    client = TestClient(app)

    first_response = client.post("/ai/analyze", json=_valid_payload())
    second_response = client.post("/ai/analyze", json=_valid_payload())

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert calls == 2
