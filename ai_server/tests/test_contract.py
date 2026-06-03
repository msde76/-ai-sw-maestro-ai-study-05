from app.api.schemas import Analysis, JobData


def test_job_data_serializes_to_spring_dto_shape():
    job = JobData(
        jobId="1",
        companyName="회사",
        jobTitle="백엔드 개발자",
        suitabilityScore=0.87,
        compensation="원문 확인 필요",
        deadline="원문 확인 필요",
        originalLink="https://example.com/1",
        analysis=Analysis(
            matchReason="Spring 경험과 관련성이 높습니다.",
            missingPoints="운영 경험 보완이 필요합니다.",
            checkpointGuide="API 성능 개선 경험을 강조하세요.",
        ),
    )

    assert job.model_dump() == {
        "jobId": "1",
        "companyName": "회사",
        "jobTitle": "백엔드 개발자",
        "suitabilityScore": 0.87,
        "compensation": "원문 확인 필요",
        "deadline": "원문 확인 필요",
        "originalLink": "https://example.com/1",
        "analysis": {
            "matchReason": "Spring 경험과 관련성이 높습니다.",
            "missingPoints": "운영 경험 보완이 필요합니다.",
            "checkpointGuide": "API 성능 개선 경험을 강조하세요.",
        },
    }
