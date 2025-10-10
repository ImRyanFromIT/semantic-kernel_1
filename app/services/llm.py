from __future__ import annotations

import json
from functools import lru_cache
from typing import Dict, List

from openai import AzureOpenAI

from ..utils.config import get_config


@lru_cache(maxsize=1)
def _client() -> AzureOpenAI:
    cfg = get_config()
    # NOTE: AzureOpenAI requires an API version; pick a recent generally available one
    return AzureOpenAI(api_key=cfg.azure_openai.api_key, azure_endpoint=str(cfg.azure_openai.endpoint), api_version="2024-05-01-preview")


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    client = _client()
    resp = client.embeddings.create(model=get_config().azure_openai.deployments.embeddings, input=texts)
    return [d.embedding for d in resp.data]


def classify_work_type(query: str) -> Dict[str, object]:
    """Return a deterministic JSON classification for the user's query.

    Schema: {
      work_type: str | null,
      consulting_type: "ops" | "engineering" | null,
      confidence: float (0..1),
      normalized_keywords: string[]
    }
    """
    system = (
        "You classify IT service request intents into a fixed taxonomy and return ONLY JSON."
        " Taxonomy: configuration, vm_resource_increase, firewall_change, data_access,"
        " consulting.ops, consulting.engineering, incident, general."
    )
    user = f"Query: {query}\nReturn JSON with fields work_type, consulting_type, confidence (0-1), normalized_keywords[]"
    client = _client()
    chat_model = get_config().azure_openai.deployments.chat
    resp = client.chat.completions.create(
        model=chat_model,
        response_format={"type": "json_object"},
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = resp.choices[0].message.content
    try:
        return json.loads(content)
    except Exception:
        return {"work_type": None, "consulting_type": None, "confidence": 0.0, "normalized_keywords": []}


