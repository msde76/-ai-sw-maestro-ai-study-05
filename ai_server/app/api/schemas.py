from pydantic import BaseModel, Field


class Preferences(BaseModel):
    jobRole: str = Field(default="")
    experienceLevel: str = Field(default="")
    techStack: list[str] = Field(default_factory=list)
    region: str = Field(default="")
    onlyWithReward: bool = False
    isUrgent: bool = False


class AnalyzeRequest(BaseModel):
    coverLetter: str = Field(min_length=1)
    preferences: Preferences = Field(default_factory=Preferences)


class Analysis(BaseModel):
    matchReason: str
    missingPoints: str
    checkpointGuide: str


class JobData(BaseModel):
    jobId: str
    companyName: str
    jobTitle: str
    jobIntroduction: str
    suitabilityScore: float = Field(ge=0.0, le=1.0)
    compensation: str
    deadline: str
    originalLink: str | None = None
    analysis: Analysis
