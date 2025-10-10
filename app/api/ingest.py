from fastapi import APIRouter

from ..services.indexer import trigger_ingestion
from ..services.models.schemas import IngestResponse


router = APIRouter(prefix="/api", tags=["ingest"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest() -> IngestResponse:
    """Trigger a batch ingestion from the configured data directory.

    This is a synchronous stub for the PoC; in production this should become an
    async background task or a job runner trigger.
    """
    return await trigger_ingestion()


