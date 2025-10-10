from typing import List

from .models.schemas import RecommendResponse, TeamItem, SRMItem
from .retriever import hybrid_search
from .llm import classify_work_type


async def recommend_from_query(query: str) -> RecommendResponse:
    """Run retrieval to produce preliminary team recommendations.

    This version uses Azure Search hybrid (semantic/keyword) until vector
    embeddings and classification are fully wired.
    """
    classification = classify_work_type(query)
    docs = hybrid_search(query, top_k=5)

    teams: List[TeamItem] = []
    for d in docs:
        if d.get("kind") != "team":
            continue
        teams.append(
            TeamItem(
                id=str(d.get("id", "")),
                name=str(d.get("name", "")),
                department=d.get("department"),
                mission=None,
                technologies=d.get("technologies", []) or [],
                services_offered=d.get("services_offered", []) or [],
                team_lead=d.get("team_lead"),
                srm_suggestions=[
                    SRMItem(name=n, url=u) for n, u in zip(d.get("srm_names", []) or [], d.get("srm_urls", []) or [])
                ],
                score=float(d.get("@search.score", 0.0) or 0.0),
                rationale="Match via semantic search on content",
            )
        )

    return RecommendResponse(work_type=classification.get("work_type"), teams=teams, query=query)


