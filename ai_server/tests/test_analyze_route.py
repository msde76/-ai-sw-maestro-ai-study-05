from fastapi.testclient import TestClient

from main import app


def test_analyze_accepts_spring_payload_and_returns_list():
    client = TestClient(app)
    payload = {
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

    response = client.post("/ai/analyze", json=payload)

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
