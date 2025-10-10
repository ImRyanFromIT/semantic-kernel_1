from fastapi import APIRouter, HTTPException
from azure.core.exceptions import ResourceNotFoundError

from ..services.models.schemas import RecommendRequest, RecommendResponse
from ..services.router_service import recommend_from_query


router = APIRouter(prefix="/api", tags=["recommend"])


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest) -> RecommendResponse:
    """Return recommended teams and SRMs for a user query.

    For the initial PoC scaffold this delegates to a stubbed service that
    will be replaced by the full SK + Azure Search pipeline.
    """
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="Query must be a non-empty string")

    try:
        return await recommend_from_query(req.query)
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Search index not found. Run /api/ingest to create and populate the index, then retry.",
        )


