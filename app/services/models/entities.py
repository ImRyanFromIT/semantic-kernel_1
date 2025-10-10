from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SRM:
    name: str
    url: str
    work_type: str
    team_id: str


@dataclass
class Team:
    id: str
    name: str
    department: Optional[str] = None
    mission: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = field(default_factory=list)
    services_offered: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    past_projects: List[str] = field(default_factory=list)
    contacts: List[str] = field(default_factory=list)
    team_lead: Optional[str] = None
    team_members: List[str] = field(default_factory=list)
    consulting_types: List[str] = field(default_factory=list)
    srm_links: List[SRM] = field(default_factory=list)


@dataclass
class DocumentSnippet:
    source: str
    title: str
    content: str
    url: Optional[str] = None
    team_id: Optional[str] = None
    section_type: Optional[str] = None


