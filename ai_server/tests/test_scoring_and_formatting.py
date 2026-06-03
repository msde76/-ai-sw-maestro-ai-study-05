import pytest

from app.graph.nodes.format_response import format_response
from app.graph.nodes.score_jobs import score_jobs


class FakeScoringLLM:
    async def complete_json(self, messages):
        return {
            "jobs": [
                {
                    "jobId": "1",
                    "companyName": "A",
                    "jobTitle": "백엔드 개발자",
                    "suitabilityScore": 0.9,
                    "compensation": "원문 확인 필요",
                    "deadline": "원문 확인 필요",
                    "originalLink": "https://example.com/1",
                    "analysis": {
                        "matchReason": "Spring API 경험이 주요 업무와 관련성이 높습니다.",
                        "missingPoints": "대규모 운영 경험은 보완이 필요합니다.",
                        "checkpointGuide": "Redis 캐시 성능 개선 경험을 강조하세요.",
                    },
                },
                {
                    "jobId": "2",
                    "companyName": "B",
                    "jobTitle": "프론트엔드 개발자",
                    "suitabilityScore": 0.4,
                    "compensation": "원문 확인 필요",
                    "deadline": "원문 확인 필요",
                    "originalLink": "https://example.com/2",
                    "analysis": {
                        "matchReason": "일부 웹 경험만 관련됩니다.",
                        "missingPoints": "React 경험이 부족합니다.",
                        "checkpointGuide": "프론트엔드 경험을 보완하세요.",
                    },
                },
            ]
        }


@pytest.mark.asyncio
async def test_score_jobs_stores_scored_jobs():
    state = {
        "user_profile": {"technicalSkills": ["Spring", "Redis"]},
        "candidate_jobs": [{"jobId": "1", "jobTitle": "백엔드 개발자"}],
    }

    result = await score_jobs(state, FakeScoringLLM())

    assert len(result["scored_jobs"]) == 2
    assert result["scored_jobs"][0]["suitabilityScore"] == 0.9


def test_format_response_filters_and_sorts_top_five():
    state = {
        "scored_jobs": [
            {
                "jobId": str(i),
                "companyName": f"회사{i}",
                "jobTitle": "백엔드 개발자",
                "suitabilityScore": score,
                "compensation": "",
                "deadline": "",
                "originalLink": None,
                "analysis": {
                    "matchReason": "관련성이 높습니다.",
                    "missingPoints": "보완점입니다.",
                    "checkpointGuide": "강조 포인트입니다.",
                },
            }
            for i, score in enumerate([0.95, 0.91, 0.88, 0.8, 0.7, 0.69], start=1)
        ]
    }

    result = format_response(state)

    jobs = result["response_jobs"]
    assert len(jobs) == 5
    assert [job.suitabilityScore for job in jobs] == [0.95, 0.91, 0.88, 0.8, 0.7]
    assert jobs[0].compensation == "원문 확인 필요"
