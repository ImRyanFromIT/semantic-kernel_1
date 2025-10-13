'''
Pydantic model for Team records from Azure AI Search.
'''

from dataclasses import dataclass, field
from typing import Annotated

from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel


@vectorstoremodel(collection_name="nlq-recommender-index")
@dataclass
class TeamRecord:
    '''
    Model to store Team records from Azure AI Search index.
    
    This represents teams that offer services and own SRMs.
    The index structure is team-centric with SRM information embedded.
    
    Fields:
        id: Unique identifier (e.g., "team_0e190f365abe")
        kind: Type of record (e.g., "team")
        name: Team name
        content: Full text description of team, services, and technologies
        technologies: List of technologies the team works with
        services_offered: List of services the team provides
        department: Department the team belongs to
        team: Team name (same as name)
        work_types: Types of work (e.g., "Decommission", "Provisioning")
        srm_names: List of SRM names owned by this team
        srm_urls: List of SRM URLs (corresponding to srm_names)
        embedding: Vector embedding for semantic search
    '''
    
    id: Annotated[str, VectorStoreField("key")]
    kind: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    name: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    content: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    technologies: Annotated[list[str], VectorStoreField("data")]
    services_offered: Annotated[list[str], VectorStoreField("data")]
    department: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    team: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    work_types: Annotated[list[str], VectorStoreField("data")]
    srm_names: Annotated[list[str], VectorStoreField("data")]
    srm_urls: Annotated[list[str], VectorStoreField("data")]
    embedding: Annotated[
        list[float] | None, 
        VectorStoreField("vector", dimensions=1536)
    ] = None

