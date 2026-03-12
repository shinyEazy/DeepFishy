from typing import List, Optional
from pydantic import BaseModel, Field


class KnowledgeSearchRequest(BaseModel):
    """Request schema for knowledge search."""

    query: str = Field(..., description="Search query in Vietnamese or English")
    top_k: int = Field(
        default=5, ge=1, le=20, description="Number of results to return"
    )
    category: Optional[str] = Field(
        default=None, description="Optional category filter"
    )


class SearchSource(BaseModel):
    """Schema for a search result source."""

    url: str
    category: str
    tags: List[str]
    relevance_score: float


class KnowledgeSearchResponse(BaseModel):
    """Response schema for knowledge search."""

    context: str = Field(..., description="Formatted context for LLM")
    sources: List[SearchSource]
    query: str
    num_results: int


class KnowledgeStatsResponse(BaseModel):
    """Response schema for knowledge base statistics."""

    total_documents: int
    collection_name: str
    status: str
    error: Optional[str] = None
