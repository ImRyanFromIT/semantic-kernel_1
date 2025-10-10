from __future__ import annotations

from typing import Any, Dict, List

from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError

from ..utils.config import get_config


def _search_client() -> SearchClient:
    cfg = get_config()
    return SearchClient(
        endpoint=str(cfg.azure_search.endpoint),
        index_name=cfg.azure_search.index_name,
        credential=AzureKeyCredential(cfg.azure_search.api_key),
    )


def hybrid_search(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Semantic search (with service-side semantic ranker).

    Vector param is omitted for broad SDK compatibility.
    """
    client = _search_client()
    try:
        results = client.search(
            search_text=query,
            query_type="semantic",
            semantic_configuration_name="default",
            top=top_k,
        )
    except ResourceNotFoundError as e:
        # Surface to caller to signal that ingestion/index creation is required
        raise
    docs: List[Dict[str, Any]] = []
    for doc in results:
        docs.append(dict(doc))
    return docs


