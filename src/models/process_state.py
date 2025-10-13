'''
State models for the SRM discovery process.
'''

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    '''A candidate SRM recommendation.'''
    
    srm_id: str = Field(description="The unique ID of the SRM")
    name: str = Field(description="The name/title of the SRM")
    category: str = Field(description="The category of the SRM")
    owning_team: str = Field(description="The team that owns this SRM")
    use_case: str = Field(description="Description of when to use this SRM")
    score: float = Field(default=0.0, description="Relevance score for ranking")


class Decision(BaseModel):
    '''The final recommendation decision.'''
    
    selected_id: Optional[str] = Field(default=None, description="The selected SRM ID")
    confidence: float = Field(default=0.0, description="Confidence in the selection (0-1)")
    alternatives: list[Candidate] = Field(default_factory=list, description="Alternative options")


class RetrievalResult(BaseModel):
    '''Results from vector search retrieval.'''
    
    hits: list[dict] = Field(default_factory=list, description="Raw search hits")
    filters: dict = Field(default_factory=dict, description="Applied filters")
    top_k: int = Field(default=8, description="Number of results retrieved")


class ClarityState(BaseModel):
    '''State tracking for clarity and clarification.'''
    
    key_terms: list[str] = Field(default_factory=list, description="Extracted key terms from query")
    needs_clarification: bool = Field(default=False, description="Whether clarification is needed")
    clarification_question: Optional[str] = Field(default=None, description="The question to ask user")
    clarification_history: list[str] = Field(default_factory=list, description="History of clarifications")


@dataclass
class ProcessState:
    '''
    Overall process state for SRM discovery.
    
    This tracks the conversation state through the process.
    '''
    
    user_query: str = ""
    clarity: ClarityState = field(default_factory=ClarityState)
    retrieval: Optional[RetrievalResult] = None
    candidates: list[Candidate] = field(default_factory=list)
    decision: Optional[Decision] = None
    turn_count: int = 0
    is_complete: bool = False
    final_answer: str = ""

