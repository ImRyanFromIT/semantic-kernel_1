'''
Pydantic model for SRM records with vector embeddings.
'''

from dataclasses import dataclass, field
from typing import Annotated
from uuid import uuid4

from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel


@vectorstoremodel(collection_name="srm-catalog")
@dataclass
class SRMRecord:
    '''
    Model to store SRM (Service Request Model) records with vector embeddings.
    
    Fields:
        name: The name/title of the SRM
        category: The category of the SRM (e.g., Provisioning, Restore, Change)
        owning_team: The team that owns this SRM
        use_case: Description of when to use this SRM
        text: Combined text for embedding generation
        owner_notes: Notes for SRM owners (publicly visible)
        hidden_notes: Internal notes (not shown to end users)
        id: Unique identifier
        embedding: Vector embedding for semantic search
    '''
    
    name: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    category: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    owning_team: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    use_case: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    text: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    owner_notes: Annotated[str, VectorStoreField("data")] = ""
    hidden_notes: Annotated[str, VectorStoreField("data")] = ""
    id: Annotated[str, VectorStoreField("key")] = field(default_factory=lambda: str(uuid4()))
    embedding: Annotated[
        list[float] | str | None, 
        VectorStoreField("vector", dimensions=1536)
    ] = None

    def __post_init__(self):
        '''Generate text for embedding if not already set.'''
        if self.embedding is None:
            # Combine fields for rich semantic search
            self.embedding = f"{self.name} {self.category} {self.use_case} {self.owning_team}"

