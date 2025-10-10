from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Tuple

import pandas as pd

from ..models.entities import Team, SRM


def _split_multi(value: object) -> List[str]:
    """Normalize a semi-colon or comma delimited cell into list of strings."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = [p.strip() for p in text.replace("\n", ";").replace(",", ";").split(";")]
    return [p for p in parts if p]


def load_teams_from_excel(xlsx_path: str | Path) -> Tuple[List[Team], List[SRM]]:
    """Load teams and SRMs from an Excel workbook.

    The extractor is tolerant to column naming by using a set of preferred names
    with fallbacks. Recommended columns:
    - team_name, department, mission, technologies, services_offered,
      team_lead, contacts, consulting_types
    - srm_name, srm_url, work_type
    Additional columns are ignored.
    """
    path = Path(xlsx_path)
    if not path.exists():
        raise FileNotFoundError(f"Excel file not found: {path}")

    logging.getLogger(__name__).info("Loading Excel workbook: %s", path)
    df = pd.read_excel(path)

    def pick(row, *names, default=None):  # type: ignore[no-untyped-def]
        for n in names:
            if n in row and pd.notna(row[n]):
                return row[n]
        return default

    teams: List[Team] = []
    srms: List[SRM] = []

    for _, row in df.iterrows():
        team_name = pick(row,
                         "team_name", "Team", "Team Name",
                         default=None)
        if not team_name:
            # Skip rows without a team name
            continue

        team = Team(
            id=str(team_name).strip().lower().replace(" ", "-"),
            name=str(team_name).strip(),
            department=pick(row, "department", "Department"),
            mission=pick(row, "mission", "Mission"),
            description=pick(row, "description", "Description"),
            technologies=_split_multi(pick(row, "technologies", "Technologies")),
            services_offered=_split_multi(pick(row, "services_offered", "Services", "Offerings")),
            contacts=_split_multi(pick(row, "contacts", "Contact", "Contacts")),
            team_lead=pick(row, "team_lead", "Lead", "Manager"),
            consulting_types=_split_multi(pick(row, "consulting_types", "Consulting Types")),
        )
        teams.append(team)

        srm_name = pick(row, "srm_name", "SRM Name")
        srm_url = pick(row, "srm_url", "SRM URL", "srm_link")
        work_type = pick(row, "work_type", "Work Type")
        if srm_name and srm_url:
            srms.append(
                SRM(
                    name=str(srm_name).strip(),
                    url=str(srm_url).strip(),
                    work_type=str(work_type).strip() if work_type else "",
                    team_id=team.id,
                )
            )

    logging.getLogger(__name__).info("Loaded %d teams and %d SRMs from Excel", len(teams), len(srms))
    return teams, srms


