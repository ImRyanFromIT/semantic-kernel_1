from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswParameters,
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
)
from azure.core.exceptions import HttpResponseError

from ..utils.config import get_config
from ..utils.scoring import jaccard
from .models.schemas import IngestResponse
from .extractors.excel_extractor import load_teams_from_excel
from .extractors.pptx_extractor import extract_org_chart_snippets
from .llm import embed_texts
from .extractors.csv_extractor import load_from_data_dir


def _search_clients() -> tuple[SearchIndexClient, SearchClient]:
    cfg = get_config()
    cred = AzureKeyCredential(cfg.azure_search.api_key)
    endpoint = str(cfg.azure_search.endpoint).rstrip('/')
    index_client = SearchIndexClient(endpoint=endpoint, credential=cred)
    doc_client = SearchClient(endpoint=endpoint, index_name=cfg.azure_search.index_name, credential=cred)
    return index_client, doc_client


def ensure_index() -> bool:
    cfg = get_config()
    index_client, _ = _search_clients()
    name = cfg.azure_search.index_name
    try:
        existing = index_client.get_index(name)
        existing_fields = {getattr(f, "name", "") for f in getattr(existing, "fields", []) or []}

        # Add missing non-vector fields if needed (e.g., srm_names/srm_urls)
        missing: list[SearchField] = []
        if "srm_names" not in existing_fields:
            missing.append(
                SearchField(
                    name="srm_names",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                    searchable=True,
                )
            )
        if "srm_urls" not in existing_fields:
            missing.append(
                SearchField(name="srm_urls", type=SearchFieldDataType.Collection(SearchFieldDataType.String))
            )
        if missing:
            new_fields = list(getattr(existing, "fields", []) or []) + missing
            updated_index = SearchIndex(
                name=name,
                fields=new_fields,
                semantic_search=getattr(existing, "semantic_search", None),
                vector_search=getattr(existing, "vector_search", None),
            )
            index_client.create_or_update_index(updated_index)
            existing_fields.update({f.name for f in missing})

        return "vector" in existing_fields
    except Exception:
        pass

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SimpleField(name="kind", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="name", type=SearchFieldDataType.String, sortable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SearchField(name="technologies", type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                    searchable=True, filterable=True),
        SearchField(name="services_offered", type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                    searchable=True, filterable=True),
        SimpleField(name="department", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="team", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="work_types", type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                    filterable=True, facetable=True),
        SearchField(name="consulting_types", type=SearchFieldDataType.Collection(SearchFieldDataType.String),
                    filterable=True, facetable=True),
        SearchField(name="srm_names", type=SearchFieldDataType.Collection(SearchFieldDataType.String), searchable=True),
        SearchField(name="srm_urls", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
    ]

    vector_search = VectorSearch(
        algorithms=[VectorSearchAlgorithmConfiguration(name="hnsw", kind="hnsw", hnsw_parameters=HnswParameters())],
        profiles=[VectorSearchProfile(name="default", algorithm_configuration_name="hnsw")],
    )

    # Prefer SemanticSearch; fall back to SemanticSettings for older API versions
    semantic = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="default",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="name"),
                    content_fields=[SemanticField(field_name="content")],
                ),
            )
        ]
    )

    # Attempt vector-capable index first
    try:
        fields_with_vector = list(fields) + [
            SearchField(
                name="vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1536,
                vector_search_profile_name="default",
            )
        ]
        index = SearchIndex(name=name, fields=fields_with_vector, vector_search=vector_search, semantic_search=semantic)
        index_client.create_index(index)
        return True
    except HttpResponseError as vec_err:
        logging.getLogger(__name__).warning("Vector index creation failed, falling back to text-only: %s", vec_err)
    except Exception as exc:
        logging.getLogger(__name__).warning("Vector index creation exception, falling back: %s", exc)

    # Fallback: text-only index (no vector field/search)
    try:
        index = SearchIndex(name=name, fields=fields, semantic_search=semantic)
        index_client.create_index(index)
        return False
    except Exception as create_exc:
        logging.getLogger(__name__).exception("Failed to create Azure Search index (fallback)")
        raise create_exc


def _hash_id(prefix: str, text: str) -> str:
    # Azure AI Search keys must be URL-safe: letters, digits, '_', '-', '=' only
    return f"{prefix}_{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}"


def _aggregate_content(mission: str, services: List[str], technologies: List[str]) -> str:
    parts = []
    if mission:
        parts.append(mission)
    if services:
        parts.append("Services: " + ", ".join(services))
    if technologies:
        parts.append("Technologies: " + ", ".join(technologies))
    return " \n".join(parts)


async def trigger_ingestion() -> IngestResponse:
    cfg = get_config()
    configured = Path(cfg.ingestion.data_dir)
    if configured.is_absolute():
        root = configured
    else:
        # Resolve relative to the project package directory to avoid CWD issues
        pkg_root = Path(__file__).resolve().parents[2]
        root = (pkg_root / configured).resolve()
    logging.getLogger(__name__).info("Ingestion data directory: %s", root)
    excel_files = list(root.glob("*.xlsx")) + list(root.glob("*.xls"))
    pptx_files = list(root.glob("*.pptx"))

    teams: List[dict] = []

    # Excel is authoritative for team facts and SRMs
    all_teams = []
    all_srms = []
    # Prefer CSVs if present (as per your provided /data folder)
    csv_teams, csv_srms = load_from_data_dir(root)
    all_teams.extend(csv_teams)
    all_srms.extend(csv_srms)
    for xf in excel_files:
        tms, srms = load_teams_from_excel(xf)
        all_teams.extend(tms)
        all_srms.extend(srms)

    # PPTX enriches snippets; associate by team slug best-effort
    team_slug_to_team = {t.id: t for t in all_teams}
    for pf in pptx_files:
        snippets, inferred_teams = extract_org_chart_snippets(pf)
        for s in snippets:
            if s.team_id and s.team_id in team_slug_to_team:
                t = team_slug_to_team[s.team_id]
                # Heuristic enrichment: append to description
                if s.section_type == "mission" and not t.mission:
                    t.mission = s.content
                elif s.section_type == "technologies":
                    t.technologies = list({*t.technologies, *[x.strip() for x in s.content.split(',') if x.strip()]})
                elif s.section_type == "services":
                    t.services_offered = list({*t.services_offered, *[x.strip() for x in s.content.split(',') if x.strip()]})

    # Attach SRMs to teams
    for srm in all_srms:
        if srm.team_id in team_slug_to_team:
            team_slug_to_team[srm.team_id].srm_links.append(srm)

    # Build indexable docs
    for t in team_slug_to_team.values():
        content = _aggregate_content(t.mission or "", t.services_offered, t.technologies)
        doc: Dict[str, Any] = {
            "id": _hash_id("team", t.id),
            "kind": "team",
            "name": t.name,
            "department": t.department,
            "team": t.name,
            "content": content,
            "technologies": t.technologies,
            "services_offered": t.services_offered,
            "work_types": list({link.work_type for link in t.srm_links if link.work_type}),
            "srm_names": [link.name for link in t.srm_links],
            "srm_urls": [link.url for link in t.srm_links],
        }
        teams.append(doc)

    has_vector = ensure_index()
    _, doc_client = _search_clients()
    if teams:
        # Generate embeddings only if index has vector field
        if has_vector:
            vectors = embed_texts([d["content"] for d in teams])
            for d, v in zip(teams, vectors):
                d["vector"] = v
        r = doc_client.upload_documents(documents=teams)
        succeeded = sum(1 for x in r if getattr(x, "succeeded", False))
    else:
        succeeded = 0

    logging.getLogger(__name__).info("Upserted %d team documents", succeeded)
    return IngestResponse(indexed=succeeded, details=f"Processed {len(csv_teams)} CSV teams, {len(excel_files)} Excel files and {len(pptx_files)} PPTX files")


