from typing import List, Optional

from pydantic import BaseModel, Field


class RecommendRequest(BaseModel):
    query: str = Field(..., min_length=1)


class SRMItem(BaseModel):
    name: str
    url: str
    work_type: Optional[str] = None


class TeamItem(BaseModel):
    id: str
    name: str
    department: Optional[str] = None
    mission: Optional[str] = None
    technologies: List[str] = []
    services_offered: List[str] = []
    team_lead: Optional[str] = None
    srm_suggestions: List[SRMItem] = []
    score: float = 0.0
    rationale: Optional[str] = None


class RecommendResponse(BaseModel):
    work_type: Optional[str] = None
    teams: List[TeamItem]
    query: str


class IngestResponse(BaseModel):
    indexed: int
    details: Optional[str] = None


