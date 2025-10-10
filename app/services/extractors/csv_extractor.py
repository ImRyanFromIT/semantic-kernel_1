from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from ..models.entities import SRM, Team


def _split_multi(value: object) -> List[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    text = str(value).strip()
    if not text:
        return []
    parts = [p.strip() for p in text.replace("\n", ";").replace(",", ";").split(";")]
    return [p for p in parts if p]


def load_from_data_dir(data_dir: str | Path) -> Tuple[List[Team], List[SRM]]:
    """Load teams and SRMs from CSV files in a directory.

    Expected files (any subset tolerated):
    - teams.csv: columns team_name, department, mission, technologies, services_offered, team_lead
    - srm_catalog.csv: columns team_name or team_id, srm_name, srm_url, work_type
    - employees.csv: optional enrichment with columns team_name, name, level
    - org_structure.csv: optional mapping of team_name to department
    """
    base = Path(data_dir)
    teams_csv = base / "teams.csv"
    srms_csv = base / "srm_catalog.csv"
    employees_csv = base / "employees.csv"
    org_csv = base / "org_structure.csv"

    teams: Dict[str, Team] = {}
    srms: List[SRM] = []

    if teams_csv.exists():
        df = pd.read_csv(teams_csv)

        def pick(row, *names, default=None):  # type: ignore[no-untyped-def]
            for n in names:
                if n in row and pd.notna(row[n]):
                    return row[n]
            return default

        for _, row in df.iterrows():
            name = pick(row, "team_name", "Team", "Team Name", "team", "name")
            if not name:
                continue
            slug = str(name).strip().lower().replace(" ", "-")
            teams[slug] = Team(
                id=slug,
                name=str(name).strip(),
                department=pick(row, "department", "Department", "dept", "Dept"),
                mission=pick(row, "mission", "Mission", "scope", "Scope", "mandate", "Mandate"),
                technologies=_split_multi(
                    pick(
                        row,
                        "technologies",
                        "Technologies",
                        "technology",
                        "Technology",
                        "tech",
                        "Tech",
                        "technologies_owned_and_used",
                        "Technologies Owned and Used",
                    )
                ),
                services_offered=_split_multi(
                    pick(
                        row,
                        "services_offered",
                        "Services",
                        "services",
                        "Service Offerings",
                        "Offerings",
                    )
                ),
                team_lead=pick(row, "team_lead", "Lead", "Owner", "Manager", "Contact", "Primary Contact"),
            )

    if org_csv.exists():
        odf = pd.read_csv(org_csv)
        for _, row in odf.iterrows():
            team_name = row.get("team_name") or row.get("Team") or row.get("team") or row.get("name")
            department = row.get("department") or row.get("Department") or row.get("dept") or row.get("Dept")
            if not team_name or not department:
                continue
            slug = str(team_name).strip().lower().replace(" ", "-")
            if slug in teams:
                teams[slug].department = str(department)

    if employees_csv.exists():
        edf = pd.read_csv(employees_csv)
        for _, row in edf.iterrows():
            team_name = row.get("team_name") or row.get("Team") or row.get("team")
            emp_name = row.get("name") or row.get("Employee")
            if not team_name or not emp_name:
                continue
            slug = str(team_name).strip().lower().replace(" ", "-")
            if slug in teams:
                teams[slug].team_members.append(str(emp_name).strip())

    if srms_csv.exists():
        sdf = pd.read_csv(srms_csv)
        for _, row in sdf.iterrows():
            team_name = row.get("team_name") or row.get("Team") or row.get("team") or row.get("team_id") or row.get("owning_team")

            # Support compact key-value in one field, e.g. "name=...; category=..."
            meta = row.get("srm_metadata")
            parsed_name = None
            parsed_category = None
            if isinstance(meta, str) and "=" in meta:
                parts = [p.strip() for p in meta.split(";") if p.strip()]
                kv = {}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        kv[k.strip().lower()] = v.strip()
                parsed_name = kv.get("name")
                parsed_category = kv.get("category")

            srm_name = row.get("srm_name") or row.get("SRM Name") or row.get("name") or parsed_name
            srm_url = row.get("srm_url") or row.get("SRM URL") or row.get("url") or "#"
            work_type = (
                row.get("work_type")
                or row.get("Work Type")
                or row.get("type")
                or row.get("Type")
                or parsed_category
            )
            if not team_name or not srm_name:
                continue
            slug = str(team_name).strip().lower().replace(" ", "-")
            srms.append(
                SRM(
                    name=str(srm_name).strip(),
                    url=str(srm_url).strip(),
                    work_type=str(work_type).strip() if isinstance(work_type, str) else "",
                    team_id=slug,
                )
            )

    return list(teams.values()), srms


