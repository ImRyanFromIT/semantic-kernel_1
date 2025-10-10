import pandas as pd
from pathlib import Path

from semantic-kernel_poc.app.services.extractors.excel_extractor import load_teams_from_excel


def test_load_teams_from_excel(tmp_path: Path):
    df = pd.DataFrame(
        [
            {
                "team_name": "Backup Services",
                "department": "Data Storage Services",
                "technologies": "Veeam; CommVault",
                "services_offered": "Backup Design & Implementation; Backup Monitoring",
                "team_lead": "Pat Singh",
                "srm_name": "Backup/Restore Assistance",
                "srm_url": "https://srm.example/requests/backup-restore",
                "work_type": "configuration",
            }
        ]
    )
    xlsx = tmp_path / "teams.xlsx"
    df.to_excel(xlsx, index=False)

    teams, srms = load_teams_from_excel(xlsx)
    assert len(teams) == 1
    assert teams[0].name == "Backup Services"
    assert "Veeam" in teams[0].technologies
    assert len(srms) == 1
    assert srms[0].team_id == teams[0].id


